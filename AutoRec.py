import keyboard
from pynput import mouse
from obswebsocket import events, obsws, requests
from contextlib import ExitStack
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
import time

from r2_upload import create_r2_uploader

# OBS WebSocket configuration
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "scit3P@ssw0rd"  # Replace with your actual password

# Global variables to track activity and recording state
recording_active = False
last_activity_time = time.time()
waiting_for_activity_to_start = True  # Start with waiting for activity to begin recording
activity_detected = False  # Flag to track if activity has been detected since last stop

# Open OBS
def open_obs():
    obs_path = r"C:\Program Files\obs-studio\bin\64bit"
    subprocess.Popen(["cmd", "/c", f"cd {obs_path} && obs64.exe --minimize-to-tray"])
    time.sleep(5)  # Wait for OBS to fully open

# Connect to OBS WebSocket
def connect_obs(uploader):
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    if uploader is not None:
        ws.register(uploader.on_recording_state_changed, events.RecordStateChanged)
        ws.register(uploader.on_recording_file_changed, events.RecordFileChanged)
    ws.connect()
    return ws

# Toggle recording based on activity
def toggle_recording(ws):
    global recording_active, last_activity_time, waiting_for_activity_to_start, activity_detected
    try:
        status = ws.call(requests.GetRecordStatus())

        if status.getOutputActive():
            ws.call(requests.StopRecord())
            print("Recording stopped.")
            recording_active = False
            activity_detected = False  # Reset activity flag after stopping recording
            waiting_for_activity_to_start = True  # Wait for new activity before starting again
        else:
            ws.call(requests.StartRecord())
            print("Recording started.")
            recording_active = True
            waiting_for_activity_to_start = False  # We don't need to wait anymore after starting recording
            activity_detected = True  # Recording has started, activity flag set to True

    except Exception as e:
        print(f"Error toggling recording: {e}")

# Activity detection callback for keyboard
def on_keyboard_activity(key):
    global last_activity_time, activity_detected
    last_activity_time = time.time()
    activity_detected = True  # Activity detected, ready to start recording

# Activity detection callback for mouse (handles both movement and clicks)
def on_mouse_activity(x, y, button=None, pressed=None):
    global last_activity_time, activity_detected
    last_activity_time = time.time()
    activity_detected = True  # Activity detected, ready to start recording

# Main function to start OBS and handle activity detection
def main():
    global recording_active, last_activity_time, waiting_for_activity_to_start, activity_detected

    uploader = create_r2_uploader()
    ws = None
    keyboard_hook = None
    mouse_listener = None

    try:
        open_obs()
        ws = connect_obs(uploader)

        print("Waiting for keyboard or mouse activity to start recording...")

        keyboard_hook = keyboard.hook(on_keyboard_activity)
        mouse_listener = mouse.Listener(on_move=on_mouse_activity, on_click=on_mouse_activity)
        mouse_listener.start()

        while True:
            # If recording is not active and there's activity, start recording
            if not recording_active and waiting_for_activity_to_start and activity_detected:
                print("Activity detected, starting recording.")
                toggle_recording(ws)
                activity_detected = False  # Reset the flag after starting the recording

            # If recording is ongoing and inactivity is detected, stop the recording
            if recording_active and time.time() - last_activity_time > 60:
                print("Inactivity detected, stopping recording.")
                toggle_recording(ws)

            time.sleep(0.1)  # Prevent high CPU usage

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        with ExitStack() as cleanup:
            if uploader is not None:
                cleanup.callback(uploader.close)
            if ws is not None:
                cleanup.callback(ws.disconnect)
            if keyboard_hook is not None:
                cleanup.callback(keyboard.unhook, keyboard_hook)
            if mouse_listener is not None:
                cleanup.callback(mouse_listener.stop)

if __name__ == "__main__":
    if sys.stderr is None:
        log_path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AutoRecord.log")
        handler = RotatingFileHandler(log_path, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
    else:
        handler = logging.StreamHandler()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[handler])
    main()
