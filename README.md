# ⚡ AeroLock // AI Virtual Mouse & Gesture Security System

A futuristic, high-performance Computer Vision system that transforms your laptop webcam into an **AI Virtual Mouse** with an integrated **Hand Gesture Laptop Lock & Unlock System**.

---

## 🌟 Key Features

### 🖱️ 1. Ultra-Low Latency Virtual Mouse
- **Pointing & Cursor Navigation**: Move your cursor smoothly across single or multi-monitor setups by pointing with your index finger.
- **Adaptive Jitter Elimination**: Velocity-responsive exponential smoothing filter eliminates hand tremor while providing instant responsiveness for fast movements.
- **Active Boundary Mapping**: 70% inner camera box maps to 100% of your monitor so you don't have to reach the edges of your webcam.
- **Tactile Click Actions**:
  - **Left Click**: Quick pinch of Index Finger and Thumb.
  - **Drag & Drop**: Sustained pinch (>0.35s) latches the left mouse button until released.
  - **Right Click**: Pinch Middle Finger and Thumb.
  - **Two-Finger Vertical Scrolling**: Extend Index + Middle fingers together and move up/down.
  - **Pause / Typing Mode**: Present an open palm to freeze cursor movement while typing on your physical keyboard.

### 🔒 2. Hand Gesture Laptop Lock & Unlock System
AeroLock introduces a multi-tier security architecture:

1. **Virtual Keyboard & Numeric Sign Passcode Unlock (NEW)**:
   - When locked, configure a **4 to 6 digit password** (e.g. `1234` or `2468`).
   - Enter digits using **two mid-air methods**:
     - **Method A: Holographic Air Keyboard**: Hover your pointing finger over virtual keys `1` to `9` on screen (with 0.65s dwell selection or pinch touch) to type digits.
     - **Method B: Numeric Hand Signs (1 to 9)**: Present clear numeric hand signs directly to the camera (1 = Index finger, 2 = Peace sign, 3 = Three fingers, 4 = Four fingers, 5 = Open palm, 6 = Shaka, 8 = Gun/L-shape, 9 = OK sign).
   - Once all 4–6 digits match, the screen unlocks with a success chime!

2. **AeroShield Holographic Screen Guard**:
   - When the **Lock Gesture** (Closed Fist ✊ held for 1.5s) is recognized, a cyberpunk fullscreen security shield locks your laptop screen.
   - Blocks unauthorized interaction while keeping camera tracking active in the background.
   - **Multi-Step Gesture Passcode**: Present your secret sequence of gestures (e.g., **✌️ Peace/Victory** followed by **👍 Thumbs Up**) to disarm the shield.
   - **Emergency Bypass**: Press `ESC` or enter master passcode.

3. **Native Windows OS Lock Integration**:
   - Calls Windows Win32 API `LockWorkStation()` (equivalent to pressing `Win + L`) to securely lock the Windows operating system session.

### 🌐 3. Real-Time Web Dashboard & Vision HUD
- Accessible at `http://127.0.0.1:5000` from any browser.
- **Live Vision Stream**: Real-time video with hand landmark skeleton, bounding brackets, and cursor reticle.
- **Live Telemetry**: Real-time FPS, detected gesture confidence, active action badges, and lock progression bar.
- **Interactive Calibration Studio**: Live sliders for Cursor Speed, Jitter Smoothing, Pinch Threshold, Scroll Multiplier, and Margin boundaries.
- **Web Audio Sci-Fi Synthesizer**: Realistic futuristic audio feedback on clicks, locks, and unlocks.

---

## 🖐️ Gesture Quick Reference

| Gesture | Pose | Action |
| :--- | :---: | :--- |
| **Move Cursor** | ☝️ Pointing Index | Moves cursor with velocity-adaptive smoothing |
| **Left Click** | 🤏 Index + Thumb Pinch | Single left mouse click |
| **Drag & Drop** | 🤏 Hold Pinch (>0.35s) | Holds left button down while moving |
| **Right Click** | 🤌 Middle + Thumb Pinch | Context menu / right mouse click |
| **Scroll Up/Down** | ✌️ Two Fingers (Index + Middle) | Vertical page scroll |
| **Lock Laptop** | ✊ Closed Fist (Hold 1.5s) | Fills lock bar and triggers Laptop Lock |
| **Step 1 Unlock** | ✌️ Peace / Victory Sign | Initiates Step 1 Biometric Verification |
| **Step 2 Unlock** | 👍 Thumbs Up | Completes Step 2 Verification & Unlocks Laptop |
| **Pause Cursor** | 🖐️ Open Palm facing camera | Freezes cursor movement |

---

## 🚀 Quick Start Guide

### 1. Requirements
- Windows 10 / 11
- Python 3.10+ (Fully compatible with Python 3.14)
- Web camera

### 2. Launching AeroLock
Simply double-click:
```bat
run.bat
```
Or run from terminal:
```bash
python app.py
```

### 3. Command Line Options
```bash
# Run in background with Web Dashboard only (no OpenCV popup window)
python app.py --no-window

# Specify custom camera index or port
python app.py --camera 0 --port 5000
```

### 4. Opening the Web Control Hub
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🛠️ Architecture & Technical Stack

- **Computer Vision & Hand Landmark Tracking**: Google MediaPipe Tasks API (`GestureRecognizer`) with 21 3D hand coordinates.
- **Low-Latency Win32 Automation**: Native Windows `ctypes.windll.user32` (`SetCursorPos`, `mouse_event`, `LockWorkStation`).
- **Screen Lock Guard**: Python Tkinter borderless topmost kiosk overlay.
- **Web Dashboard**: Flask, HTML5, CSS3 Cyberpunk Glassmorphism, Vanilla JS, and Web Audio API synthesizer.

---

## ⚙️ Configuration (`config.json`)

You can customize all behaviors in `config.json` or live through the Web Dashboard:
```json
{
  "camera_id": 0,
  "cursor_speed": 1.25,
  "smoothing": 0.65,
  "active_margin_x": 0.15,
  "active_margin_y": 0.15,
  "pinch_click_threshold": 0.048,
  "middle_click_threshold": 0.050,
  "drag_hold_duration": 0.35,
  "scroll_sensitivity": 25,
  "lock_system_type": "both",
  "lock_hold_duration": 1.5,
  "lock_gesture": "Closed_Fist",
  "unlock_sequence": ["Victory", "Thumb_Up"],
  "unlock_pin": "1234"
}
```

---

## ⌨️ Hotkeys
- `m` : Toggle Virtual Mouse ON / OFF
- `l` : Instantly trigger test Lock
- `u` : Instantly trigger test Unlock
- `ESC` / `q` : Emergency unlock or quit application
