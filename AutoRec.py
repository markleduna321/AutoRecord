import keyboard
from pynput import mouse
from obswebsocket import obsws, requests
import subprocess
import time
import threading

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
def connect_obs():
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
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

# Function to monitor inactivity and stop recording
def monitor_inactivity(ws):
    global last_activity_time, recording_active, waiting_for_activity_to_start, activity_detected
    while True:
        time.sleep(1)  # Check every second
        if time.time() - last_activity_time > 60:  # 1 minute of inactivity
            if recording_active:
                print("Inactivity detected. Stopping recording.")
                toggle_recording(ws)
            else:
                waiting_for_activity_to_start = True  # Ensure we're waiting for activity after stopping
            last_activity_time = time.time()  # Reset the timer after checking

# Main function to start OBS and handle activity detection
def main():
    global recording_active, last_activity_time, waiting_for_activity_to_start, activity_detected

    open_obs()
    ws = connect_obs()

    # Start recording when activity is first detected
    print("Waiting for keyboard or mouse activity to start recording...")

    # Start the inactivity monitoring in a separate thread
    inactivity_thread = threading.Thread(target=monitor_inactivity, args=(ws,))
    inactivity_thread.daemon = True
    inactivity_thread.start()

    # Set up listeners for keyboard and mouse activity
    keyboard.hook(on_keyboard_activity)
    mouse_listener = mouse.Listener(on_move=on_mouse_activity, on_click=on_mouse_activity)
    mouse_listener.start()

    try:
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
        ws.disconnect()

if __name__ == "__main__":
    main()
