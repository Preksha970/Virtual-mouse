"""
Flask Web Dashboard & API Server for AeroLock Virtual Mouse.
Streams live camera HUD, exposes REST API for telemetry & settings, and handles remote actions.
"""

from flask import Flask, render_template, Response, jsonify, request
import cv2
import json
import os
import threading

class WebDashboard:
    def __init__(self, engine, mouse, shield, sys_lock, config_path="config.json", host="127.0.0.1", port=5000):
        self.engine = engine
        self.mouse = mouse
        self.shield = shield
        self.sys_lock = sys_lock
        self.config_path = config_path
        self.host = host
        self.port = port
        
        self.latest_jpeg = None
        self.lock = threading.Lock()
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.app = Flask(
            __name__,
            template_folder=os.path.join(base_dir, "templates"),
            static_folder=os.path.join(base_dir, "static")
        )
        self._setup_routes()

    def update_frame(self, frame):
        """Encodes annotated OpenCV frame to JPEG for streaming."""
        success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if success:
            with self.lock:
                self.latest_jpeg = buffer.tobytes()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/frame.jpg")
        def snapshot():
            with self.lock:
                if self.latest_jpeg is None:
                    return ("No frame", 503)
                return Response(self.latest_jpeg, mimetype="image/jpeg")

        @self.app.route("/video_feed")
        def video_feed():
            def generate():
                import time
                while True:
                    time.sleep(0.033)  # Smooth 30 FPS stream without CPU lockup
                    with self.lock:
                        if self.latest_jpeg is None:
                            continue
                        frame_bytes = self.latest_jpeg
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

        @self.app.route("/api/status")
        def get_status():
            status = {
                "mouse_enabled": self.mouse.enabled,
                "is_locked": self.engine.is_locked,
                "lock_progress": round(self.engine.lock_progress, 2),
                "fps": int(self.engine.fps),
                "current_action": getattr(self.engine, "current_action", "IDLE"),
                "current_gesture": getattr(self.engine, "current_gesture", "None"),
                "unlock_step": self.engine.unlock_step,
                "unlock_target": self.engine.unlock_sequence[self.engine.unlock_step] if self.engine.unlock_step < len(self.engine.unlock_sequence) else "None",
                "cursor_pos": list(self.mouse.get_cursor_pos()),
                "entered_pin": getattr(self.engine, "entered_pin_digits", ""),
                "target_pin_len": len(getattr(self.engine, "unlock_pin", "1234")),
                "detected_digit_sign": getattr(self.engine, "current_sign_digit", None),
                "active_hover_key": getattr(self.engine, "active_hover_key", None)
            }
            return jsonify(status)

        @self.app.route("/api/config", methods=["GET"])
        def get_config():
            return jsonify(self.engine.config)

        @self.app.route("/api/config", methods=["POST"])
        def save_config():
            new_cfg = request.get_json() or {}
            self.engine.update_config(new_cfg)
            
            # Update mouse parameters
            if "smoothing" in new_cfg:
                self.mouse.smoothing = float(new_cfg["smoothing"])
            if "cursor_speed" in new_cfg:
                self.mouse.cursor_speed = float(new_cfg["cursor_speed"])
            if "scroll_sensitivity" in new_cfg:
                self.mouse.scroll_sensitivity = float(new_cfg["scroll_sensitivity"])
            if "active_margin_x" in new_cfg:
                self.mouse.margin_x = float(new_cfg["active_margin_x"])
            if "active_margin_y" in new_cfg:
                self.mouse.margin_y = float(new_cfg["active_margin_y"])
            if "mouse_enabled" in new_cfg:
                self.mouse.enabled = bool(new_cfg["mouse_enabled"])
            if "unlock_pin" in new_cfg:
                self.shield.unlock_pin = str(new_cfg["unlock_pin"])

            # Persist to disk
            try:
                with open(self.config_path, "w") as f:
                    json.dump(self.engine.config, f, indent=2)
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

            return jsonify({"status": "success", "config": self.engine.config})

        @self.app.route("/api/action/lock", methods=["POST"])
        def trigger_lock():
            self.engine.is_locked = True
            lock_type = self.engine.config.get("lock_system_type", "both")
            if lock_type in ("both", "shield_only"):
                self.shield.activate()
            if lock_type in ("both", "windows_only"):
                self.sys_lock.lock_windows_os()
            return jsonify({"status": "locked"})

        @self.app.route("/api/action/unlock", methods=["POST"])
        def trigger_unlock():
            self.engine.unlock_manual()
            self.shield.dismiss()
            return jsonify({"status": "unlocked"})

        @self.app.route("/api/action/toggle_mouse", methods=["POST"])
        def toggle_mouse():
            self.mouse.enabled = not self.mouse.enabled
            return jsonify({"mouse_enabled": self.mouse.enabled})

    def run(self):
        """Starts Flask in a background thread."""
        thread = threading.Thread(
            target=lambda: self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False),
            daemon=True
        )
        thread.start()
        print(f"[Web Dashboard] Live at http://{self.host}:{self.port}")
