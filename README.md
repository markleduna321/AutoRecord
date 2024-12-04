# Activity-Based Recording with OBS 🎥

This project automates the process of starting and stopping an OBS (Open Broadcaster Software) recording based on user activity. It uses the `keyboard` and `pynput` libraries to detect keyboard and mouse activity. When activity is detected, recording starts, and after a specified period of inactivity, the recording stops. This helps to automatically capture only the moments when there is user interaction with the computer.

---

## Features ✨

- **Start Recording on Activity**: Automatically starts recording in OBS when any keyboard or mouse activity is detected. 🖱️⌨️
- **Stop Recording on Inactivity**: Stops the recording after 1 minute of inactivity. ⏳
- **OBS WebSocket Integration**: Communicates with OBS using the `obs-websocket-py` library to control the recording. 🌐
- **Background Monitoring**: Continuously monitors keyboard and mouse activity in the background using separate threads. 🔄
- **OBS Minimization**: Opens OBS minimized to the system tray. 💻

---

## Requirements ⚙️

- **Python 3.x** 🐍
- **OBS Studio** (with the OBS WebSocket plugin installed) 🎥
- **OBS WebSocket** (Port: 4455, Password required) 🔒
- Install the following Python packages:
  - `keyboard`: To detect keyboard activity ⌨️
  - `pynput`: To detect mouse activity 🖱️
  - `obswebsocket`: To interact with OBS 🌐
  - `subprocess`: To open OBS if it's not already running 💻

### Install Dependencies 📦

To install the required dependencies, run the following command:

```bash
pip install keyboard pynput obswebsocket
```

---

## Setup 🛠️
1. OBS WebSocket Plugin 🔌
- Download and install the OBS WebSocket plugin for OBS.
- After installation, configure the WebSocket server in OBS (default port 4455, password required).
2. OBS Path Configuration 🏠
- Update the open_obs() function with the correct path to the OBS executable on your machine (if different).
3. Password Configuration 🔑
- Replace the OBS_PASSWORD variable in the script with your actual OBS WebSocket password.

---

## How to Use 🚀

**Run the Script 💻:**
```bash
python activity_recording.py
```

**OBS Behavior 🎥:**

The script will open OBS (if not already running), and it will minimize to the system tray.
When keyboard or mouse activity is detected, it will start recording.
After 1 minute of inactivity, it will stop the recording.

**Exit the Script ❌:**

To exit the script, press Ctrl+C in the terminal where the script is running.

---

## Running in the Background & Startup ⚡
If you'd like the script to run in the background automatically when you start your computer, follow these steps:

**1. Create a Batch File 📑**
- Create a batch file (e.g., AutoRec.bat) with the following content:
```bash
start /B pythonw C:\IP-Wpage\AutoRec.py
```
- Make sure to change the file path to the location where you saved the AutoRec.py script.

**2. Add to Startup Folder 🔄**
- Copy the batch file you created (AutoRec.bat) and place it in the Startup folder.
- Press WinKey + R, type shell:startup, and press Enter. This will open the Startup folder.
- Paste the batch file into this folder, and it will run automatically every time your computer starts.

---

## Customization ⚙️

- Inactivity Duration ⏰: You can adjust the inactivity threshold (currently set to 1 minute) in the monitor_inactivity() function by changing the if time.time() - last_activity_time > 60 condition.
- OBS Path 🖥️: If your OBS installation is in a different directory, change the path in the open_obs() function.

---

## Troubleshooting ⚠️

- OBS Not Responding: Ensure that the OBS WebSocket plugin is correctly installed and the port/password are configured correctly. 🔒
- Permission Issues: On some systems, you may need to run the script with elevated privileges to detect keyboard or mouse events. ⚡

---

## 📝 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

