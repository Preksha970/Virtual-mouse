# ⚡ AeroLock // AI Virtual Mouse & Smart User Presence Detection System

A futuristic, high-performance Computer Vision system that transforms your webcam into an **AI Virtual Mouse** with **Smart User Presence Detection**, **Multi-Stage Message Pop-ups**, and **Biometric Screen Lock Security**.

---

## 🌟 Key Features

### 🖱️ 1. Ultra-Low Latency Virtual Mouse
- **Pointing & Cursor Navigation**: Move your cursor smoothly across single or multi-monitor setups by pointing with your index finger.
- **Adaptive Jitter Elimination**: Exponential smoothing filter eliminates hand tremor while providing instant responsiveness.
- **Active Boundary Mapping**: 70% inner camera box maps to 100% of your monitor so you don't have to reach the physical edges of your webcam.
- **Tactile Click Actions**:
  - **Left Click**: Quick pinch of Index Finger and Thumb (< 38px).
  - **Drag & Drop**: Sustained pinch (>0.35s) latches the left mouse button until released.
  - **Right Click**: Pinch Middle Finger and Thumb (< 38px).
  - **Two-Finger Vertical Scrolling**: Extend Index + Middle fingers together and move up/down.
  - **Screen Brightness Control**: Spread Thumb and Pinky finger to dynamically adjust screen brightness (10% to 100%).

---

### 👁️ 2. Smart User Presence Detection & Message Pop-up System
- **Continuous Face Tracking**: Monitors the webcam feed to detect whether the user is seated in front of the screen.
- **Anti-Flicker & Debounce Protection**: Grace period (1.5s) avoids false alarms from brief head turns, sneezing, or momentary occlusion.
- **Zero Privacy Risk**: All video processing runs strictly in-memory. **No images, frames, or audio recordings are ever written to disk or transmitted.**
- **Asynchronous Worker**: Face detection runs in a background thread so the video loop runs at full FPS without freezing cursor movement.
- **Timed Absence Notification Stages**:
  | Absence Duration | Notification Message | Features / Actions |
  | :--- | :--- | :--- |
  | **10 seconds** | *"Hey, are you still there? We can't see you!"* | Modern frameless card, Indigo accent, Close button |
  | **30 seconds** | *"Where did you go? Take your time!"* | In-place card update, Purple accent |
  | **1 minute** | *"Still away? Your virtual mouse is waiting for you!"* | In-place card update, Pink accent |
  | **3 minutes** | *"You've been away for a while. Would you like to lock your screen?"* | Interactive **"🔒 Lock Screen Now"** button + Close |

- **Welcome Back Notification**:
  - When the user's face is re-detected, immediately dismisses the absence notification.
  - Displays a green notification toast:
    > *"Welcome back! Your virtual mouse is ready!"*
  - Automatically fades out / dismisses after 3 seconds.
  - Automatically resumes normal hand gesture tracking.

- **Modern Tkinter Interface**:
  - Dedicated background daemon thread with thread-safe `queue.Queue`.
  - Catppuccin dark card styling with colored accent bars.
  - Draggable cards: click and drag cards anywhere across multiple monitors.
  - Close controls: both an explicit "Close" button and a top-right "✕" quick-close button.
  - Singleton window design: updates in-place without duplicate or stacked windows.
  - Camera disconnect alert if webcam feed drops, with anti-spam cooldown.

---

### 🔒 3. Laptop Lock & Security System
- **Biometric Closed Fist Lock**: Hold a closed fist (✊) for 1.5–1.8s to lock your laptop workstation.
- **Actionable 3-Minute Lock Button**: One-click screen lock directly from the absence popup.
- **Native Windows Lock**: Calls Windows Win32 API `LockWorkStation()` (equivalent to pressing `Win + L`).
- **AeroShield Holographic Screen Guard**: Cyberpunk fullscreen security shield with gesture passcode unlock (Peace sign ✌️ followed by Thumbs Up 👍) or numeric air-keyboard PIN entry.

---

### 🌐 4. Real-Time Web Dashboards & Control Hub
- **Localhost Web Dashboard**: Accessible at `http://localhost:8000` with real-time automatic face presence detection, interactive stage testing buttons, and camera monitoring.
- **AeroLock Telemetry Hub**: Accessible at `http://127.0.0.1:5000` for live gesture stream, calibration studio, and visual HUD.

---

## 🖐️ Gesture Quick Reference

| Gesture | Pose | Action |
| :--- | :---: | :--- |
| **Move Cursor** | ☝️ Pointing Index | Moves cursor with exponential smoothing |
| **Left Click** | 🤏 Index + Thumb Pinch | Single left mouse click |
| **Drag & Drop** | 🤏 Hold Pinch (>0.35s) | Holds left button down while moving |
| **Right Click** | 🤌 Middle + Thumb Pinch | Context menu / right mouse click |
| **Scroll Up/Down** | ✌️ Two Fingers (Index + Middle) | Vertical page scroll |
| **Adjust Brightness** | 🤙 Thumb + Pinky Spread | Adjusts brightness (10% - 100%) |
| **Lock Laptop** | ✊ Closed Fist (Hold 1.5s - 1.8s) | Triggers Windows Laptop Lock |
| **Unlock Step 1** | ✌️ Peace / Victory Sign | Initiates Step 1 Biometric Verification |
| **Unlock Step 2** | 👍 Thumbs Up | Completes Step 2 Verification & Unlocks Laptop |

---

## 📁 Project Structure

```
Virtual-mouse/
│
├── presence_detector.py    # Core presence logic, timers, multi-stage events, anti-flicker & async worker
├── popup_manager.py        # Thread-safe Tkinter modern popup, toast & error system
├── virtual_mouse.py        # Integrated Virtual Mouse with Smart Presence Detection
├── test_presence_demo.py   # Automated simulation script (verifies all stages in ~10s)
├── app.py                  # Full AeroLock master application
├── gesture_engine.py       # Hand landmark processor & gesture classifier
├── mouse_controller.py     # Native Windows mouse input controller
├── screen_shield.py        # Holographic screen lock & passcode interface
├── system_lock.py          # Windows OS lock integration
├── server.py               # Lightweight web server for presence detection (http://localhost:8000)
├── web_server.py           # Web telemetry dashboard (http://127.0.0.1:5000)
├── config.json             # System sensitivity & threshold configuration
├── run.bat                 # One-click Windows launch script
└── README.md               # Complete architecture & usage documentation
```

---

## 🚀 Quick Start Guide

### 1. Requirements
- Windows 10 / 11
- Python 3.10+ (Fully compatible with Python 3.14)
- Webcam (built-in or USB)

### 2. Fast Automated Simulation Test (No Waiting!)
To test all 4 absence tiers, the screen lock trigger, the welcome back toast, and camera disconnect handling:
```bash
python test_presence_demo.py
```

### 3. Launching Virtual Mouse with Presence Detection
```bash
python virtual_mouse.py
```

### 4. Launching the Full AeroLock Suite
```bash
python app.py
```
Or double-click `run.bat`.

### 5. Hotkeys:
- `q` or `ESC`: Quit application
- `l`: Trigger screen lock
- `t`: Simulate 10-second absence alert immediately
- `m`: Toggle virtual mouse ON / OFF
