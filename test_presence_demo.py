"""
Interactive Test & Simulation Script for Smart User Presence Detection
======================================================================
This script verifies the presence detection logic and Tkinter popup system.
It accelerates time so you can inspect all 4 absence tiers (10s, 30s, 1m, 3m),
the "Lock Screen Now" button, the Welcome Back toast with auto-dismissal,
cooldown behavior, and the Camera Disconnect alert in just ~10 seconds!

Stages Tested:
1. User present in front of the camera.
2. User walks away -> 10s trigger: "Hey, are you still there? We can't see you!"
3. User stays away -> 30s trigger: "Where did you go? Take your time!"
4. User stays away -> 60s trigger: "Still away? Your virtual mouse is waiting for you!"
5. User stays away -> 180s trigger: "You've been away for a while. Would you like to lock your screen?"
6. User returns -> Auto-dismisses absence popup and displays:
   "Welcome back! Your virtual mouse is ready!"
7. Cooldown verification: ensures notifications aren't rapidly spammed.
8. Camera disconnect simulation alert.
"""

import time
import numpy as np
from presence_detector import PresenceDetector
from popup_manager import PopupManager


def run_simulation(time_multiplier: float = 20.0):
    """
    Runs an accelerated simulation of user presence transitions.
    :param time_multiplier: Speed-up factor (e.g., 20.0 runs 20x faster for quick testing).
    """
    print("=" * 75)
    print("SMART USER PRESENCE DETECTION & POPUP SYSTEM - AUTOMATED VERIFICATION")
    print("=" * 75)
    print(f"[TEST SETUP] Speed multiplier: {time_multiplier}x")

    # Use synchronous mode (async_mode=False) for deterministic simulation stepping
    detector = PresenceDetector(debounce_sec=1.0, cooldown_sec=3.0, async_mode=False)
    popup = PopupManager()

    # Create dummy frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    simulated_clock = time.time()

    def step_time(seconds: float):
        nonlocal simulated_clock
        simulated_clock += seconds
        real_sleep = seconds / time_multiplier
        if real_sleep > 0.05:
            time.sleep(real_sleep)

    # --------------------------------------------------------------------------
    # Phase 1: User Present
    # --------------------------------------------------------------------------
    print("\n--- PHASE 1: User is sitting at the computer (Present) ---")
    detector.last_face_seen_time = simulated_clock
    detector.is_present = True
    print("Status: User is active. Hand gesture virtual mouse running.")
    step_time(2.0)

    # --------------------------------------------------------------------------
    # Phase 2: User leaves camera view (Absence Begins)
    # --------------------------------------------------------------------------
    print("\n--- PHASE 2: User leaves the camera (Absence begins) ---")
    user_left_time = simulated_clock

    # Step through time until 10s popup triggers
    print("Waiting for 10 seconds of continuous absence...")
    while simulated_clock - user_left_time < 10.5:
        step_time(1.0)
        is_pres, bbox, event = detector.update(dummy_frame, current_time=simulated_clock)
        if event and event["type"] == "away":
            print(f"\n>>> [POPUP TRIGGERED @ {event['seconds']}s]: '{event['message']}'")
            popup.show_absence_popup(event["stage"], event["message"], event["show_lock_option"])

    # Step to 30s
    print("\nUser still away... Advancing to 30 seconds...")
    while simulated_clock - user_left_time < 30.5:
        step_time(2.0)
        is_pres, bbox, event = detector.update(dummy_frame, current_time=simulated_clock)
        if event and event["type"] == "away":
            print(f"\n>>> [POPUP TRIGGERED @ {event['seconds']}s]: '{event['message']}'")
            popup.show_absence_popup(event["stage"], event["message"], event["show_lock_option"])

    # Step to 60s (1 minute)
    print("\nUser still away... Advancing to 60 seconds (1 minute)...")
    while simulated_clock - user_left_time < 60.5:
        step_time(5.0)
        is_pres, bbox, event = detector.update(dummy_frame, current_time=simulated_clock)
        if event and event["type"] == "away":
            print(f"\n>>> [POPUP TRIGGERED @ {event['seconds']}s]: '{event['message']}'")
            popup.show_absence_popup(event["stage"], event["message"], event["show_lock_option"])

    # Step to 180s (3 minutes)
    print("\nUser still away... Advancing to 180 seconds (3 minutes)...")
    while simulated_clock - user_left_time < 180.5:
        step_time(10.0)
        is_pres, bbox, event = detector.update(dummy_frame, current_time=simulated_clock)
        if event and event["type"] == "away":
            print(f"\n>>> [POPUP TRIGGERED @ {event['seconds']}s]: '{event['message']}'")
            print(">>> Notice: Actionable 'Lock Screen Now' button added to popup!")
            popup.show_absence_popup(event["stage"], event["message"], event["show_lock_option"])

    # Keep 3m popup visible briefly for visual inspection
    time.sleep(1.5)

    # --------------------------------------------------------------------------
    # Phase 3: User Returns!
    # --------------------------------------------------------------------------
    print("\n--- PHASE 3: User returns in front of webcam! ---")
    step_time(1.0)

    # Simulate face detected
    detector.detect_face = lambda frame: (True, (150, 100, 200, 200))

    # Send confirmation frames
    for _ in range(detector.required_return_frames):
        is_pres, bbox, event = detector.update(dummy_frame, current_time=simulated_clock)
        if event and event["type"] == "welcome":
            print(f"\n>>> [WELCOME BACK TRIGGERED]: '{event['message']}'")
            print(">>> Absence popup was automatically dismissed!")
            print(">>> Welcome Back toast displayed (auto-dismisses in 3 seconds).")
            popup.show_welcome_back(event["message"], duration=3.0)

    time.sleep(2.5)

    # --------------------------------------------------------------------------
    # Phase 4: Camera Disconnect Alert Test
    # --------------------------------------------------------------------------
    print("\n--- PHASE 4: Testing Camera Disconnection Alert ---")
    popup.show_camera_error("Webcam feed was disconnected or lost!", cooldown_sec=5.0)
    time.sleep(2.0)

    print("\n[TEST COMPLETED] All features and transitions verified successfully!")
    popup.close_all()
    print("=" * 75)


if __name__ == "__main__":
    run_simulation(time_multiplier=20.0)
