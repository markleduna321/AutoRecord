import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from botocore.stub import Stubber
from obswebsocket import events

import AutoRec
from r2_upload import R2Uploader, R2_VARIABLES, create_r2_uploader


CONFIG = {
    "R2_ENDPOINT_URL": "https://test-account.r2.cloudflarestorage.com",
    "R2_BUCKET_NAME": "recording-bucket",
    "R2_ACCESS_KEY_ID": "test-key",
    "R2_SECRET_ACCESS_KEY": "test-secret",
}


def recording_state(state, path=None):
    event = events.RecordStateChanged()
    event.input({"outputState": state, "outputPath": path})
    return event


def recording_file_changed(path):
    event = events.RecordFileChanged()
    event.input({"newOutputPath": path})
    return event


class R2ConfigurationTests(unittest.TestCase):
    def test_no_r2_configuration_keeps_recording_local_only(self):
        with mock.patch.dict(os.environ, {name: "" for name in R2_VARIABLES}):
            with self.assertLogs("r2_upload", level="INFO") as logs:
                self.assertIsNone(create_r2_uploader())
        self.assertIn("disabled", "\n".join(logs.output))

    def test_partial_configuration_fails_before_creating_a_client(self):
        config = dict(CONFIG, R2_SECRET_ACCESS_KEY="")
        with mock.patch.dict(os.environ, config), mock.patch("r2_upload.boto3.client") as client:
            with self.assertLogs("r2_upload", level="ERROR"):
                with self.assertRaisesRegex(ValueError, "R2_SECRET_ACCESS_KEY"):
                    create_r2_uploader()
        client.assert_not_called()

    def test_configures_r2_client_and_rejects_non_r2_endpoints(self):
        with mock.patch.dict(os.environ, CONFIG), mock.patch("r2_upload.boto3.client") as client:
            uploader = create_r2_uploader()
            self.assertIsNotNone(uploader)
            uploader.close()
        client.assert_called_once_with(
            "s3",
            endpoint_url=CONFIG["R2_ENDPOINT_URL"],
            aws_access_key_id=CONFIG["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=CONFIG["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

        with mock.patch.dict(os.environ, dict(CONFIG, R2_ENDPOINT_URL="https://example.com")):
            with self.assertLogs("r2_upload", level="ERROR"):
                with self.assertRaisesRegex(ValueError, "Cloudflare R2 HTTPS endpoint"):
                    create_r2_uploader()


class R2UploadTests(unittest.TestCase):
    def test_uploads_all_observed_files_only_after_recording_stops(self):
        client = mock.Mock()
        uploader = R2Uploader(client, "recording-bucket")
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory, "first.mkv")
            second = Path(directory, "second.mkv")
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STARTED", str(first)))
            uploader.on_recording_file_changed(recording_file_changed(str(second)))
            client.upload_file.assert_not_called()

            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", str(first)))
            uploader.close()

            calls = client.upload_file.call_args_list
            self.assertEqual([call.args[0] for call in calls], [str(first), str(second)])
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            keys = [call.args[2] for call in calls]
            self.assertEqual(len(set(keys)), 2)
            for call in calls:
                self.assertEqual(call.args[1], "recording-bucket")
                self.assertTrue(call.args[2].startswith("recordings/"))
                self.assertTrue(call.args[2].endswith("/" + Path(call.args[0]).name))

    def test_upload_does_not_block_the_obs_event_callback(self):
        started = threading.Event()
        release = threading.Event()
        client = mock.Mock()

        def upload(*args):
            started.set()
            if not release.wait(5):
                raise TimeoutError("Test upload was not released")

        client.upload_file.side_effect = upload
        uploader = R2Uploader(client, "recording-bucket")
        try:
            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", "capture.mkv"))
            self.assertTrue(started.wait(1))
            self.assertFalse(release.is_set())
        finally:
            release.set()
            uploader.close()

    def test_failed_upload_is_reported_and_local_file_is_kept(self):
        client = mock.Mock()
        client.upload_file.side_effect = OSError("network unavailable")
        uploader = R2Uploader(client, "recording-bucket")
        with tempfile.TemporaryDirectory() as directory:
            recording = Path(directory, "capture.mkv")
            recording.write_bytes(b"recording")
            with self.assertLogs("r2_upload", level="ERROR") as logs:
                uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", str(recording)))
                uploader.close()
            self.assertTrue(recording.exists())
            self.assertIn("network unavailable", "\n".join(logs.output))
            self.assertIn(str(recording), "\n".join(logs.output))

    def test_missing_stopped_path_is_reported(self):
        client = mock.Mock()
        uploader = R2Uploader(client, "recording-bucket")
        with self.assertLogs("r2_upload", level="ERROR") as logs:
            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED"))
            uploader.close()
        self.assertIn("without a recording path", "\n".join(logs.output))
        client.upload_file.assert_not_called()

    def test_registers_obs_event_handlers_before_connecting(self):
        client = mock.Mock()
        uploader = R2Uploader(client, "recording-bucket")
        with mock.patch("AutoRec.obsws") as obsws:
            ws = AutoRec.connect_obs(uploader)
        self.assertEqual(
            ws.method_calls,
            [
                mock.call.register(uploader.on_recording_state_changed, events.RecordStateChanged),
                mock.call.register(uploader.on_recording_file_changed, events.RecordFileChanged),
                mock.call.connect(),
            ],
        )
        uploader.close()

    def test_completed_file_reaches_the_real_boto3_transfer_client(self):
        with mock.patch.dict(os.environ, CONFIG):
            uploader = create_r2_uploader()

        requests = []

        def capture_request(params, **kwargs):
            requests.append((params["Bucket"], params["Key"]))

        uploader.client.meta.events.register("before-parameter-build.s3.PutObject", capture_request)
        with tempfile.TemporaryDirectory() as directory, Stubber(uploader.client) as stubber:
            recording = Path(directory, "capture.mkv")
            recording.write_bytes(b"recording")
            stubber.add_response("put_object", {"ETag": '"test"'})
            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", str(recording)))
            uploader.close()
            stubber.assert_no_pending_responses()
            self.assertTrue(recording.exists())

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0], CONFIG["R2_BUCKET_NAME"])
        self.assertTrue(requests[0][1].startswith("recordings/"))
        self.assertTrue(requests[0][1].endswith("/capture.mkv"))

    def test_large_recording_uses_multipart_upload(self):
        with mock.patch.dict(os.environ, CONFIG):
            uploader = create_r2_uploader()

        with tempfile.TemporaryDirectory() as directory, Stubber(uploader.client) as stubber:
            recording = Path(directory, "large.mkv")
            with recording.open("wb") as file:
                file.truncate(9 * 1024 * 1024)

            stubber.add_response("create_multipart_upload", {"UploadId": "test-upload"})
            stubber.add_response("upload_part", {"ETag": '"part-1"'})
            stubber.add_response("upload_part", {"ETag": '"part-2"'})
            stubber.add_response("complete_multipart_upload", {"ETag": '"complete"'})

            uploader.on_recording_state_changed(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", str(recording)))
            uploader.close()
            stubber.assert_no_pending_responses()
            self.assertTrue(recording.exists())

    def test_activity_timeout_stops_recording_and_uploads_it(self):
        client = mock.Mock()
        uploader = R2Uploader(client, "recording-bucket")
        ws = mock.Mock()
        handlers = {}
        clock = {"now": 0}
        obs_state = {"active": False}
        request_names = []

        def register(handler, event_type):
            handlers[event_type] = handler

        def emit(event):
            handlers[type(event)](event)

        def call(request):
            request_names.append(request.name)
            if request.name == "GetRecordStatus":
                request.input({"outputActive": obs_state["active"]}, True)
            elif request.name == "StartRecord":
                obs_state["active"] = True
                emit(recording_state("OBS_WEBSOCKET_OUTPUT_STARTED", str(recording)))
                request.input({}, True)
            elif request.name == "StopRecord":
                obs_state["active"] = False
                emit(recording_state("OBS_WEBSOCKET_OUTPUT_STOPPED", str(recording)))
                request.input({"outputPath": str(recording)}, True)
            return request

        def advance_clock(seconds):
            if clock["now"] == 0:
                clock["now"] = 61
            else:
                raise KeyboardInterrupt

        ws.register.side_effect = register
        ws.call.side_effect = call
        with tempfile.TemporaryDirectory() as directory:
            recording = Path(directory, "capture.mkv")
            recording.write_bytes(b"recording")
            with mock.patch.multiple(
                AutoRec,
                recording_active=False,
                last_activity_time=0,
                waiting_for_activity_to_start=True,
                activity_detected=True,
            ), mock.patch.object(AutoRec, "create_r2_uploader", return_value=uploader), \
                mock.patch.object(AutoRec, "open_obs"), \
                mock.patch.object(AutoRec, "obsws", return_value=ws), \
                mock.patch.object(AutoRec.keyboard, "hook", return_value="hook"), \
                mock.patch.object(AutoRec.keyboard, "unhook") as unhook, \
                mock.patch.object(AutoRec.mouse, "Listener") as listener, \
                mock.patch.object(AutoRec.time, "time", side_effect=lambda: clock["now"]), \
                mock.patch.object(AutoRec.time, "sleep", side_effect=advance_clock):
                AutoRec.main()

            self.assertEqual(request_names, ["GetRecordStatus", "StartRecord", "GetRecordStatus", "StopRecord"])
            client.upload_file.assert_called_once()
            self.assertEqual(client.upload_file.call_args.args[0], str(recording))
            self.assertTrue(recording.exists())
            ws.disconnect.assert_called_once()
            unhook.assert_called_once_with("hook")
            listener.return_value.stop.assert_called_once()

    def test_shutdown_waits_for_uploads_even_if_listener_cleanup_fails(self):
        uploader = mock.Mock()
        ws = mock.Mock()
        listener = mock.Mock()
        listener.stop.side_effect = RuntimeError("listener cleanup failed")

        with mock.patch.multiple(
            AutoRec,
            recording_active=False,
            waiting_for_activity_to_start=True,
            activity_detected=False,
        ), mock.patch.object(AutoRec, "create_r2_uploader", return_value=uploader), \
            mock.patch.object(AutoRec, "open_obs"), \
            mock.patch.object(AutoRec, "connect_obs", return_value=ws), \
            mock.patch.object(AutoRec.keyboard, "hook", return_value="hook"), \
            mock.patch.object(AutoRec.keyboard, "unhook"), \
            mock.patch.object(AutoRec.mouse, "Listener", return_value=listener), \
            mock.patch.object(AutoRec.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaisesRegex(RuntimeError, "listener cleanup failed"):
                AutoRec.main()

        ws.disconnect.assert_called_once()
        uploader.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
