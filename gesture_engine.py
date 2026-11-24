"""
Advanced Gesture Recognition Engine powered by MediaPipe Tasks API.
Processes hand landmarks in real-time, filters jitter, and detects mouse actions,
screen lock gestures, 4-6 digit passwords, virtual keyboard input, and numeric signs 1 to 9.
"""

import math
import time
import os
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class GestureEngine:
    # Landmark indices
    WRIST = 0
    THUMB_TIP = 4
    THUMB_IP = 3
    THUMB_MCP = 2
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20

    # Hand connections for drawing skeleton
    CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),        # Index
        (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
        (9, 13), (13, 14), (14, 15), (15, 16), # Ring
        (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
        (0, 17)                                # Palm base
    ]

    def __init__(self, model_path="gesture_recognizer.task", config=None):
        self.config = config or {}
        self.model_path = model_path
        
        if not os.path.isabs(self.model_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.model_path = os.path.join(base_dir, model_path)
            
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)
        
        # Configuration parameters
        self.pinch_click_threshold = self.config.get("pinch_click_threshold", 0.048)
        self.middle_click_threshold = self.config.get("middle_click_threshold", 0.050)
        self.drag_hold_duration = self.config.get("drag_hold_duration", 0.35)
        self.lock_hold_duration = self.config.get("lock_hold_duration", 1.5)
        self.lock_gesture_name = self.config.get("lock_gesture", "Closed_Fist")
        self.unlock_sequence = self.config.get("unlock_sequence", ["Victory", "Thumb_Up"])
        self.unlock_pin = str(self.config.get("unlock_pin", "1234"))
        
        # State tracking
        self.is_locked = False
        self.lock_start_time = None
        self.lock_progress = 0.0
        
        # Fast & Responsive Unlock State (0.35s hold instead of 0.8s)
        self.unlock_step = 0
        self.unlock_step_start_time = None
        self.unlock_hold_start = None
        self.unlock_hold_required = 0.35  # Fast 0.35s unlock response
        self.last_matched_time = 0

        # Virtual Keyboard & 4-6 Digit Password State
        self.entered_pin_digits = ""
        self.last_key_press_time = 0
        self.active_hover_key = None
        self.hover_start_time = None
        self.hover_dwell_duration = 0.35  # Snappy 0.35s hover dwell
        self.pin_error_reset_time = None
        
        # Numeric Hand Sign Recognition (1 to 9)
        self.current_sign_digit = None
        self.sign_hold_start = None
        self.sign_hold_duration = 0.35  # Snappy 0.35s sign confirmation
        self.last_sign_detect_time = 0
        
        # Click / Drag state
        self.pinch_start_time = None
        self.is_pinching = False
        self.is_dragging = False
        
        # Scroll tracking
        self.prev_scroll_y = None
        
        # FPS calculation
        self.prev_frame_time = time.time()
        self.fps = 0.0

    def update_config(self, new_config):
        self.config.update(new_config)
        self.pinch_click_threshold = self.config.get("pinch_click_threshold", self.pinch_click_threshold)
        self.middle_click_threshold = self.config.get("middle_click_threshold", self.middle_click_threshold)
        self.drag_hold_duration = self.config.get("drag_hold_duration", self.drag_hold_duration)
        self.lock_hold_duration = self.config.get("lock_hold_duration", self.lock_hold_duration)
        self.lock_gesture_name = self.config.get("lock_gesture", self.lock_gesture_name)
        self.unlock_sequence = self.config.get("unlock_sequence", self.unlock_sequence)
        self.unlock_pin = str(self.config.get("unlock_pin", self.unlock_pin))

    @staticmethod
    def dist(pt1, pt2):
        return math.hypot(pt1.x - pt2.x, pt1.y - pt2.y)

    def detect_digit_sign(self, landmarks):
        """
        Analyzes hand landmarks and recognizes numeric hand signs for digits 1 through 9.
        Returns digit string ('1'-'9') or None.
        """
        if not landmarks:
            return None

        # Finger extension states
        index_up = landmarks[self.INDEX_TIP].y < landmarks[self.INDEX_PIP].y
        middle_up = landmarks[self.MIDDLE_TIP].y < landmarks[self.MIDDLE_PIP].y
        ring_up = landmarks[self.RING_TIP].y < landmarks[self.RING_PIP].y
        pinky_up = landmarks[self.PINKY_TIP].y < landmarks[self.PINKY_PIP].y

        # Thumb extension outwards
        d_tip_pinky = self.dist(landmarks[self.THUMB_TIP], landmarks[self.PINKY_MCP])
        d_ip_pinky = self.dist(landmarks[self.THUMB_IP], landmarks[self.PINKY_MCP])
        thumb_open = d_tip_pinky > (d_ip_pinky * 1.15)

        # OK sign circle (Index tip touching Thumb tip)
        d_index_thumb = self.dist(landmarks[self.THUMB_TIP], landmarks[self.INDEX_TIP])
        index_thumb_touching = d_index_thumb < 0.065

        count_up = sum([index_up, middle_up, ring_up, pinky_up])

        # Digit 9: "OK" Sign (Index tip touches thumb tip, at least 2 fingers up)
        if index_thumb_touching and (middle_up or ring_up or pinky_up):
            return "9"

        # Digit 5: All 5 fingers extended (Open palm)
        if count_up == 4 and thumb_open:
            return "5"

        # Digit 4: 4 fingers extended upright
        if count_up == 4:
            return "4"

        # Digit 3: 3 fingers extended
        if count_up == 3:
            return "3"

        # Digit 2: 2 fingers extended (Peace / V)
        if count_up == 2 and index_up and middle_up:
            return "2"

        # Digit 1: Only Index finger up
        if count_up == 1 and index_up:
            return "1"

        # Digit 8: L / Gun Shape (Thumb + Index extended at 90 deg, other 3 curled)
        if thumb_open and index_up and not middle_up and not ring_up and not pinky_up:
            return "8"

        # Digit 6: "Shaka" / "Call Me" (Thumb + Pinky extended, middle 3 curled)
        if thumb_open and pinky_up and not index_up and not middle_up and not ring_up:
            return "6"

        # Digit 7: Thumb + Index + Pinky extended ("Rock / I Love You")
        if thumb_open and index_up and pinky_up and not middle_up and not ring_up:
            return "7"

        return None

    def _press_virtual_key(self, key_label):
        """Handles virtual keypad input and verifies 4-6 digit password."""
        now = time.time()
        # Debounce: if same key, debounce 0.35s; if different key, minimal debounce
        if getattr(self, "last_pressed_key", None) == key_label:
            if now - self.last_key_press_time < 0.35:
                return
        elif now - self.last_key_press_time < 0.02:
            return

        self.last_pressed_key = key_label
        self.last_key_press_time = now

        if key_label == "CLR":
            self.entered_pin_digits = ""
        elif key_label == "DEL":
            self.entered_pin_digits = self.entered_pin_digits[:-1]
        elif key_label.isdigit():
            if len(self.entered_pin_digits) < max(6, len(self.unlock_pin)):
                self.entered_pin_digits += key_label

    def process_frame(self, bgr_frame):
        """
        Processes one video frame and returns extracted gestures, landmarks, and actions.
        """
        now = time.time()
        self.fps = 0.85 * self.fps + 0.15 * (1.0 / max(0.001, (now - self.prev_frame_time)))
        self.prev_frame_time = now

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        result = self.recognizer.recognize(mp_image)
        
        data = {
            "hand_detected": False,
            "gesture": "None",
            "gesture_confidence": 0.0,
            "action": "IDLE",
            "pointer_x": 0.5,
            "pointer_y": 0.5,
            "click_event": None,
            "scroll_delta": 0,
            "lock_triggered": False,
            "unlock_triggered": False,
            "lock_progress": 0.0,
            "unlock_step": self.unlock_step,
            "unlock_target": self.unlock_sequence[self.unlock_step] if self.unlock_step < len(self.unlock_sequence) else None,
            "landmarks": None,
            "handedness": "Right",
            "detected_digit_sign": None,
            "sign_hold_progress": 0.0,
            "entered_pin": self.entered_pin_digits,
            "target_pin_len": len(self.unlock_pin),
            "active_hover_key": self.active_hover_key,
            "key_dwell_progress": 0.0
        }

        # If locked, check if complete passcode has already been satisfied
        if self.is_locked and len(self.entered_pin_digits) == len(self.unlock_pin):
            if self.entered_pin_digits == self.unlock_pin:
                self.is_locked = False
                data["unlock_triggered"] = True
                data["action"] = "PASSWORD UNLOCKED! ✓"
                self.entered_pin_digits = ""
                return data

        if not result.hand_landmarks:
            self._handle_no_hand(data)
            return data

        landmarks = result.hand_landmarks[0]
        data["hand_detected"] = True
        data["landmarks"] = landmarks

        # Extract gesture from recognizer
        if result.gestures and len(result.gestures[0]) > 0:
            top_gesture = result.gestures[0][0]
            data["gesture"] = top_gesture.category_name
            data["gesture_confidence"] = top_gesture.score

        if result.handedness and len(result.handedness[0]) > 0:
            data["handedness"] = result.handedness[0][0].category_name

        # Calculate finger extension states
        index_up = landmarks[self.INDEX_TIP].y < landmarks[self.INDEX_PIP].y
        middle_up = landmarks[self.MIDDLE_TIP].y < landmarks[self.MIDDLE_PIP].y
        ring_up = landmarks[self.RING_TIP].y < landmarks[self.RING_PIP].y
        pinky_up = landmarks[self.PINKY_TIP].y < landmarks[self.PINKY_PIP].y
        
        thumb_tip = landmarks[self.THUMB_TIP]
        index_tip = landmarks[self.INDEX_TIP]
        middle_tip = landmarks[self.MIDDLE_TIP]
        
        # Distances
        index_thumb_dist = self.dist(thumb_tip, index_tip)
        middle_thumb_dist = self.dist(thumb_tip, middle_tip)
        index_middle_dist = self.dist(index_tip, middle_tip)

        # Pointer coordinates (frame is already flipped with cv2.flip)
        pointer_x = index_tip.x
        pointer_y = index_tip.y
        data["pointer_x"] = pointer_x
        data["pointer_y"] = pointer_y

        # ==========================================
        # 1. LOCK / UNLOCK SECURITY STATE MACHINE
        # ==========================================
        if self.is_locked:
            data["action"] = "LOCKED"
            self._evaluate_unlock(data, now, pointer_x, pointer_y, index_thumb_dist)
            data["entered_pin"] = self.entered_pin_digits
            data["active_hover_key"] = self.active_hover_key
            return data

        # Check for Lock gesture (Closed Fist held for duration)
        is_lock_pose = (data["gesture"] == self.lock_gesture_name) or (not index_up and not middle_up and not ring_up and not pinky_up)
        
        if is_lock_pose:
            if self.lock_start_time is None:
                self.lock_start_time = now
            elapsed = now - self.lock_start_time
            self.lock_progress = min(1.0, elapsed / self.lock_hold_duration)
            data["lock_progress"] = self.lock_progress
            data["action"] = f"LOCKING ({int(self.lock_progress * 100)}%)"
            
            if self.lock_progress >= 1.0:
                self.is_locked = True
                data["lock_triggered"] = True
                self.lock_start_time = None
                self.lock_progress = 0.0
                self.unlock_step = 0
                self.unlock_step_start_time = None
                self.entered_pin_digits = ""
            return data
        else:
            self.lock_start_time = None
            self.lock_progress = 0.0

        # ==========================================
        # 2. VIRTUAL MOUSE GESTURES (When Unlocked)
        # ==========================================
        # SCROLL GESTURE
        if index_up and middle_up and not ring_up and not pinky_up and index_middle_dist < 0.075:
            data["action"] = "SCROLLING"
            avg_y = (index_tip.y + middle_tip.y) / 2.0
            if self.prev_scroll_y is not None:
                dy = avg_y - self.prev_scroll_y
                if abs(dy) > 0.005:
                    data["scroll_delta"] = -dy * 150.0
            self.prev_scroll_y = avg_y
            self._reset_pinch()
            return data
        else:
            self.prev_scroll_y = None

        # RIGHT CLICK
        if middle_thumb_dist < self.middle_click_threshold and not index_up:
            data["action"] = "RIGHT CLICK"
            data["click_event"] = "right_click"
            self._reset_pinch()
            return data

        # LEFT CLICK / DRAG
        if index_thumb_dist < self.pinch_click_threshold:
            if not self.is_pinching:
                self.is_pinching = True
                self.pinch_start_time = now
                
            pinch_duration = now - self.pinch_start_time
            if pinch_duration >= self.drag_hold_duration:
                self.is_dragging = True
                data["action"] = "DRAGGING"
                data["click_event"] = "left_down"
            else:
                data["action"] = "PINCHING"
        else:
            if self.is_pinching:
                pinch_duration = now - self.pinch_start_time
                if self.is_dragging:
                    data["click_event"] = "left_up"
                    data["action"] = "RELEASED"
                elif pinch_duration < self.drag_hold_duration:
                    data["click_event"] = "left_click"
                    data["action"] = "LEFT CLICK"
                self._reset_pinch()
            else:
                if index_up or data.get("gesture") == "Pointing_Up":
                    data["action"] = "POINTER"
                elif data.get("gesture") == "Open_Palm":
                    data["action"] = "IDLE (PALM)"
                else:
                    data["action"] = "POINTER"

        return data

    def _reset_pinch(self):
        self.is_pinching = False
        self.is_dragging = False
        self.pinch_start_time = None

    def _handle_no_hand(self, data):
        self.lock_start_time = None
        self.lock_progress = 0.0
        self.prev_scroll_y = None
        self.unlock_step_start_time = None
        self.active_hover_key = None
        self.hover_start_time = None
        self.current_sign_digit = None
        self.sign_hold_start = None
        self._reset_pinch()
        if self.is_locked:
            data["action"] = "LOCKED (AWAITING HAND)"

    def _evaluate_unlock(self, data, now, pointer_x, pointer_y, index_thumb_dist):
        """
        Dual Unlock System:
        1. Virtual Keyboard Air-Touch (1-9) & Numeric Signs (1-9) for 4-6 digit PIN.
        2. Multi-Gesture Sequence (Victory -> Thumb_Up).
        """
        # ==========================================
        # A. PASSWORD PIN VERIFICATION CHECK
        # ==========================================
        if self.pin_error_reset_time and now < self.pin_error_reset_time:
            data["action"] = "INCORRECT PASSWORD!"
            return
        elif self.pin_error_reset_time and now >= self.pin_error_reset_time:
            self.entered_pin_digits = ""
            self.pin_error_reset_time = None

        if len(self.entered_pin_digits) == len(self.unlock_pin):
            if self.entered_pin_digits == self.unlock_pin:
                self.is_locked = False
                data["unlock_triggered"] = True
                data["action"] = "PASSWORD UNLOCKED! ✓"
                self.entered_pin_digits = ""
                return
            else:
                data["action"] = "INCORRECT PASSWORD!"
                self.pin_error_reset_time = now + 1.0
                return

        # ==========================================
        # B. METHOD 1: NUMERIC SIGN RECOGNITION (1 to 9)
        # ==========================================
        digit_sign = self.detect_digit_sign(data["landmarks"])
        data["detected_digit_sign"] = digit_sign

        if digit_sign:
            if digit_sign == self.current_sign_digit:
                elapsed = now - self.sign_hold_start
                prog = min(1.0, elapsed / self.sign_hold_duration)
                data["sign_hold_progress"] = prog
                data["action"] = f"ANALYZING SIGN [{digit_sign}] ({int(prog * 100)}%)"

                if prog >= 1.0:
                    self._press_virtual_key(digit_sign)
                    data["action"] = f"ENTERED [{digit_sign}]"
                    self.current_sign_digit = None
                    self.sign_hold_start = None
            else:
                self.current_sign_digit = digit_sign
                self.sign_hold_start = now
        else:
            self.current_sign_digit = None
            self.sign_hold_start = None

        # ==========================================
        # C. METHOD 2: VIRTUAL KEYBOARD AIR-TOUCH
        # ==========================================
        px = int(pointer_x * 640)
        py = int(pointer_y * 480)

        hovered_key = None
        key_grid = [
            ("1", 360, 115, 435, 190), ("2", 450, 115, 525, 190), ("3", 540, 115, 615, 190),
            ("4", 360, 205, 435, 280), ("5", 450, 205, 525, 280), ("6", 540, 205, 615, 280),
            ("7", 360, 295, 435, 370), ("8", 450, 295, 525, 370), ("9", 540, 295, 615, 370),
            ("CLR", 360, 385, 435, 455), ("0", 450, 385, 525, 455), ("DEL", 540, 385, 615, 455)
        ]

        for k_name, kx1, ky1, kx2, ky2 in key_grid:
            if kx1 <= px <= kx2 and ky1 <= py <= ky2:
                hovered_key = k_name
                break

        self.active_hover_key = hovered_key
        data["active_hover_key"] = hovered_key

        if hovered_key:
            is_pinch_click = (index_thumb_dist < self.pinch_click_threshold)
            if is_pinch_click:
                self._press_virtual_key(hovered_key)
                data["action"] = f"CLICKED KEY [{hovered_key}]"
                self.hover_start_time = None
            else:
                if self.hover_start_time is None:
                    self.hover_start_time = now
                elapsed = now - self.hover_start_time
                dwell_prog = min(1.0, elapsed / self.hover_dwell_duration)
                data["key_dwell_progress"] = dwell_prog
                data["action"] = f"HOVERING [{hovered_key}] ({int(dwell_prog * 100)}%)"

                if dwell_prog >= 1.0:
                    self._press_virtual_key(hovered_key)
                    data["action"] = f"SELECTED [{hovered_key}]"
                    self.hover_start_time = None
        else:
            self.hover_start_time = None

        # ==========================================
        # D. DIRECT BIOMETRIC GESTURE UNLOCK (Peace ✌️, Open Palm 🖐️, Thumbs Up 👍)
        # ==========================================
        is_victory = False
        is_palm = (data["gesture"] == "Open_Palm")
        is_thumbs_up = (data["gesture"] in ("Thumb_Up", "Thumbs_Up"))

        if data["landmarks"]:
            idx_up = data["landmarks"][self.INDEX_TIP].y < data["landmarks"][self.INDEX_PIP].y
            mid_up = data["landmarks"][self.MIDDLE_TIP].y < data["landmarks"][self.MIDDLE_PIP].y
            rng_up = data["landmarks"][self.RING_TIP].y < data["landmarks"][self.RING_PIP].y
            pnk_up = data["landmarks"][self.PINKY_TIP].y < data["landmarks"][self.PINKY_PIP].y
            
            # Victory (Peace ✌️): Index + Middle up, Ring + Pinky curled
            if idx_up and mid_up and not rng_up and not pnk_up:
                is_victory = True
            # Open Palm (🖐️): All 4 fingers up
            if idx_up and mid_up and rng_up and pnk_up:
                is_palm = True
            # Thumbs Up (👍): Thumb up, other fingers curled
            thumb_up = data["landmarks"][self.THUMB_TIP].y < data["landmarks"][self.INDEX_MCP].y
            if thumb_up and not idx_up and not mid_up:
                is_thumbs_up = True

        # Check if any primary unlock gesture is presented (when not hovering on virtual keyboard)
        if (is_victory or is_palm or is_thumbs_up) and not hovered_key:
            self.last_matched_time = now
            if self.unlock_hold_start is None:
                self.unlock_hold_start = now
            elapsed = now - self.unlock_hold_start
            progress = min(1.0, elapsed / self.unlock_hold_required)
            g_name = "PEACE SIGN ✌️" if is_victory else ("OPEN PALM 🖐️" if is_palm else "THUMBS UP 👍")
            data["action"] = f"UNLOCKING WITH {g_name} ({int(progress * 100)}%)"

            if progress >= 1.0:
                self.is_locked = False
                data["unlock_triggered"] = True
                data["action"] = f"UNLOCKED WITH {g_name}! ✓"
                self.unlock_hold_start = None
                self.entered_pin_digits = ""
                return
        else:
            if now - self.last_matched_time > 0.25:
                self.unlock_hold_start = None

    def unlock_manual(self):
        """Emergency or master PIN unlock override."""
        self.is_locked = False
        self.lock_progress = 0.0
        self.unlock_step = 0
        self.unlock_step_start_time = None
        self.entered_pin_digits = ""

    def draw_hud(self, frame, data):
        """
        Draws high-tech Sci-Fi / Cyberpunk HUD overlay including Virtual Keyboard & Numeric Signs.
        """
        h, w = frame.shape[:2]
        
        # When LOCKED: Draw full futuristic Holographic Virtual Keyboard HUD
        if self.is_locked:
            self._draw_locked_virtual_keyboard_hud(frame, data, w, h)
            return frame

        # ==========================================
        # NORMAL RUNTIME HUD (When Unlocked)
        # ==========================================
        margin_x = int(self.config.get("active_margin_x", 0.15) * w)
        margin_y = int(self.config.get("active_margin_y", 0.15) * h)
        
        box_color = (0, 220, 255)
        cv2.rectangle(frame, (margin_x, margin_y), (w - margin_x, h - margin_y), box_color, 1, cv2.LINE_AA)
        
        bracket_len = 24
        thick = 2
        # Top-Left
        cv2.line(frame, (margin_x, margin_y), (margin_x + bracket_len, margin_y), box_color, thick, cv2.LINE_AA)
        cv2.line(frame, (margin_x, margin_y), (margin_x, margin_y + bracket_len), box_color, thick, cv2.LINE_AA)
        # Top-Right
        cv2.line(frame, (w - margin_x, margin_y), (w - margin_x - bracket_len, margin_y), box_color, thick, cv2.LINE_AA)
        cv2.line(frame, (w - margin_x, margin_y), (w - margin_x, margin_y + bracket_len), box_color, thick, cv2.LINE_AA)
        # Bottom-Left
        cv2.line(frame, (margin_x, h - margin_y), (margin_x + bracket_len, h - margin_y), box_color, thick, cv2.LINE_AA)
        cv2.line(frame, (margin_x, h - margin_y), (margin_x, h - margin_y - bracket_len), box_color, thick, cv2.LINE_AA)
        # Bottom-Right
        cv2.line(frame, (w - margin_x, h - margin_y), (w - margin_x - bracket_len, h - margin_y), box_color, thick, cv2.LINE_AA)
        cv2.line(frame, (w - margin_x, h - margin_y), (w - margin_x, h - margin_y - bracket_len), box_color, thick, cv2.LINE_AA)

        if data["hand_detected"] and data["landmarks"]:
            landmarks = data["landmarks"]
            for lm in landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 200), -1, cv2.LINE_AA)
                cv2.circle(frame, (cx, cy), 5, (0, 180, 255), 1, cv2.LINE_AA)
            
            for p1, p2 in self.CONNECTIONS:
                pt1 = (int(landmarks[p1].x * w), int(landmarks[p1].y * h))
                pt2 = (int(landmarks[p2].x * w), int(landmarks[p2].y * h))
                cv2.line(frame, pt1, pt2, (0, 240, 255), 1, cv2.LINE_AA)

            idx_pt = (int(landmarks[self.INDEX_TIP].x * w), int(landmarks[self.INDEX_TIP].y * h))
            reticle_color = (0, 255, 120) if data["action"] == "POINTER" else (255, 200, 0)
            if "CLICK" in data["action"] or data["action"] == "DRAGGING":
                reticle_color = (0, 0, 255)
            cv2.circle(frame, idx_pt, 12, reticle_color, 2, cv2.LINE_AA)
            cv2.circle(frame, idx_pt, 2, reticle_color, -1, cv2.LINE_AA)
            cv2.line(frame, (idx_pt[0] - 16, idx_pt[1]), (idx_pt[0] + 16, idx_pt[1]), reticle_color, 1, cv2.LINE_AA)
            cv2.line(frame, (idx_pt[0], idx_pt[1] - 16), (idx_pt[0], idx_pt[1] + 16), reticle_color, 1, cv2.LINE_AA)

        if data["lock_progress"] > 0.0:
            prog = data["lock_progress"]
            bar_w = 260
            bar_h = 18
            bx = (w - bar_w) // 2
            by = h - 65
            cv2.rectangle(frame, (bx - 2, by - 2), (bx + bar_w + 2, by + bar_h + 2), (255, 255, 255), 1, cv2.LINE_AA)
            fill_w = int(bar_w * prog)
            cv2.rectangle(frame, (bx, by), (bx + fill_w, by + bar_h), (0, 0, 255), -1)
            cv2.putText(frame, f"LOCKING LAPTOP... {int(prog * 100)}%", (bx + 20, by - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 100, 255), 2, cv2.LINE_AA)

        # Status Overlay Bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (15, 15), (320, 105), (15, 15, 25), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        cv2.rectangle(frame, (15, 15), (320, 105), (0, 200, 255), 1, cv2.LINE_AA)

        status_text = data["action"]
        status_color = (0, 255, 0)
        if "CLICK" in status_text or "LOCKING" in status_text:
            status_color = (0, 165, 255)

        cv2.putText(frame, "AEROLOCK // VIRTUAL MOUSE", (25, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"STATUS: {status_text}", (25, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, status_color, 2, cv2.LINE_AA)
        cv2.putText(frame, f"GESTURE: {data['gesture']}  |  FPS: {int(self.fps)}", (25, 82),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, f"HAND: {data['handedness']}", (25, 98),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1, cv2.LINE_AA)

        return frame

    def _draw_locked_virtual_keyboard_hud(self, frame, data, w, h):
        """
        Draws the interactive Holographic Virtual Keyboard (1 to 9) and 4-6 Digit Password status.
        """
        # Dark tech background overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (10, 12, 22), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        # Draw hand skeleton if detected
        if data["hand_detected"] and data["landmarks"]:
            landmarks = data["landmarks"]
            for lm in landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 200), -1, cv2.LINE_AA)
            for p1, p2 in self.CONNECTIONS:
                pt1 = (int(landmarks[p1].x * w), int(landmarks[p1].y * h))
                pt2 = (int(landmarks[p2].x * w), int(landmarks[p2].y * h))
                cv2.line(frame, pt1, pt2, (0, 200, 255), 1, cv2.LINE_AA)

            # Mirrored pointer reticle on Index tip
            px = int(data["pointer_x"] * w)
            py = int(data["pointer_y"] * h)
            cv2.circle(frame, (px, py), 10, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 2, (0, 255, 255), -1, cv2.LINE_AA)

        # Header Title
        cv2.putText(frame, "AEROLOCK // VIRTUAL KEYBOARD UNLOCK", (25, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "Show Peace Sign (V) or Open Palm to Instant Unlock, or Enter Passcode", (25, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

        # LEFT PANEL: 4-6 Digit Password Display Boxes
        pw_len = len(self.unlock_pin)
        box_w = 42
        box_h = 50
        start_x = 25
        start_y = 100

        cv2.putText(frame, f"ENTER {pw_len}-DIGIT PASSCODE:", (start_x, start_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 200), 1, cv2.LINE_AA)

        for i in range(pw_len):
            bx = start_x + i * (box_w + 10)
            by = start_y
            has_digit = i < len(self.entered_pin_digits)
            box_col = (0, 255, 120) if has_digit else (80, 80, 90)
            cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), box_col, 2, cv2.LINE_AA)
            
            if has_digit:
                digit_char = self.entered_pin_digits[i]
                cv2.putText(frame, digit_char, (bx + 14, by + 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2, cv2.LINE_AA)
            else:
                cv2.circle(frame, (bx + box_w // 2, by + box_h // 2), 4, (120, 120, 130), -1, cv2.LINE_AA)

        # Numeric Sign Detection Feedback
        cv2.putText(frame, "NUMERIC HAND SIGN DETECTED:", (start_x, start_y + 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)
        
        detected_sign = data.get("detected_digit_sign")
        sign_txt = f"SIGN: [{detected_sign}]" if detected_sign else "SHOW SIGN 1 TO 9"
        sign_col = (0, 255, 0) if detected_sign else (120, 120, 120)
        cv2.putText(frame, sign_txt, (start_x, start_y + 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, sign_col, 2, cv2.LINE_AA)

        # Sign hold progress bar
        sign_prog = data.get("sign_hold_progress", 0.0)
        if sign_prog > 0:
            cv2.rectangle(frame, (start_x, start_y + 128), (start_x + 180, start_y + 138), (50, 50, 60), -1)
            cv2.rectangle(frame, (start_x, start_y + 128), (start_x + int(180 * sign_prog), start_y + 138), (0, 255, 0), -1)
            cv2.putText(frame, f"CONFIRMING {int(sign_prog * 100)}%", (start_x + 190, start_y + 137),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1, cv2.LINE_AA)

        # Current Action Status
        cv2.putText(frame, f"STATUS: {data['action']}", (start_x, start_y + 175),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 2, cv2.LINE_AA)

        # Quick guide mini box
        cv2.putText(frame, "SIGN GUIDE: 1=Index, 2=V, 3=3-Fingers, 4=4-Fingers", (start_x, start_y + 225),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 140, 140), 1, cv2.LINE_AA)
        cv2.putText(frame, "            5=Palm, 6=Shaka, 8=Gun, 9=OK Sign", (start_x, start_y + 242),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 140, 140), 1, cv2.LINE_AA)

        # RIGHT PANEL: 3x4 VIRTUAL AIR KEYBOARD
        key_grid = [
            ("1", 360, 115, 435, 190), ("2", 450, 115, 525, 190), ("3", 540, 115, 615, 190),
            ("4", 360, 205, 435, 280), ("5", 450, 205, 525, 280), ("6", 540, 205, 615, 280),
            ("7", 360, 295, 435, 370), ("8", 450, 295, 525, 370), ("9", 540, 295, 615, 370),
            ("CLR", 360, 385, 435, 455), ("0", 450, 385, 525, 455), ("DEL", 540, 385, 615, 455)
        ]

        active_k = data.get("active_hover_key")
        dwell_prog = data.get("key_dwell_progress", 0.0)

        for name, kx1, ky1, kx2, ky2 in key_grid:
            is_hovered = (name == active_k)
            border_col = (0, 255, 255) if is_hovered else (50, 180, 220)
            bg_col = (20, 60, 80) if is_hovered else (15, 20, 35)

            # Draw key background
            cv2.rectangle(frame, (kx1, ky1), (kx2, ky2), bg_col, -1)
            cv2.rectangle(frame, (kx1, ky1), (kx2, ky2), border_col, 2 if is_hovered else 1, cv2.LINE_AA)

            # Draw dwell progress fill if hovered
            if is_hovered and dwell_prog > 0:
                fill_h = int((ky2 - ky1) * dwell_prog)
                cv2.rectangle(frame, (kx1, ky2 - fill_h), (kx2, ky2), (0, 255, 120), -1)

            # Draw key text
            text_size = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
            tx = kx1 + (kx2 - kx1 - text_size[0]) // 2
            ty = ky1 + (ky2 - ky1 + text_size[1]) // 2
            text_col = (0, 0, 0) if (is_hovered and dwell_prog > 0.5) else (255, 255, 255)
            cv2.putText(frame, name, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.70, text_col, 2, cv2.LINE_AA)
