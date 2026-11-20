# Activity-Based Recording with OBS 🎥

This project automates the process of starting and stopping an OBS (Open Broadcaster Software) recording based on user activity. It uses the `keyboard` and `pynput` libraries to detect keyboard and mouse activity. When activity is detected, recording starts, and after a specified period of inactivity, the recording stops. This helps to automatically capture only the moments when there is user interaction with the computer.

---

## Features ✨

- **Start Recording on Activity**: Automatically starts recording in OBS when any keyboard or mouse activity is detected. 🖱️⌨️
- **Stop Recording on Inactivity**: Stops the recording after 1 minute of inactivity. ⏳
- **OBS WebSocket Integration**: Communicates with OBS using the `obs-websocket-py` library to control the recording. 🌐
- **Optional Cloudflare R2 Uploads**: Uploads completed recordings in the background while keeping the local files.
- **Background Monitoring**: Continuously monitors keyboard and mouse activity. 🔄
- **OBS Minimization**: Opens OBS minimized to the system tray. 💻

---

## Requirements ⚙️

- **Python 3.x** 🐍
- **OBS Studio** (with the OBS WebSocket plugin installed) 🎥
- **OBS WebSocket** (Port: 4455, Password required) 🔒
- Install the following Python packages:
  - `keyboard`: To detect keyboard activity ⌨️
  - `pynput`: To detect mouse activity 🖱️
  - `obs-websocket-py`: To interact with OBS 🌐
  - `boto3`: To upload recordings to Cloudflare R2

### Install Dependencies 📦

To install the required dependencies, run the following command:

```bash
python -m pip install -r requirements.txt
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

### Optional: Cloudflare R2 uploads

1. Create an R2 bucket and an [R2 API token](https://developers.cloudflare.com/r2/api/tokens/) with **Object Read & Write** access scoped to that bucket. Use its Access Key ID and Secret Access Key, not the Cloudflare dashboard API token itself.
2. Set these environment variables before starting the script. In PowerShell, for the current session:

   ```powershell
   $env:R2_ENDPOINT_URL = "https://<account-id>.r2.cloudflarestorage.com"
   $env:R2_BUCKET_NAME = "<bucket-name>"
   $env:R2_ACCESS_KEY_ID = Read-Host "R2 Access Key ID"
   $secret = Read-Host "R2 Secret Access Key" -AsSecureString
   $env:R2_SECRET_ACCESS_KEY = [System.Net.NetworkCredential]::new("", $secret).Password
   Remove-Variable secret
   ```

   Use the jurisdiction-specific endpoint shown by Cloudflare if your bucket has a jurisdiction. Do not commit credentials or put them in the startup batch file.
3. Run `python .\AutoRec.py` from that same PowerShell session. For startup use, configure the variables in your Windows user environment instead; a new session inherits them. Environment variables can be read by processes running as your user, so keep the account and credentials secure.

All four variables must be set together. If none are set, R2 uploads are disabled and recordings remain local-only; partial configuration stops the script with an error.

When OBS reports that a recording has stopped, each observed file is uploaded under `recordings/<unique-id>/<filename>`. Uploads run in the background, and local files are never deleted. If OBS splits a recording, the observed parts are uploaded after it stops; split-file events require OBS WebSocket 5.5 or later.

The script must be connected to OBS when the recording stops. It does not scan for older recordings or recover uploads after a restart. Failed uploads are reported and the local files remain available for a manual retry. On Ctrl+C, the script waits for queued uploads, but it does not stop an active OBS recording. Stop the recording and wait for it to be queued before exiting.

Upload messages and errors appear in the terminal. When using `pythonw`, they are instead written to `%LOCALAPPDATA%\AutoRecord.log` (with rotation). Check the log or R2 bucket to verify uploads, and keep the bucket private unless you intend to share recordings.

---

## How to Use 🚀

**Run the Script 💻:**
```bash
python AutoRec.py
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
```bat
start "" /B pythonw "C:\path\to\AutoRec.py"
```
- Make sure to change the file path to the location where you saved the AutoRec.py script.

**2. Add to Startup Folder 🔄**
- Copy the batch file you created (AutoRec.bat) and place it in the Startup folder.
- Press WinKey + R, type shell:startup, and press Enter. This will open the Startup folder.
- Paste the batch file into this folder, and it will run automatically every time your computer starts.

---

## Customization ⚙️

- Inactivity Duration ⏰: Change the `time.time() - last_activity_time > 60` condition in `main()` to adjust the threshold.
- OBS Path 🖥️: If your OBS installation is in a different directory, change the path in the open_obs() function.

---

## Troubleshooting ⚠️

- OBS Not Responding: Ensure that the OBS WebSocket plugin is correctly installed and the port/password are configured correctly. 🔒
- Permission Issues: On some systems, you may need to run the script with elevated privileges to detect keyboard or mouse events. ⚡

---

## 📝 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

