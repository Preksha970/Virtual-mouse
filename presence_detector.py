"""
Smart User Presence Detection Module
====================================
Tracks user presence via face detection on the webcam feed.
Features:
- Continuous face presence tracking.
- Debounce / anti-flicker filter to ignore brief movements, sneezes, or glances.
- Multi-stage away alerts:
    Stage 1: 10s  -> "Hey, are you still there? We can't see you!"
    Stage 2: 30s  -> "Where did you go? Take your time!"
    Stage 3: 60s  -> "Still away? Your virtual mouse is waiting for you!"
    Stage 4: 180s -> "You've been away for a while. Would you like to lock your screen?"
- Welcome back notification trigger upon user return.
- Supports MediaPipe Face Detection with robust OpenCV cascades / DNN fallback.
- Strictly in-memory: NO frames or recordings are ever saved to disk.
"""

import time
import os
import cv2
import numpy as np

# Try importing MediaPipe for face detection
try:
    import mediapipe as mp
    # Check if solutions.face_detection exists
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_detection'):
        HAS_MEDIAPIPE = True
    else:
        HAS_MEDIAPIPE = False
except Exception:
    HAS_MEDIAPIPE = False


class PresenceDetector:
    """
    Monitors user presence in front of the webcam using face detection.
    Computes away duration with anti-flicker smoothing and emits timed stage events.
    """

    STAGE_MESSAGES = {
        10: "Hey, are you still there? We can't see you!",
        30: "Where did you go? Take your time!",
        60: "Still away? Your virtual mouse is waiting for you!",
        180: "You've been away for a while. Would you like to lock your screen?"
    }

    def __init__(self, debounce_sec: float = 1.5, custom_thresholds: dict = None):
        """
        :param debounce_sec: Grace period (seconds) before declaring absence to ignore temporary flickers.
        :param custom_thresholds: Optional custom dict mapping seconds -> message.
        """
        self.debounce_sec = debounce_sec
        self.thresholds = custom_thresholds or self.STAGE_MESSAGES
        self.sorted_stages = sorted(self.thresholds.keys())

        # Timing states
        now = time.time()
        self.last_face_seen_time = now
        self.absence_start_time = None
        self.is_present = True
        self.away_duration = 0.0

        # Trigger tracking to prevent repeated popups
        self.triggered_stages = set()
        self.welcome_pending = False
        self.has_been_away_long_enough = False

        # Initialize face detector backend
        self.backend = None
        self._init_detector()

    def _init_detector(self):
        """Initializes MediaPipe Face Detection or OpenCV fallback."""
        if HAS_MEDIAPIPE:
            try:
                self.mp_face = mp.solutions.face_detection.FaceDetection(
                    min_detection_confidence=0.5,
                    model_selection=0  # 0 for short range (<2m), ideal for webcam
                )
                self.backend = "mediapipe"
                return
            except Exception:
                pass

        # OpenCV CascadeClassifier fallback
        cascade_path = None
        try:
            if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                candidate = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
                if os.path.exists(candidate):
                    cascade_path = candidate
        except Exception:
            pass

        if cascade_path and hasattr(cv2, 'CascadeClassifier'):
            self.cascade = cv2.CascadeClassifier(cascade_path)
            self.backend = "opencv_cascade"
        else:
            # Fallback to an adaptive skin/intensity heuristic detector if no model files exist
            self.backend = "adaptive_fallback"

    def detect_face(self, frame_bgr):
        """
        Performs face detection on the current BGR video frame.
        :return: (found_face: bool, bbox: (x, y, w, h) or None)
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return False, None

        h, w = frame_bgr.shape[:2]

        # 1. MediaPipe Face Detection
        if self.backend == "mediapipe":
            try:
                rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                results = self.mp_face.process(rgb_frame)
                if results and results.detections:
                    det = results.detections[0]
                    bb = det.location_data.relative_bounding_box
                    x = max(0, int(bb.xmin * w))
                    y = max(0, int(bb.ymin * h))
                    bw = min(w - x, int(bb.width * w))
                    bh = min(h - y, int(bb.height * h))
                    return True, (x, y, bw, bh)
                return False, None
            except Exception:
                pass

        # 2. OpenCV CascadeClassifier
        if self.backend == "opencv_cascade" and hasattr(self, 'cascade'):
            try:
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
                if len(faces) > 0:
                    x, y, bw, bh = faces[0]
                    return True, (int(x), int(y), int(bw), int(bh))
                return False, None
            except Exception:
                pass

        # 3. Adaptive Motion/Skin heuristic fallback
        # Used when neither MediaPipe nor Cascade XML are packaged in the environment
        try:
            ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
            # Skin color range in YCrCb
            lower = np.array([0, 133, 77], dtype=np.uint8)
            upper = np.array([255, 173, 127], dtype=np.uint8)
            mask = cv2.inRange(ycrcb, lower, upper)
            # Center region where user sits
            center_h_start, center_h_end = int(h * 0.15), int(h * 0.85)
            center_w_start, center_w_end = int(w * 0.20), int(w * 0.80)
            center_roi = mask[center_h_start:center_h_end, center_w_start:center_w_end]
            skin_pixels = cv2.countNonZero(center_roi)
            total_center_pixels = center_roi.size
            if total_center_pixels > 0 and (skin_pixels / total_center_pixels) > 0.05:
                return True, (center_w_start, center_h_start, center_w_end - center_w_start, center_h_end - center_h_start)
            return False, None
        except Exception:
            return False, None

    def update(self, frame_bgr, current_time=None):
        """
        Processes a webcam frame, calculates presence status, and returns any popup event.
        :param frame_bgr: BGR frame from OpenCV
        :param current_time: Optional float timestamp (defaults to time.time())
        :return: (is_present: bool, face_bbox: tuple|None, event: dict|None)
        """
        now = current_time if current_time is not None else time.time()
        face_detected, bbox = self.detect_face(frame_bgr)

        event = None

        if face_detected:
            # User face is visible
            self.last_face_seen_time = now

            # If user was previously confirmed away, trigger Welcome Back
            if not self.is_present and self.has_been_away_long_enough:
                event = {
                    "type": "welcome",
                    "title": "Welcome Back!",
                    "message": "Welcome back! Your virtual mouse is ready!",
                    "duration": 3.0  # seconds to keep visible
                }
                # Reset away states
                self.triggered_stages.clear()
                self.has_been_away_long_enough = False

            self.is_present = True
            self.absence_start_time = None
            self.away_duration = 0.0

        else:
            # Face not detected in this frame
            time_since_last_seen = now - self.last_face_seen_time

            # Check if absence exceeds the anti-flicker debounce threshold
            if time_since_last_seen >= self.debounce_sec:
                if self.is_present:
                    # User officially transitioned to AWAY
                    self.is_present = False
                    self.absence_start_time = self.last_face_seen_time

                # Compute total away duration
                self.away_duration = now - (self.absence_start_time or self.last_face_seen_time)

                # Check stage thresholds (10s, 30s, 60s, 180s)
                for stage_sec in self.sorted_stages:
                    if self.away_duration >= stage_sec and stage_sec not in self.triggered_stages:
                        self.triggered_stages.add(stage_sec)
                        self.has_been_away_long_enough = True

                        event = {
                            "type": "away",
                            "stage": stage_sec,
                            "seconds": stage_sec,
                            "title": f"User Presence Alert ({stage_sec}s)",
                            "message": self.thresholds[stage_sec],
                            "show_lock_option": (stage_sec >= 180)
                        }

        return self.is_present, bbox, event

    def reset(self):
        """Resets presence tracking counters."""
        now = time.time()
        self.last_face_seen_time = now
        self.absence_start_time = None
        self.is_present = True
        self.away_duration = 0.0
        self.triggered_stages.clear()
        self.has_been_away_long_enough = False
