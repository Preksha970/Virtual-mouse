"""
Smart User Presence Detection Module
====================================
Tracks user presence via face detection on the webcam feed.

Key Features:
- Continuous face presence tracking using OpenCV webcam feed.
- Anti-flicker & debounce protection to ignore brief movements, sneezes, or glances.
- Multi-stage away alerts:
    Stage 1: 10s  -> "Hey, are you still there? We can't see you!"
    Stage 2: 30s  -> "Where did you go? Take your time!"
    Stage 3: 60s  -> "Still away? Your virtual mouse is waiting for you!"
    Stage 4: 180s -> "You've been away for a while. Would you like to lock your screen?"
- Welcome back notification trigger upon user return:
    "Welcome back! Your virtual mouse is ready!"
- Cooldown period after return to prevent repeated notification bursts.
- Non-blocking async face detection worker thread to prevent freezing the webcam feed.
- Multi-backend face detector: MediaPipe Face Detection with robust OpenCV Haar Cascade fallback.
- Strictly in-memory: ZERO frames, images, or audio recordings are saved to disk.
"""

import time
import os
import threading
import cv2
import numpy as np

# Try importing MediaPipe for face detection
try:
    import mediapipe as mp
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
    Supports both synchronous and asynchronous (non-blocking) detection.
    """

    STAGE_MESSAGES = {
        10: "Hey, are you still there? We can't see you!",
        30: "Where did you go? Take your time!",
        60: "Still away? Your virtual mouse is waiting for you!",
        180: "You've been away for a while. Would you like to lock your screen?"
    }

    def __init__(self, debounce_sec: float = 1.5, custom_thresholds: dict = None,
                 cooldown_sec: float = 5.0, async_mode: bool = False):
        """
        :param debounce_sec: Grace period (seconds) before declaring absence to ignore temporary flickers.
        :param custom_thresholds: Optional custom dict mapping seconds -> message.
        :param cooldown_sec: Cooldown period (seconds) after welcome-back before new absence alerts can trigger.
        :param async_mode: When True, runs face detection in a background worker thread to ensure
                           the main OpenCV webcam loop never freezes or drops frames.
        """
        self.debounce_sec = debounce_sec
        self.cooldown_sec = cooldown_sec
        self.async_mode = async_mode
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
        self.last_welcome_time = 0.0

        # Anti-flicker return verification (require 2 consecutive frames of face to confirm return)
        self.consecutive_face_frames = 0
        self.required_return_frames = 2

        # Initialize face detector backend
        self.backend = None
        self._init_detector()

        # Thread synchronization for async mode
        self._lock = threading.Lock()
        self._latest_detected = True
        self._latest_bbox = None
        self._pending_frame = None
        self._worker_running = False

        if self.async_mode:
            self._start_async_worker()

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
            # Fallback to adaptive skin/intensity heuristic detector if no cascade file exists
            self.backend = "adaptive_fallback"

    def _start_async_worker(self):
        """Launches background thread for non-blocking face detection."""
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._async_detection_loop, daemon=True)
        self._worker_thread.start()

    def _async_detection_loop(self):
        """Continuously processes queued frames in background."""
        while self._worker_running:
            frame_to_process = None
            with self._lock:
                if self._pending_frame is not None:
                    frame_to_process = self._pending_frame
                    self._pending_frame = None

            if frame_to_process is not None:
                detected, bbox = self.detect_face(frame_to_process)
                with self._lock:
                    self._latest_detected = detected
                    self._latest_bbox = bbox
            else:
                time.sleep(0.01)

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

        # 2. OpenCV CascadeClassifier (optimized with 2x downscaling for high FPS)
        if self.backend == "opencv_cascade" and hasattr(self, 'cascade'):
            try:
                # Downsample frame for 4x faster detection
                scale_factor = 2
                small_w = max(1, w // scale_factor)
                small_h = max(1, h // scale_factor)
                small_gray = cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), (small_w, small_h))
                faces = self.cascade.detectMultiScale(
                    small_gray,
                    scaleFactor=1.15,
                    minNeighbors=4,
                    minSize=(30, 30)
                )
                if len(faces) > 0:
                    x, y, bw, bh = faces[0]
                    # Scale back up to original coordinates
                    return True, (int(x * scale_factor), int(y * scale_factor),
                                  int(bw * scale_factor), int(bh * scale_factor))
                return False, None
            except Exception:
                pass

        # 3. Adaptive Motion/Skin heuristic fallback
        try:
            ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
            lower = np.array([0, 133, 77], dtype=np.uint8)
            upper = np.array([255, 173, 127], dtype=np.uint8)
            mask = cv2.inRange(ycrcb, lower, upper)
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

    def update(self, frame_bgr, current_time=None, hand_active: bool = False):
        """
        Processes a webcam frame, calculates presence status, and returns any popup event.

        :param frame_bgr: BGR frame from OpenCV
        :param current_time: Optional float timestamp (defaults to time.time())
        :param hand_active: Optional bool indicating if an active hand gesture is currently detected
        :return: (is_present: bool, face_bbox: tuple|None, event: dict|None)
        """
        now = current_time if current_time is not None else time.time()

        # Face detection (synchronous or async cached)
        if self.async_mode:
            with self._lock:
                if self._pending_frame is None:
                    # Provide a low-res copy to background worker to prevent latency
                    self._pending_frame = frame_bgr.copy()
                face_detected = self._latest_detected
                bbox = self._latest_bbox
        else:
            face_detected, bbox = self.detect_face(frame_bgr)

        # If user's hand is actively tracked and moving, maintain presence to prevent accidental interruptions
        if hand_active:
            face_detected = True

        event = None

        if face_detected:
            self.consecutive_face_frames += 1
            self.last_face_seen_time = now

            # If user was confirmed away and we have seen consecutive positive frames
            if not self.is_present and self.has_been_away_long_enough:
                if self.consecutive_face_frames >= self.required_return_frames:
                    # Emit Welcome Back event
                    event = {
                        "type": "welcome",
                        "title": "Welcome Back!",
                        "message": "Welcome back! Your virtual mouse is ready!",
                        "duration": 3.0
                    }
                    self.last_welcome_time = now
                    self.triggered_stages.clear()
                    self.has_been_away_long_enough = False
                    self.is_present = True
                    self.absence_start_time = None
                    self.away_duration = 0.0
            else:
                self.is_present = True
                self.absence_start_time = None
                self.away_duration = 0.0

        else:
            self.consecutive_face_frames = 0
            time_since_last_seen = now - self.last_face_seen_time

            # Check if absence exceeds the anti-flicker debounce threshold
            if time_since_last_seen >= self.debounce_sec:
                if self.is_present:
                    # User officially transitioned to AWAY
                    self.is_present = False
                    self.absence_start_time = self.last_face_seen_time

                # Total away duration
                self.away_duration = now - (self.absence_start_time or self.last_face_seen_time)

                # Check cooldown: don't trigger absence popups right after welcoming back
                in_cooldown = (now - self.last_welcome_time < self.cooldown_sec)

                if not in_cooldown:
                    # Check multi-stage thresholds (10s, 30s, 60s, 180s)
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
        """Resets presence tracking counters and stages."""
        now = time.time()
        self.last_face_seen_time = now
        self.absence_start_time = None
        self.is_present = True
        self.away_duration = 0.0
        self.triggered_stages.clear()
        self.has_been_away_long_enough = False
        self.consecutive_face_frames = 0

    def stop(self):
        """Stops background async worker thread if active."""
        self._worker_running = False
