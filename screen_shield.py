"""
AeroShield: Fullscreen Holographic Screen Guard & Gesture Security Shield.
Runs as an isolated process to guarantee 100% thread safety and native OS window stability.
"""

import sys
import os
import json
import time
import subprocess
import tkinter as tk

class ScreenShield:
    def __init__(self, config=None, on_unlocked_callback=None):
        self.config = config or {}
        self.on_unlocked_callback = on_unlocked_callback
        self.process = None
        self.is_active = False
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.status_file = os.path.join(self.base_dir, ".shield_status.json")

    def activate(self):
        """Spawns the fullscreen lock screen in an isolated subprocess."""
        if self.is_active and self.process and self.process.poll() is None:
            return
            
        self.is_active = True
        
        # Write state config for subprocess
        shield_state = {
            "is_locked": True,
            "unlock_pin": str(self.config.get("unlock_pin", "1234")),
            "unlock_sequence": self.config.get("unlock_sequence", ["Victory", "Thumb_Up"])
        }
        try:
            with open(self.status_file, "w") as f:
                json.dump(shield_state, f)
        except Exception:
            pass

        cmd = [sys.executable, os.path.join(self.base_dir, "screen_shield.py"), "--run-gui"]
        try:
            self.process = subprocess.Popen(cmd)
        except Exception as e:
            print(f"[Error] Failed to spawn ScreenShield subprocess: {e}")

    def update_gesture_progress(self, current_step, step_name, progress_pct, status_text, entered_pin="", detected_sign=None):
        """Updates gesture status file so the shield HUD displays live scan progress."""
        if not self.is_active or not self.process or self.process.poll() is not None:
            return
            
        shield_state = {
            "is_locked": True,
            "current_step": current_step,
            "step_name": step_name,
            "progress_pct": progress_pct,
            "status_text": status_text,
            "entered_pin": entered_pin,
            "detected_sign": detected_sign,
            "unlock_pin": str(self.config.get("unlock_pin", "1234")),
            "unlock_sequence": self.config.get("unlock_sequence", ["Victory", "Thumb_Up"])
        }
        try:
            with open(self.status_file, "w") as f:
                json.dump(shield_state, f)
        except Exception:
            pass

    def dismiss(self):
        """Terminates lock screen process cleanly."""
        self.is_active = False
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        try:
            if os.path.exists(self.status_file):
                os.remove(self.status_file)
        except Exception:
            pass

        if self.on_unlocked_callback:
            try:
                self.on_unlocked_callback()
            except Exception:
                pass

    def check_subprocess_status(self):
        """Checks if user unlocked the shield via PIN or ESC from within the window."""
        if self.is_active and self.process:
            ret = self.process.poll()
            if ret is not None:
                # Subprocess exited (user entered correct PIN or pressed ESC)
                self.is_active = False
                self.process = None
                if self.on_unlocked_callback:
                    self.on_unlocked_callback()
                return "UNLOCKED"
        return "ACTIVE" if self.is_active else "IDLE"


# ==============================================================================
# SUBPROCESS GUI IMPLEMENTATION (Runs on its own Main Thread)
# ==============================================================================

class ShieldGUI:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.status_file = os.path.join(self.base_dir, ".shield_status.json")
        
        self.state = self._read_state()
        self.unlock_pin = self.state.get("unlock_pin", "1234")
        self.unlock_sequence = self.state.get("unlock_sequence", ["Victory", "Thumb_Up"])
        
        self.entered_pin = ""
        self.root = tk.Tk()
        self.root.title("AeroLock Security Shield")
        
        # Configure full screen, always on top, borderless
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#080c16")
        
        # Ignore Alt+F4
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Key bindings
        self.root.bind("<Escape>", lambda e: self._exit_unlocked())
        self.root.bind("<Key>", self._on_key_press)
        
        self._build_ui()
        self._poll_status_file()
        
    def _read_state(self):
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#080c16")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            main_frame,
            text="AEROLOCK // BIOMETRIC GESTURE SECURITY",
            font=("Consolas", 12, "bold"),
            fg="#00e5ff",
            bg="#080c16"
        ).pack(pady=(0, 10))

        tk.Label(
            main_frame,
            text="🔒",
            font=("Segoe UI Emoji", 48),
            fg="#ff0055",
            bg="#080c16"
        ).pack(pady=5)

        tk.Label(
            main_frame,
            text="LAPTOP SECURE LOCKED",
            font=("Segoe UI", 26, "bold"),
            fg="#ffffff",
            bg="#080c16"
        ).pack(pady=(0, 5))

        tk.Label(
            main_frame,
            text="Show Peace Sign (✌️) or Open Palm (🖐️) to Instant Unlock, or enter Air-PIN",
            font=("Segoe UI", 12),
            fg="#8892b0",
            bg="#080c16"
        ).pack(pady=(0, 25))

        content_frame = tk.Frame(main_frame, bg="#080c16")
        content_frame.pack(pady=10)

        # LEFT SIDE: Gesture Sequence Status
        seq_box = tk.LabelFrame(
            content_frame,
            text=" REQUIRED GESTURE SEQUENCE ",
            font=("Consolas", 10, "bold"),
            fg="#00e5ff",
            bg="#0f172a",
            padx=20,
            pady=15,
            bd=1,
            relief="solid"
        )
        seq_box.pack(side="left", padx=25, fill="y")

        self.step_frames = []
        gesture_icons = {
            "victory": "✌️  PEACE / VICTORY",
            "thumb_up": "👍  THUMBS UP",
            "open_palm": "🖐️  OPEN PALM",
            "pointing_up": "☝️  POINT UP"
        }

        for idx, gesture in enumerate(self.unlock_sequence):
            card = tk.Frame(seq_box, bg="#1e293b", padx=15, pady=10, bd=1, relief="ridge")
            card.pack(pady=8, fill="x")

            disp_name = gesture_icons.get(gesture.lower(), f"👋  {gesture.upper()}")
            lbl_step = tk.Label(
                card,
                text=f"Step {idx + 1}: {disp_name}",
                font=("Segoe UI", 11, "bold"),
                fg="#ffffff",
                bg="#1e293b",
                anchor="w"
            )
            lbl_step.pack(anchor="w")

            status_lbl = tk.Label(
                card,
                text="WAITING FOR SCAN...",
                font=("Consolas", 9),
                fg="#64748b",
                bg="#1e293b",
                anchor="w"
            )
            status_lbl.pack(anchor="w", pady=(2, 0))

            self.step_frames.append({
                "card": card,
                "label": lbl_step,
                "status": status_lbl,
                "gesture": gesture
            })

        self.status_var = tk.StringVar(value="CAMERA ACTIVATED: SHOW HAND TO BEGIN")
        self.lbl_status = tk.Label(
            seq_box,
            textvariable=self.status_var,
            font=("Consolas", 10, "bold"),
            fg="#00f5d4",
            bg="#0f172a",
            wraplength=260
        )
        self.lbl_status.pack(pady=(15, 5))

        # RIGHT SIDE: Air-PIN Keypad
        pin_box = tk.LabelFrame(
            content_frame,
            text=" AIR-PIN KEYPAD ",
            font=("Consolas", 10, "bold"),
            fg="#b5179e",
            bg="#0f172a",
            padx=20,
            pady=15,
            bd=1,
            relief="solid"
        )
        pin_box.pack(side="right", padx=25)

        self.pin_display_var = tk.StringVar(value="----")
        pin_entry_display = tk.Label(
            pin_box,
            textvariable=self.pin_display_var,
            font=("Consolas", 22, "bold"),
            fg="#00e5ff",
            bg="#070d18",
            width=12,
            pady=8,
            relief="sunken",
            bd=1
        )
        pin_entry_display.pack(pady=(0, 15))

        keypad_grid = tk.Frame(pin_box, bg="#0f172a")
        keypad_grid.pack()

        keys = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("CLR", 3, 0), ("0", 3, 1), ("OK", 3, 2),
        ]

        for text, r, c in keys:
            color = "#1e293b"
            fg_color = "#ffffff"
            if text == "OK":
                color = "#059669"
            elif text == "CLR":
                color = "#dc2626"

            btn = tk.Button(
                keypad_grid,
                text=text,
                font=("Consolas", 12, "bold"),
                width=4,
                height=1,
                bg=color,
                fg=fg_color,
                activebackground="#38bdf8",
                activeforeground="#000000",
                bd=0,
                command=lambda t=text: self._on_pin_button(t)
            )
            btn.grid(row=r, column=c, padx=5, pady=5)

        tk.Label(
            main_frame,
            text="Tip: Move cursor with your hand or type PIN directly. Press ESC to dismiss.",
            font=("Segoe UI", 10, "italic"),
            fg="#64748b",
            bg="#080c16"
        ).pack(pady=(25, 0))

    def _on_pin_button(self, key):
        if key == "CLR":
            self.entered_pin = ""
        elif key == "OK":
            self._verify_pin()
            return
        elif len(self.entered_pin) < 6:
            self.entered_pin += key

        mask = "●" * len(self.entered_pin)
        self.pin_display_var.set(mask.ljust(4, "-"))

        if len(self.entered_pin) == len(self.unlock_pin):
            self._verify_pin()

    def _verify_pin(self):
        if self.entered_pin == self.unlock_pin:
            self.status_var.set("PIN ACCEPTED! UNLOCKING...")
            self.root.after(400, self._exit_unlocked)
        else:
            self.status_var.set("INCORRECT PIN! TRY AGAIN")
            self.entered_pin = ""
            self.pin_display_var.set("----")

    def _on_key_press(self, event):
        if event.char and event.char.isdigit():
            self._on_pin_button(event.char)
        elif event.keysym in ("Return", "KP_Enter"):
            self._verify_pin()
        elif event.keysym == "BackSpace":
            self.entered_pin = self.entered_pin[:-1]
            mask = "●" * len(self.entered_pin)
            self.pin_display_var.set(mask.ljust(4, "-"))

    def _exit_unlocked(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _poll_status_file(self):
        """Continuously checks the status file for gesture updates from app.py."""
        state = self._read_state()
        if state:
            status_txt = state.get("status_text", "")
            if status_txt:
                self.status_var.set(status_txt)

            # Sync entered PIN from air-touch or numeric sign
            ext_pin = state.get("entered_pin")
            if ext_pin is not None and ext_pin != "":
                self.entered_pin = ext_pin
                mask = "●" * len(self.entered_pin)
                self.pin_display_var.set(mask.ljust(len(self.unlock_pin), "-"))
                if len(self.entered_pin) == len(self.unlock_pin):
                    self._verify_pin()

            curr_step = state.get("current_step", 0)
            prog = state.get("progress_pct", 0.0)

            for idx, frame_info in enumerate(self.step_frames):
                if idx < curr_step:
                    frame_info["card"].configure(bg="#064e3b")
                    frame_info["status"].configure(text="VERIFIED ✓", fg="#34d399")
                elif idx == curr_step:
                    frame_info["card"].configure(bg="#1e3a8a")
                    pct = int(prog * 100)
                    frame_info["status"].configure(text=f"SCANNING: {pct}%", fg="#38bdf8")
                else:
                    frame_info["card"].configure(bg="#1e293b")
                    frame_info["status"].configure(text="WAITING...", fg="#64748b")

        self.root.after(80, self._poll_status_file)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if "--run-gui" in sys.argv:
        gui = ShieldGUI()
        gui.run()
