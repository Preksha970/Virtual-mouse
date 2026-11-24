# Smart User Presence Detection & Message Pop-up System
## Integrated with Virtual Mouse Using Hand Gestures

An intelligent, non-blocking user presence detection and notification system integrated with a **Virtual Mouse Using Hand Gestures** (OpenCV, MediaPipe, Tkinter, PyAutoGUI, ctypes).

---

## 🚀 Key Features

### 1. Smart User Presence Detection
- **Continuous Face Tracking**: Monitors the webcam feed to detect whether the user is seated in front of the screen.
- **Debounce & Anti-Flicker Protection**: Grace period (1.5s) avoids false alarms from brief head turns, sneezing, or momentary occlusion.
- **Asynchronous Non-Blocking Worker**: Runs face detection in a background thread so the main OpenCV video loop runs at full FPS with zero mouse cursor lag or frame drops.
- **Zero Privacy Risk**: All video processing runs strictly in-memory. **No images, frames, or audio recordings are ever written to disk or transmitted.**

### 2. Timed Absence Notification Stages
As the user stays away, the system smoothly updates the notification window:
| Absence Duration | Notification Message | Features / Actions |
| :--- | :--- | :--- |
| **10 seconds** | *"Hey, are you still there? We can't see you!"* | Modern frameless card, Indigo accent, Close button |
| **30 seconds** | *"Where did you go? Take your time!"* | In-place card update, Purple accent |
| **1 minute** | *"Still away? Your virtual mouse is waiting for you!"* | In-place card update, Pink accent |
| **3 minutes** | *"You've been away for a while. Would you like to lock your screen?"* | Interactive **"🔒 Lock Screen Now"** button + Close |

### 3. Welcome Back & Gesture Resumption
- When the user's face is re-detected:
  - Immediately **dismisses** any active absence popup.
  - Displays a stylish green notification toast:
    > *"Welcome back! Your virtual mouse is ready!"*
  - Automatically fades out / dismisses after 3 seconds.
  - Normal hand gesture tracking resumes seamlessly.

### 4. Modern Tkinter Interface & Non-Blocking Architecture
- **Non-blocking Architecture**: Runs Tkinter in a dedicated background daemon thread with thread-safe `queue.Queue` communication. This ensures **zero lag or stutter** in OpenCV webcam rendering or mouse cursor movement.
- **Dark-Themed Frameless UI**: Styled with modern Catppuccin dark palettes, accent indicator bars, and native screen centering.
- **Draggable Cards**: Users can click and drag the frameless notification cards anywhere across multiple monitors.
- **Close Buttons**: Every popup features both a dedicated "Close" button and a top-right "✕" quick-close button.
- **Singleton Window Lifecycle**: Never opens annoying duplicate or stacked windows; updates the existing window in-place.
- **Webcam Disconnect Alert**: Immediately notifies if the camera feed drops or fails to deliver frames, with anti-flood cooldown protection.

### 5. Full Virtual Mouse Capabilities
- **Cursor Navigation**: Index fingertip tracking with exponential smoothing to eliminate hand jitter.
- **Left Click**: Pinch between Index finger and Thumb (< 38px).
- **Right Click**: Pinch between Middle finger and Thumb (< 38px).
- **Scrolling**: Index and Middle fingers held together (move up to scroll up, down to scroll down).
- **Brightness Control**: Distance between Thumb and Pinky finger controls screen brightness (10% - 100%).
- **Biometric / Fist Screen Lock**: Hold a closed fist for 1.8 seconds (or click the popup's Lock Screen button) to lock Windows workstation via native `ctypes.windll.user32.LockWorkStation()`.

---

## 📁 Project Structure

```
MESSAGEMINI/
│
├── presence_detector.py    # Core presence logic, timers, multi-stage events, anti-flicker & async worker
├── popup_manager.py        # Thread-safe Tkinter modern popup, toast & error system
├── virtual_mouse.py        # Complete integrated Virtual Mouse application
├── test_presence_demo.py   # Automated simulation script (verifies all stages in ~10s)
├── server.py               # Optional interactive web-based test dashboard (localhost:8000)
└── README.md               # Architecture documentation & integration guide
```

---

## 🛠️ Step-by-Step Integration into an Existing Virtual Mouse Codebase

If you already have an existing `main.py` or `virtual_mouse.py` file, follow these 4 simple steps to integrate this feature:

### Step 1: Place Modules
Place `presence_detector.py` and `popup_manager.py` into your project directory.

### Step 2: Add Imports
At the top of your existing virtual mouse file:
```python
from presence_detector import PresenceDetector
from popup_manager import PopupManager
```

### Step 3: Initialize Before Main Loop
Right before starting your camera capture loop:
```python
# Initialize Presence Detector (async_mode=True ensures zero video lag) and Popup Manager
presence_detector = PresenceDetector(debounce_sec=1.5, cooldown_sec=5.0, async_mode=True)
popup_manager = PopupManager()
```

### Step 4: Add Detection & Popup Logic Inside the `while cap.isOpened():` Loop
Inside your frame processing loop:
```python
while cap.isOpened():
    ret, frame = cap.read()
    if not ret or frame is None:
        popup_manager.show_camera_error("Webcam feed disconnected or unavailable!", cooldown_sec=10.0)
        continue

    # 1. Update Presence Detection
    is_user_present, face_bbox, event = presence_detector.update(frame)

    if event:
        if event["type"] == "away":
            # Trigger multi-stage popup (10s, 30s, 60s, 180s)
            popup_manager.show_absence_popup(
                stage=event["stage"],
                message=event["message"],
                show_lock_option=event["show_lock_option"]
            )
        elif event["type"] == "welcome":
            # Trigger Welcome Back toast & auto-dismiss absence popup
            popup_manager.show_welcome_back(
                message=event["message"],
                duration=event["duration"]
            )

    # 2. Existing Hand Gesture Recognition (Only process when user is present!)
    if is_user_present:
        # --> YOUR EXISTING HAND GESTURE TRACKING & MOUSE CODE RUNS HERE <--
        pass
    else:
        # Visual indicator when user is away
        cv2.putText(frame, "User Away - Paused", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.imshow("Virtual Mouse", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up on exit
presence_detector.stop()
popup_manager.close_all()
cap.release()
cv2.destroyAllWindows()
```

---

## ⚡ Quick Testing & Verification

### Automated Fast Simulation (No Waiting!)
To verify all notifications and window transitions without waiting for minutes, run the automated simulation:
```bash
python test_presence_demo.py
```
This runs an accelerated test through all 4 absence tiers (10s, 30s, 60s, 180s with screen lock button), triggers the welcome back toast, and tests the camera disconnect notification.

### Full Application
To run the complete integrated application with webcam:
```bash
python virtual_mouse.py
```

### Hotkeys in Virtual Mouse:
- `q`: Quit the application
- `l`: Lock screen immediately
- `t`: Simulate 10-second absence trigger instantly
