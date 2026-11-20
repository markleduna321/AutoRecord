import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import boto3


LOGGER = logging.getLogger(__name__)
R2_VARIABLES = (
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)


def create_r2_uploader():
    values = {name: os.environ.get(name, "").strip() for name in R2_VARIABLES}
    if not any(values.values()):
        LOGGER.info("R2 uploads are disabled. Set the R2 environment variables to enable them.")
        return None

    missing = [name for name, value in values.items() if not value]
    if missing:
        message = "Incomplete R2 configuration; missing: " + ", ".join(missing)
        LOGGER.error(message)
        raise ValueError(message)

    try:
        endpoint = urlsplit(values["R2_ENDPOINT_URL"])
        hostname = endpoint.hostname
        port = endpoint.port
    except ValueError as exc:
        LOGGER.error("Invalid R2_ENDPOINT_URL: %s", exc)
        raise ValueError("R2_ENDPOINT_URL must be a Cloudflare R2 HTTPS endpoint.") from exc
    if (
        endpoint.scheme != "https"
        or not hostname
        or not hostname.endswith(".r2.cloudflarestorage.com")
        or endpoint.username is not None
        or endpoint.password is not None
        or port not in (None, 443)
        or endpoint.path not in ("", "/")
        or endpoint.query
        or endpoint.fragment
    ):
        message = "R2_ENDPOINT_URL must be a Cloudflare R2 HTTPS endpoint."
        LOGGER.error(message)
        raise ValueError(message)

    client = boto3.client(
        "s3",
        endpoint_url=values["R2_ENDPOINT_URL"],
        aws_access_key_id=values["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=values["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    LOGGER.info("R2 uploads are enabled for bucket %s.", values["R2_BUCKET_NAME"])
    return R2Uploader(client, values["R2_BUCKET_NAME"])


class R2Uploader:
    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="r2-upload")
        self._recording_paths = []
        self._recording_in_progress = False

    def _remember_path(self, path):
        if not isinstance(path, str) or not path.strip():
            return False
        if path not in self._recording_paths:
            self._recording_paths.append(path)
        return True

    def on_recording_state_changed(self, event):
        try:
            state = event.getOutputState()
        except KeyError:
            LOGGER.error("OBS recording event did not include an output state.")
            return

        if state not in ("OBS_WEBSOCKET_OUTPUT_STARTED", "OBS_WEBSOCKET_OUTPUT_STOPPED"):
            return

        try:
            path = event.getOutputPath()
        except KeyError:
            path = None

        if state == "OBS_WEBSOCKET_OUTPUT_STARTED":
            if self._recording_in_progress:
                LOGGER.error("A new recording started before the previous stop event; check local recordings for missed uploads.")
            self._recording_paths = []
            self._recording_in_progress = True
            self._remember_path(path)
            return

        if not self._remember_path(path):
            LOGGER.error("OBS stopped without a recording path; only previously observed files can be uploaded.")
        paths = self._recording_paths
        self._recording_paths = []
        self._recording_in_progress = False
        for recording_path in paths:
            self._queue_upload(recording_path)

    def on_recording_file_changed(self, event):
        try:
            path = event.getNewOutputPath()
        except KeyError:
            path = None
        if not self._remember_path(path):
            LOGGER.error("OBS reported a recording file change without a new file path.")
            return
        self._recording_in_progress = True

    def _queue_upload(self, path):
        key = f"recordings/{uuid4().hex}/{Path(path).name}"
        try:
            future = self._executor.submit(self.client.upload_file, path, self.bucket, key)
        except RuntimeError as exc:
            LOGGER.error("Could not queue %s for R2 upload: %s. The local file was kept.", path, exc)
            return
        LOGGER.info("Queued %s for R2 upload.", path)
        future.add_done_callback(partial(self._report_upload, path=path, key=key))

    def _report_upload(self, future, path, key):
        if future.cancelled():
            LOGGER.error("R2 upload was cancelled for %s. The local file was kept.", path)
            return
        error = future.exception()
        if error is not None:
            LOGGER.error("R2 upload failed for %s: %s. The local file was kept.", path, error)
        else:
            LOGGER.info("Uploaded %s to R2 bucket %s as %s.", path, self.bucket, key)

    def close(self):
        if self._recording_in_progress:
            LOGGER.warning("OBS is still recording; it must stop while AutoRecord is running to upload its files.")
        LOGGER.info("Waiting for queued R2 uploads to finish.")
        self._executor.shutdown(wait=True)
