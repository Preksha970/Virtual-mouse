"""
AeroLock Master Application
Integrates Virtual Mouse, Real-time Gesture Engine, Holographic Screen Shield,
Windows OS Lock integration, and Web Dashboard Control Center.
"""

import sys
import os
import json
import time
import argparse
import threading
import cv2
import numpy as np

from mouse_controller import MouseController
from gesture_engine import GestureEngine
from system_lock import SystemLock
from screen_shield import ScreenShield
from web_server import WebDashboard

def load_config(config_path="config.json"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, config_path)
    if os.path.exists(full_path):
        try:
            with open(full_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to read {config_path}: {e}")
    return {}

def init_camera(preferred_id=0, frame_w=640, frame_h=480):
    """
    Intelligently probes and connects to the working webcam (preferring Camera 0).
    Rejects dummy/disconnected devices that output completely black frames (mean < 3.0).
    """
    candidates = []
    for c in [preferred_id, 0, 1, 2, 3]:
        if c not in candidates:
            candidates.append(c)
    
    for cid in candidates:
        print(f"[*] Probing Camera Device #{cid}...", flush=True)
        for backend, b_name in [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "MediaFoundation"), (cv2.CAP_ANY, "Default")]:
            try:
                cap = cv2.VideoCapture(cid, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_w)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_h)
                    
                    # Read 2-3 warm-up frames to confirm active stream
                    ret = False
                    frame = None
                    for _ in range(3):
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            break
                        time.sleep(0.05)
                        
                    if ret and frame is not None and frame.size > 0:
                        mean_val = float(frame.mean())
                        print(f"[*] Device #{cid} ({b_name}) test frame brightness: {mean_val:.2f}", flush=True)
                        if mean_val < 3.0:
                            print(f"[!] Device #{cid} ({b_name}) returned pitch-black frames (mean={mean_val:.2f}), skipping dummy sensor.", flush=True)
                            cap.release()
                            continue
                        print(f"[✓] Active RGB webcam connected: Device #{cid} ({b_name}) [brightness: {mean_val:.2f}]!", flush=True)
                        return cap, cid
                    cap.release()
                else:
                    cap.release()
            except Exception as e:
                print(f"    Notice on #{cid} ({b_name}): {e}", flush=True)
                
    print("[!] No active physical webcam stream could be read.", flush=True)
    return None, None

def create_synthetic_frame(w=640, h=480, counter=0):
    """Fallback synthetic camera frame if physical webcam is unavailable."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Dark blue-gray tech background
    frame[:, :] = (20, 16, 12)
    # Grid lines
    for x in range(0, w, 40):
        cv2.line(frame, (x, 0), (x, h), (35, 28, 22), 1)
    for y in range(0, h, 40):
        cv2.line(frame, (0, y), (w, y), (35, 28, 22), 1)

    cv2.putText(frame, "SIMULATED CAMERA MODE", (w // 2 - 140, h // 2 - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 245, 212), 2, cv2.LINE_AA)
    cv2.putText(frame, "No physical webcam stream detected", (w // 2 - 130, h // 2 + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.putText(frame, "Connect webcam & restart to track hand gestures", (w // 2 - 165, h // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 200, 255), 1, cv2.LINE_AA)
    return frame

def main():
    parser = argparse.ArgumentParser(description="AeroLock: Virtual Mouse & Gesture Security System")
    parser.add_argument("--no-window", action="store_true", help="Run without native OpenCV window (Web Dashboard only)")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (default from config)")
    parser.add_argument("--port", type=int, default=5000, help="Web dashboard port")
    args = parser.parse_args()

    config = load_config()
    camera_id = args.camera if args.camera is not None else config.get("camera_id", 0)
    frame_w = config.get("frame_width", 640)
    frame_h = config.get("frame_height", 480)
    show_window = not args.no_window and config.get("show_camera_window", True)

    print("=" * 60)
    print("      AEROLOCK // AI VIRTUAL MOUSE & SECURITY SYSTEM")
    print("=" * 60)
    print(f"[*] Initializing low-latency Windows Mouse Controller...")
    mouse = MouseController(config=config)
    print(f"[*] Screen Resolution Detected: {mouse.screen_width} x {mouse.screen_height}")

    print(f"[*] Initializing MediaPipe Gesture Engine...")
    engine = GestureEngine(config=config)

    print(f"[*] Initializing Native Windows Lock & Holographic Screen Shield...")
    sys_lock = SystemLock(config=config)
    
    def on_unlocked():
        print("[Security] System unlocked by user.")
        engine.unlock_manual()

    shield = ScreenShield(config=config, on_unlocked_callback=on_unlocked)

    print(f"[*] Starting Web Dashboard & Telemetry Hub at http://127.0.0.1:{args.port}...")
    dashboard = WebDashboard(
        engine=engine,
        mouse=mouse,
        shield=shield,
        sys_lock=sys_lock,
        port=args.port
    )
    dashboard.run()

    # Initialize Camera with Auto-Discovery
    cap, active_cid = init_camera(preferred_id=camera_id, frame_w=frame_w, frame_h=frame_h)
    camera_available = (cap is not None and cap.isOpened())
    if not camera_available:
        print("[!] Physical webcam unavailable. Entering standby synthetic feed mode.")

    print("\n[Controls Guide]")
    print("  • Point Index Finger      : Move Cursor")
    print("  • Pinch Index + Thumb     : Left Click / Hold to Drag")
    print("  • Pinch Middle + Thumb    : Right Click")
    print("  • Two Fingers Up (V)      : Scroll Up / Down")
    print("  • Closed Fist (Hold 1.5s) : Lock Laptop")
    print("  • Sequence (Peace -> Up)  : Unlock Screen")
    print("  • Press 'm'               : Toggle Virtual Mouse ON/OFF")
    print("  • Press 'l'               : Test Lock System")
    print("  • Press 'u'               : Test Unlock System")
    print("  • Press 'q' or ESC        : Quit Application\n")

    sim_counter = 0
    frame_counter = 0

    try:
        while True:
            frame_counter += 1
            if camera_available:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
                # Flip horizontally for natural mirror feel
                frame = cv2.flip(frame, 1)
            else:
                sim_counter += 1
                frame = create_synthetic_frame(frame_w, frame_h, sim_counter)
                time.sleep(0.033)

            if frame_counter % 60 == 0:
                print(f"[*] Frame {frame_counter}: cam_ok={camera_available}, raw_mean={frame.mean():.2f}", flush=True)

            # Process frame through gesture engine
            data = engine.process_frame(frame)
            engine.current_action = data["action"]
            engine.current_gesture = data["gesture"]

            # Sync shield subprocess status (if unlocked via PIN/ESC inside the window)
            if engine.is_locked and shield.is_active:
                if shield.check_subprocess_status() == "UNLOCKED":
                    engine.unlock_manual()

            # ==========================================
            # HANDLE LOCK / UNLOCK EVENTS
            # ==========================================
            if data["lock_triggered"]:
                print("\n[ALERT] LOCK GESTURE DETECTED! Initiating lock sequence...")
                lock_type = config.get("lock_system_type", "both")
                if lock_type in ("both", "shield_only"):
                    shield.activate()
                if lock_type in ("both", "windows_only"):
                    sys_lock.lock_windows_os()

            if data["unlock_triggered"]:
                print("\n[ALERT] UNLOCK SEQUENCE VERIFIED! Restoring access...")
                shield.dismiss()

            # If locked, update the holographic shield status
            if engine.is_locked and shield.is_active:
                step = data["unlock_step"]
                target = data["unlock_target"] or "None"
                # Extract hold progress
                prog = 0.0
                if engine.unlock_step_start_time:
                    prog = min(1.0, (time.time() - engine.unlock_step_start_time) / engine.step_hold_required)
                shield.update_gesture_progress(
                    current_step=step,
                    step_name=target,
                    progress_pct=prog,
                    status_text=data["action"],
                    entered_pin=data.get("entered_pin", ""),
                    detected_sign=data.get("detected_digit_sign")
                )

            # ==========================================
            # HANDLE MOUSE ACTIONS (When Unlocked)
            # ==========================================
            if not engine.is_locked and mouse.enabled:
                action = data["action"]
                
                # Move cursor
                if action in ("POINTER", "DRAGGING", "PINCHING"):
                    mouse.update_position(data["pointer_x"], data["pointer_y"])

                # Click events
                clk = data["click_event"]
                if clk == "left_click":
                    mouse.left_click()
                elif clk == "right_click":
                    mouse.right_click()
                elif clk == "left_down":
                    mouse.left_down()
                elif clk == "left_up":
                    mouse.left_up()

                # Scroll
                if data["scroll_delta"] != 0:
                    mouse.scroll(data["scroll_delta"])

            # Draw HUD
            annotated_frame = engine.draw_hud(frame, data)

            # Update Web Dashboard live stream
            dashboard.update_frame(annotated_frame)

            # Native OpenCV Desktop Window
            if show_window:
                cv2.imshow("AeroLock // AI Virtual Mouse & Security HUD", annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord('q')): # ESC or Q
                    break
                elif key == ord('m'):
                    mouse.enabled = not mouse.enabled
                    print(f"[*] Virtual Mouse: {'ENABLED' if mouse.enabled else 'DISABLED'}")
                elif key == ord('l'):
                    print("[*] Manual Lock triggered via hotkey.")
                    engine.is_locked = True
                    shield.activate()
                elif key == ord('u'):
                    print("[*] Manual Unlock triggered via hotkey.")
                    engine.unlock_manual()
                    shield.dismiss()

    except KeyboardInterrupt:
        print("\n[*] Shutting down AeroLock gracefully...")
    finally:
        if cap and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        shield.dismiss()
        mouse.release_all()
        print("[✓] AeroLock stopped cleanly.")

if __name__ == "__main__":
    main()
