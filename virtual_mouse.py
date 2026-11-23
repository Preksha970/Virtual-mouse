"""
Virtual Mouse Using Hand Gestures with Smart User Presence Detection
====================================================================
Complete integrated application combining:
1. Virtual Mouse Hand Gesture Tracking:
   - Cursor movement (Index finger pointing with smoothing)
   - Left click (Index-Thumb pinch)
   - Right click (Middle-Thumb pinch)
   - Vertical Scrolling (Two-finger gesture)
   - Screen Brightness Control (Thumb-Pinky spread gesture)
   - Biometric / Fist Screen Lock (Windows LockWorkStation)
2. Smart User Presence Detection & Message Pop-up System:
   - 10s:  "Hey, are you still there? We can't see you!"
   - 30s:  "Where did you go? Take your time!"
   - 1m:   "Still away? Your virtual mouse is waiting for you!"
   - 3m:   "You've been away for a while. Would you like to lock your screen?" (Actionable button)
   - Welcome Back toast: "Welcome back! Your virtual mouse is ready!"
   - Automatic dismissal of absence popup on return
   - Camera disconnect notification
   - Anti-flicker debounce filter
   - Non-blocking threaded Tkinter interface
"""

import os
import sys
import time
import math
import ctypes
import cv2
import numpy as np

# Import our custom modules
from presence_detector import PresenceDetector
from popup_manager import PopupManager

# Optional PyAutoGUI with ctypes fallback
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False

# Optional MediaPipe Hands
try:
    import mediapipe as mp
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
        HAS_MP_HANDS = True
    else:
        HAS_MP_HANDS = False
except Exception:
    HAS_MP_HANDS = False

# Optional Screen Brightness Control
try:
    import screen_brightness_control as sbc
    HAS_SBC = True
except Exception:
    HAS_SBC = False


# ==============================================================================
# Native Windows Mouse & System Controller (Zero-Dependency Fallback)
# ==============================================================================

class SystemController:
    """Controls mouse cursor, clicks, scrolls, screen lock, and brightness."""

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.screen_w = self.user32.GetSystemMetrics(0)
        self.screen_h = self.user32.GetSystemMetrics(1)
        self.last_brightness_time = 0.0

    def move_cursor(self, x: int, y: int):
        """Moves cursor to absolute screen coordinates."""
        clamped_x = max(0, min(self.screen_w - 1, int(x)))
        clamped_y = max(0, min(self.screen_h - 1, int(y)))
        if HAS_PYAUTOGUI:
            pyautogui.moveTo(clamped_x, clamped_y)
        else:
            self.user32.SetCursorPos(clamped_x, clamped_y)

    def left_click(self):
        """Simulates left mouse click."""
        if HAS_PYAUTOGUI:
            pyautogui.click()
        else:
            self.user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            time.sleep(0.02)
            self.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP

    def right_click(self):
        """Simulates right mouse click."""
        if HAS_PYAUTOGUI:
            pyautogui.rightClick()
        else:
            self.user32.mouse_event(0x0008, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTDOWN
            time.sleep(0.02)
            self.user32.mouse_event(0x0010, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP

    def scroll(self, amount: int):
        """Scrolls vertically (positive=up, negative=down)."""
        if HAS_PYAUTOGUI:
            pyautogui.scroll(amount)
        else:
            # 120 units per notch in Windows wheel delta
            self.user32.mouse_event(0x0800, 0, 0, int(amount * 120), 0)

    def lock_screen(self):
        """Locks the Windows workstation."""
        try:
            self.user32.LockWorkStation()
        except Exception:
            try:
                os.system("rundll32.exe user32.dll,LockWorkStation")
            except Exception:
                pass

    def set_brightness(self, level_percent: int):
        """Sets screen brightness (0-100%). Throttled to prevent lag."""
        now = time.time()
        if now - self.last_brightness_time < 0.2:
            return
        self.last_brightness_time = now

        level = max(10, min(100, int(level_percent)))
        if HAS_SBC:
            try:
                sbc.set_brightness(level)
                return
            except Exception:
                pass
        # Fallback via PowerShell WMI
        try:
            cmd = f'powershell -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"'
            os.system(cmd)
        except Exception:
            pass


# ==============================================================================
# Hand Tracking & Gesture Processor
# ==============================================================================

class HandGestureTracker:
    """
    Detects hand landmarks and translates gestures into virtual mouse commands.
    """

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Smoothing & cooldown variables
        self.prev_x, self.prev_y = 0.0, 0.0
        self.smooth_factor = 0.5  # Exponential smoothing
        self.last_left_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_scroll_time = 0.0
        self.fist_start_time = None

        if HAS_MP_HANDS:
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.6
            )
            self.mp_draw = mp.solutions.drawing_utils
            self.backend = "mediapipe"
        else:
            self.hands = None
            self.backend = "fallback"

    def process_frame(self, frame_bgr, system_ctrl: SystemController):
        """
        Processes frame for gestures and performs corresponding mouse actions.
        :return: (status_text: str, hand_detected: bool)
        """
        h, w = frame_bgr.shape[:2]
        status = "SEARCHING"
        hand_detected = False

        if self.backend == "mediapipe" and self.hands:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb)

            if results and results.multi_hand_landmarks:
                hand_detected = True
                hand_landmarks = results.multi_hand_landmarks[0]
                self.mp_draw.draw_landmarks(frame_bgr, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)

                # Landmark Coordinates
                landmarks = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks.landmark]
                thumb_tip = landmarks[4]
                index_tip = landmarks[8]
                index_pip = landmarks[6]
                middle_tip = landmarks[12]
                middle_pip = landmarks[10]
                ring_tip = landmarks[16]
                pinky_tip = landmarks[20]

                # Finger extended states
                index_up = index_tip[1] < index_pip[1]
                middle_up = middle_tip[1] < middle_pip[1]
                ring_up = ring_tip[1] < landmarks[14][1]
                pinky_up = pinky_tip[1] < landmarks[18][1]

                # Euclidean distances
                dist_index_thumb = math.hypot(index_tip[0] - thumb_tip[0], index_tip[1] - thumb_tip[1])
                dist_middle_thumb = math.hypot(middle_tip[0] - thumb_tip[0], middle_tip[1] - thumb_tip[1])
                dist_thumb_pinky = math.hypot(thumb_tip[0] - pinky_tip[0], thumb_tip[1] - pinky_tip[1])

                now = time.time()

                # GESTURE 1: FIST (Lock Screen)
                if not index_up and not middle_up and not ring_up and not pinky_up:
                    if self.fist_start_time is None:
                        self.fist_start_time = now
                    elif now - self.fist_start_time > 1.8:  # Hold fist for 1.8s
                        status = "LOCK SCREEN"
                        system_ctrl.lock_screen()
                        self.fist_start_time = None
                    else:
                        remaining = round(1.8 - (now - self.fist_start_time), 1)
                        status = f"HOLD FIST TO LOCK ({remaining}s)"
                    return status, hand_detected
                else:
                    self.fist_start_time = None

                # GESTURE 2: SCROLLING (Index + Middle extended together)
                if index_up and middle_up and not ring_up:
                    status = "SCROLL MODE"
                    if now - self.last_scroll_time > 0.15:
                        # Map vertical position to scroll direction
                        if middle_tip[1] < h * 0.35:
                            system_ctrl.scroll(2)  # Scroll Up
                            status = "SCROLL UP"
                        elif middle_tip[1] > h * 0.65:
                            system_ctrl.scroll(-2)  # Scroll Down
                            status = "SCROLL DOWN"
                        self.last_scroll_time = now
                    return status, hand_detected

                # GESTURE 3: BRIGHTNESS CONTROL (Thumb + Pinky spread wide, other fingers down)
                if pinky_up and not index_up and not middle_up:
                    # Map distance 40px - 220px to 10% - 100% brightness
                    pct = int(np.interp(dist_thumb_pinky, [40, 220], [10, 100]))
                    status = f"BRIGHTNESS: {pct}%"
                    system_ctrl.set_brightness(pct)
                    return status, hand_detected

                # GESTURE 4: CURSOR MOVEMENT & CLICKS
                if index_up:
                    # Frame padding margin to reach screen edges easily
                    pad_x, pad_y = int(w * 0.18), int(h * 0.18)
                    mapped_x = np.interp(index_tip[0], [pad_x, w - pad_x], [0, self.screen_w])
                    mapped_y = np.interp(index_tip[1], [pad_y, h - pad_y], [0, self.screen_h])

                    # Exponential smoothing to prevent jitter
                    curr_x = self.prev_x + (mapped_x - self.prev_x) * self.smooth_factor
                    curr_y = self.prev_y + (mapped_y - self.prev_y) * self.smooth_factor
                    self.prev_x, self.prev_y = curr_x, curr_y

                    system_ctrl.move_cursor(curr_x, curr_y)
                    status = "CURSOR MOVE"

                    # LEFT CLICK (Index-Thumb pinch < 38px)
                    if dist_index_thumb < 38 and (now - self.last_left_click_time > 0.4):
                        system_ctrl.left_click()
                        self.last_left_click_time = now
                        status = "LEFT CLICK"

                    # RIGHT CLICK (Middle-Thumb pinch < 38px)
                    elif dist_middle_thumb < 38 and (now - self.last_right_click_time > 0.4):
                        system_ctrl.right_click()
                        self.last_right_click_time = now
                        status = "RIGHT CLICK"

        return status, hand_detected


# ==============================================================================
# Main Integrated Virtual Mouse Application
# ==============================================================================

class VirtualMouseApp:
    """
    Main Application orchestrating Webcam Feed, Hand Tracking,
    and Smart User Presence Detection & Message Pop-ups.
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.system_ctrl = SystemController()
        self.hand_tracker = HandGestureTracker(self.system_ctrl.screen_w, self.system_ctrl.screen_h)

        # Smart Presence Detection & Tkinter Pop-up System
        self.presence_detector = PresenceDetector(debounce_sec=1.5)
        self.popup_manager = PopupManager()

        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.last_face_bbox = None
        self.is_user_present = True

    def start(self):
        """Starts the webcam capture and main processing loop."""
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"[ERROR] Could not open webcam at index {self.camera_index}")
            self.popup_manager.show_camera_error("Unable to open webcam. Please verify your camera is connected.")
            time.sleep(3.0)
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.is_running = True

        print("[INFO] Virtual Mouse & Smart Presence Detection started successfully.")
        print("[INFO] Controls:")
        print("       - Move Index Finger: Move cursor")
        print("       - Pinch Index + Thumb: Left click")
        print("       - Pinch Middle + Thumb: Right click")
        print("       - Index + Middle Together: Scroll Up / Down")
        print("       - Spread Thumb + Pinky: Adjust Brightness")
        print("       - Hold Closed Fist (1.8s): Lock Screen")
        print("       - Press 'q' on video window: Quit")
        print("       - Press 't': Simulate 12s Away (for quick popup test)")

        prev_time = time.time()

        try:
            while self.is_running and self.cap.isOpened():
                ret, frame = self.cap.read()

                # Feature 5: Camera Disconnect Notification
                if not ret or frame is None:
                    print("[WARNING] Webcam feed disconnected or failed to read frame.")
                    self.popup_manager.show_camera_error("Webcam feed was disconnected or lost!")
                    time.sleep(1.0)
                    continue

                # Mirror frame horizontally for natural intuitive interaction
                frame = cv2.flip(frame, 1)
                self.frame_count += 1
                curr_time = time.time()
                fps = 1.0 / max(0.001, curr_time - prev_time)
                prev_time = curr_time

                # --------------------------------------------------------------
                # 1. Smart User Presence Detection
                # --------------------------------------------------------------
                # Runs face detection (every frame or every 2 frames for performance)
                if self.frame_count % 2 == 0 or self.last_face_bbox is None:
                    self.is_user_present, self.last_face_bbox, event = self.presence_detector.update(frame, curr_time)

                    # Handle presence events
                    if event:
                        if event["type"] == "away":
                            # Feature 2 & 4: Multi-stage absence popups
                            print(f"[PRESENCE] User away for {event['seconds']}s -> Triggering Popup: {event['message']}")
                            self.popup_manager.show_absence_popup(
                                stage=event["stage"],
                                message=event["message"],
                                show_lock_option=event["show_lock_option"]
                            )
                        elif event["type"] == "welcome":
                            # Feature 3: Welcome back notification & auto-dismiss
                            print(f"[PRESENCE] User returned -> {event['message']}")
                            self.popup_manager.show_welcome_back(
                                message=event["message"],
                                duration=event["duration"]
                            )

                # --------------------------------------------------------------
                # 2. Hand Gesture Recognition & Virtual Mouse Control
                # --------------------------------------------------------------
                gesture_status = "USER AWAY"
                hand_found = False

                # Only track gestures if user is present in front of the camera
                if self.is_user_present:
                    gesture_status, hand_found = self.hand_tracker.process_frame(frame, self.system_ctrl)
                else:
                    # User is away: gesture recognition pauses gracefully
                    away_sec = int(self.presence_detector.away_duration)
                    gesture_status = f"AWAY ({away_sec}s)"

                # --------------------------------------------------------------
                # 3. OpenCV Heads-Up Display (HUD) Rendering
                # --------------------------------------------------------------
                self._draw_hud(frame, fps, gesture_status, hand_found)

                # Display the processed frame
                cv2.imshow("Smart Virtual Mouse with User Presence Detection", frame)

                # Key handling
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("[INFO] Quitting application...")
                    break
                elif key == ord('l'):
                    print("[INFO] Manual screen lock triggered.")
                    self.system_ctrl.lock_screen()
                elif key == ord('t'):
                    # Test mode: simulate away duration
                    print("[TEST] Simulating 10s absence trigger...")
                    self.presence_detector.last_face_seen_time = time.time() - 11.0

        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user.")
        finally:
            self.stop()

    def _draw_hud(self, frame, fps: float, gesture_status: str, hand_found: bool):
        """Renders a sleek HUD showing presence, gesture mode, and FPS."""
        h, w = frame.shape[:2]

        # Draw face bounding box if present
        if self.is_user_present and self.last_face_bbox:
            fx, fy, fw, fh = self.last_face_bbox
            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 128), 2)
            cv2.putText(frame, "User Present", (fx, max(20, fy - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 128), 2)

        # Semi-transparent top dashboard banner
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 54), (24, 24, 37), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Presence Indicator
        if self.is_user_present:
            p_color = (0, 230, 118)  # Bright green
            p_text = "PRESENCE: ACTIVE"
        else:
            p_color = (70, 70, 240)   # Coral red
            p_text = f"PRESENCE: AWAY ({int(self.presence_detector.away_duration)}s)"
        cv2.circle(frame, (18, 27), 7, p_color, -1)
        cv2.putText(frame, p_text, (32, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Gesture Status
        g_color = (255, 200, 0) if hand_found else (180, 180, 180)
        cv2.putText(frame, f"MODE: {gesture_status}", (280, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.55, g_color, 2)

        # FPS counter
        cv2.putText(frame, f"FPS: {int(fps)}", (w - 100, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

    def stop(self):
        """Releases resources cleanly."""
        self.is_running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
        self.popup_manager.close_all()
        print("[INFO] Clean shutdown complete.")


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    app = VirtualMouseApp(camera_index=0)
    app.start()
