"""
Tkinter Smart Popup & Notification Manager
==========================================
Thread-safe, non-blocking modern Tkinter popup system for Virtual Mouse.

Key Features:
- Runs in a dedicated background daemon thread to prevent freezing the OpenCV
  webcam feed or causing mouse cursor stutter.
- Thread-safe queue communication (`queue.Queue`).
- Modern dark-themed card styling (Catppuccin Mocha palette) with accent indicators.
- Draggable frameless cards for seamless desktop ergonomics.
- Explicit "Close" button and top-right "✕" button on all popups.
- Singleton window design: NEVER spawns duplicate windows; smoothly updates in-place.
- Auto-dismisses absence notifications as soon as the user's face is re-detected.
- Actionable buttons (Close, "🔒 Lock Screen Now" for 3-minute extended absence).
- Welcome back toast notification with auto-dismiss timer (3 seconds).
- Camera disconnect alert handling with cooldown protection against repeated popups.
- Zero frame or image storage: strictly UI rendering.
"""

import threading
import queue
import time
import os
import ctypes
import tkinter as tk
from tkinter import ttk


class PopupManager:
    """
    Manages display, update, and dismissal of modern Tkinter notification popups.
    Thread-safe API designed for real-time OpenCV loops.
    """

    def __init__(self):
        self.cmd_queue = queue.Queue()
        self.tk_ready = threading.Event()
        self.root = None

        # Windows
        self.absence_window = None
        self.welcome_window = None
        self.camera_error_window = None

        # Cooldown & state tracking
        self.last_shown_stage = None
        self.last_dismissed_time = 0.0
        self.last_camera_error_time = 0.0

        # Start Tkinter daemon thread
        self.thread = threading.Thread(target=self._run_tk_thread, daemon=True)
        self.thread.start()
        self.tk_ready.wait(timeout=3.0)

    # --------------------------------------------------------------------------
    # Public Thread-Safe API (Called from main OpenCV / Gesture loop)
    # --------------------------------------------------------------------------

    def show_absence_popup(self, stage: int, message: str, show_lock_option: bool = False):
        """Displays or updates the absence popup for the given stage with cooldown protection."""
        # Cooldown: if user explicitly closed the popup within the last 3 seconds, avoid immediate re-spawn
        now = time.time()
        if now - self.last_dismissed_time < 3.0:
            return

        self.cmd_queue.put({
            "action": "show_away",
            "stage": stage,
            "message": message,
            "show_lock": show_lock_option
        })

    def dismiss_absence_popup(self):
        """Immediately closes any active absence popup (e.g., when face is re-detected)."""
        self.cmd_queue.put({"action": "dismiss_away"})

    def show_welcome_back(self, message: str = "Welcome back! Your virtual mouse is ready!", duration: float = 3.0):
        """Displays a welcome back toast notification that auto-dismisses."""
        self.cmd_queue.put({
            "action": "show_welcome",
            "message": message,
            "duration": duration
        })

    def show_camera_error(self, message: str = "Webcam feed disconnected or unavailable!", cooldown_sec: float = 10.0):
        """Displays an alert notifying that the camera has disconnected with anti-spam cooldown."""
        now = time.time()
        if now - self.last_camera_error_time < cooldown_sec:
            return
        self.last_camera_error_time = now

        self.cmd_queue.put({
            "action": "show_camera_error",
            "message": message
        })

    def close_all(self):
        """Shuts down all active popups and stops the Tkinter loop."""
        self.cmd_queue.put({"action": "quit"})

    # --------------------------------------------------------------------------
    # Tkinter Internal Thread Loop & Queue Processing
    # --------------------------------------------------------------------------

    def _run_tk_thread(self):
        self.root = tk.Tk()
        # Keep hidden root window for event processing
        self.root.withdraw()
        self.tk_ready.set()

        # Start checking incoming queue
        self.root.after(40, self._process_queue)
        try:
            self.root.mainloop()
        except Exception:
            pass

    def _process_queue(self):
        """Processes pending UI commands from the queue without blocking."""
        try:
            while not self.cmd_queue.empty():
                cmd = self.cmd_queue.get_nowait()
                action = cmd.get("action")

                if action == "show_away":
                    self._handle_show_away(cmd)
                elif action == "dismiss_away":
                    self._handle_dismiss_away()
                elif action == "show_welcome":
                    self._handle_show_welcome(cmd)
                elif action == "show_camera_error":
                    self._handle_show_camera_error(cmd)
                elif action == "quit":
                    self._handle_quit()
                    return
        except Exception:
            pass

        if self.root:
            self.root.after(40, self._process_queue)

    # --------------------------------------------------------------------------
    # Popup UI Implementation
    # --------------------------------------------------------------------------

    def _handle_show_away(self, cmd):
        stage = cmd.get("stage", 10)
        message = cmd.get("message", "")
        show_lock = cmd.get("show_lock", False)

        # Stage titles & accent themes
        stage_themes = {
            10: ("👀", "Hey! Still There?", "#6366f1"),      # Indigo
            30: ("☕", "Taking a Break?", "#8b5cf6"),        # Purple
            60: ("⏳", "Virtual Mouse Waiting", "#ec4899"),   # Pink
            180: ("🔒", "Extended Absence Alert", "#ef4444") # Red
        }
        icon, title, accent_color = stage_themes.get(stage, ("🔔", "User Presence Alert", "#6366f1"))

        # If absence window already exists, update in-place to avoid duplicate windows
        if self.absence_window and tk.Toplevel.winfo_exists(self.absence_window):
            self._update_existing_away_window(stage, title, message, accent_color, show_lock)
            return

        # Otherwise create a new modern top-level card window
        win = tk.Toplevel(self.root)
        self.absence_window = win
        win.title(title)
        win.attributes("-topmost", True)
        win.configure(bg="#181825")
        win.resizable(False, False)

        # Frameless modern card styling
        win.overrideredirect(True)

        # Outer card frame with accent border
        card = tk.Frame(win, bg="#1e1e2e", bd=1, relief="solid", highlightthickness=1, highlightbackground=accent_color)
        card.pack(fill="both", expand=True)

        # Top Accent strip
        accent_strip = tk.Frame(card, bg=accent_color, height=5)
        accent_strip.pack(fill="x", side="top")

        content_box = tk.Frame(card, bg="#1e1e2e", padx=20, pady=16)
        content_box.pack(fill="both", expand=True)

        # Header Row (Icon + Title + Top-Right Close '✕' Button)
        header_frame = tk.Frame(content_box, bg="#1e1e2e")
        header_frame.pack(fill="x", pady=(0, 10))

        lbl_icon = tk.Label(header_frame, text=icon, font=("Segoe UI Emoji", 20), bg="#1e1e2e", fg="#ffffff")
        lbl_icon.pack(side="left", padx=(0, 10))

        lbl_title = tk.Label(header_frame, text=title, font=("Segoe UI", 13, "bold"), bg="#1e1e2e", fg="#ffffff")
        lbl_title.pack(side="left", anchor="w")

        btn_x = tk.Button(header_frame, text="✕", font=("Segoe UI", 10, "bold"),
                          bg="#1e1e2e", fg="#6c7086", activebackground="#1e1e2e", activeforeground="#ffffff",
                          bd=0, relief="flat", cursor="hand2",
                          command=self._handle_dismiss_away)
        btn_x.pack(side="right")

        # Message label
        lbl_msg = tk.Label(content_box, text=message, font=("Segoe UI", 10), bg="#1e1e2e", fg="#cdd6f4",
                           wraplength=340, justify="left")
        lbl_msg.pack(fill="x", pady=(0, 14))

        # Buttons Frame
        btn_frame = tk.Frame(content_box, bg="#1e1e2e")
        btn_frame.pack(fill="x", side="bottom")

        # Optional Lock Screen button (Stage 4: 180s)
        if show_lock:
            btn_lock = tk.Button(btn_frame, text="🔒 Lock Screen Now", font=("Segoe UI", 9, "bold"),
                                 bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
                                 relief="flat", padx=12, pady=6, cursor="hand2",
                                 command=self._action_lock_screen)
            btn_lock.pack(side="left", padx=(0, 10))

        # Standard Close button
        btn_close = tk.Button(btn_frame, text="Close", font=("Segoe UI", 9, "bold"),
                              bg="#313244", fg="#cdd6f4", activebackground="#45475a", activeforeground="#ffffff",
                              relief="flat", padx=16, pady=6, cursor="hand2",
                              command=self._handle_dismiss_away)
        btn_close.pack(side="right")

        # Enable dragging window
        self._make_draggable(card, win)
        self._make_draggable(header_frame, win)

        # Center window on screen
        self._center_window(win, width=390, height=165 if show_lock else 145)

        # Store references for in-place updates
        win._lbl_icon = lbl_icon
        win._lbl_title = lbl_title
        win._lbl_msg = lbl_msg
        win._accent_strip = accent_strip
        win._card = card
        win._btn_frame = btn_frame

    def _update_existing_away_window(self, stage, title, message, accent_color, show_lock):
        """Updates text and buttons on an already open window without duplicating it."""
        try:
            win = self.absence_window
            stage_icons = {"10": "👀", "30": "☕", "60": "⏳", "180": "🔒"}
            win._lbl_icon.config(text=stage_icons.get(str(stage), "🔔"))
            win._lbl_title.config(text=title)
            win._lbl_msg.config(text=message)
            win._accent_strip.config(bg=accent_color)
            win._card.config(highlightbackground=accent_color)

            # Check if lock button should be added (for 180s stage)
            if show_lock and not getattr(win, '_has_lock_btn', False):
                btn_lock = tk.Button(win._btn_frame, text="🔒 Lock Screen Now", font=("Segoe UI", 9, "bold"),
                                     bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
                                     relief="flat", padx=12, pady=6, cursor="hand2",
                                     command=self._action_lock_screen)
                btn_lock.pack(side="left", padx=(0, 10))
                win._has_lock_btn = True
                self._center_window(win, width=390, height=165)
        except Exception:
            pass

    def _handle_dismiss_away(self):
        """Closes active absence window and records dismissal time for cooldown."""
        self.last_dismissed_time = time.time()
        if self.absence_window and tk.Toplevel.winfo_exists(self.absence_window):
            try:
                self.absence_window.destroy()
            except Exception:
                pass
        self.absence_window = None

    def _handle_show_welcome(self, cmd):
        """Displays an attractive welcome back toast that automatically dismisses."""
        # Immediately dismiss any lingering away popup
        self._handle_dismiss_away()

        message = cmd.get("message", "Welcome back! Your virtual mouse is ready!")
        duration_ms = int(cmd.get("duration", 3.0) * 1000)

        # Close existing welcome window if open
        if self.welcome_window and tk.Toplevel.winfo_exists(self.welcome_window):
            try:
                self.welcome_window.destroy()
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        self.welcome_window = win
        win.title("Welcome Back")
        win.attributes("-topmost", True)
        win.configure(bg="#181825")
        win.resizable(False, False)
        win.overrideredirect(True)

        card = tk.Frame(win, bg="#1e1e2e", bd=1, relief="solid", highlightthickness=1, highlightbackground="#a6e3a1")
        card.pack(fill="both", expand=True)

        accent = tk.Frame(card, bg="#a6e3a1", height=4)  # Emerald green accent
        accent.pack(fill="x", side="top")

        content = tk.Frame(card, bg="#1e1e2e", padx=18, pady=12)
        content.pack(fill="both", expand=True)

        row = tk.Frame(content, bg="#1e1e2e")
        row.pack(fill="x")

        lbl_icon = tk.Label(row, text="🎉", font=("Segoe UI Emoji", 18), bg="#1e1e2e")
        lbl_icon.pack(side="left", padx=(0, 10))

        text_frame = tk.Frame(row, bg="#1e1e2e")
        text_frame.pack(side="left", fill="x", expand=True)

        lbl_title = tk.Label(text_frame, text="User Returned", font=("Segoe UI", 11, "bold"), bg="#1e1e2e", fg="#a6e3a1")
        lbl_title.pack(anchor="w")

        lbl_msg = tk.Label(text_frame, text=message, font=("Segoe UI", 9), bg="#1e1e2e", fg="#cdd6f4")
        lbl_msg.pack(anchor="w")

        # Top-right quick close button
        btn_x = tk.Button(row, text="✕", font=("Segoe UI", 9, "bold"),
                          bg="#1e1e2e", fg="#6c7086", activebackground="#1e1e2e", activeforeground="#ffffff",
                          bd=0, relief="flat", cursor="hand2",
                          command=lambda: self._safe_destroy(win))
        btn_x.pack(side="right", padx=(8, 0))

        self._make_draggable(card, win)

        # Center near top of screen for notification toast feel
        self._center_window(win, width=390, height=80, y_offset=80)

        # Auto-dismiss after duration
        self.root.after(duration_ms, lambda: self._safe_destroy(win))

    def _handle_show_camera_error(self, cmd):
        """Displays webcam disconnect alert with Close button."""
        message = cmd.get("message", "Webcam feed was disconnected or is unavailable!")

        if self.camera_error_window and tk.Toplevel.winfo_exists(self.camera_error_window):
            return

        win = tk.Toplevel(self.root)
        self.camera_error_window = win
        win.title("Camera Error")
        win.attributes("-topmost", True)
        win.configure(bg="#181825")
        win.resizable(False, False)
        win.overrideredirect(True)

        card = tk.Frame(win, bg="#1e1e2e", bd=1, relief="solid", highlightthickness=1, highlightbackground="#f38ba8")
        card.pack(fill="both", expand=True)

        accent = tk.Frame(card, bg="#f38ba8", height=4)  # Coral red
        accent.pack(fill="x", side="top")

        content = tk.Frame(card, bg="#1e1e2e", padx=18, pady=14)
        content.pack(fill="both", expand=True)

        row = tk.Frame(content, bg="#1e1e2e")
        row.pack(fill="x", pady=(0, 10))

        lbl_icon = tk.Label(row, text="⚠️", font=("Segoe UI Emoji", 20), bg="#1e1e2e")
        lbl_icon.pack(side="left", padx=(0, 10))

        text_frame = tk.Frame(row, bg="#1e1e2e")
        text_frame.pack(side="left", fill="x", expand=True)

        lbl_title = tk.Label(text_frame, text="Webcam Unavailable", font=("Segoe UI", 12, "bold"), bg="#1e1e2e", fg="#f38ba8")
        lbl_title.pack(anchor="w")

        lbl_msg = tk.Label(text_frame, text=message, font=("Segoe UI", 9), bg="#1e1e2e", fg="#cdd6f4", wraplength=280)
        lbl_msg.pack(anchor="w")

        btn_close = tk.Button(content, text="Close", font=("Segoe UI", 9, "bold"),
                              bg="#313244", fg="#cdd6f4", activebackground="#45475a", activeforeground="#ffffff",
                              relief="flat", padx=14, pady=5, cursor="hand2",
                              command=lambda: self._safe_destroy(win))
        btn_close.pack(side="right")

        self._make_draggable(card, win)
        self._center_window(win, width=390, height=125)

    # --------------------------------------------------------------------------
    # Utility & Desktop Actions
    # --------------------------------------------------------------------------

    def _action_lock_screen(self):
        """Locks the Windows workstation immediately."""
        self._handle_dismiss_away()
        try:
            # Native Windows LockWorkStation API
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            try:
                os.system("rundll32.exe user32.dll,LockWorkStation")
            except Exception:
                pass

    def _make_draggable(self, widget, win):
        """Allows user to drag frameless window across monitors."""
        def start_move(event):
            win._drag_x = event.x
            win._drag_y = event.y

        def do_move(event):
            deltax = event.x - win._drag_x
            deltay = event.y - win._drag_y
            x = win.winfo_x() + deltax
            y = win.winfo_y() + deltay
            win.geometry(f"+{x}+{y}")

        widget.bind("<ButtonPress-1>", start_move)
        widget.bind("<B1-Motion>", do_move)

    def _center_window(self, win, width=390, height=150, y_offset=None):
        """Centers the popup window horizontally on the primary monitor."""
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w - width) // 2
        y = y_offset if y_offset is not None else (screen_h - height) // 3
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _safe_destroy(self, win):
        """Safely destroys a Tkinter window if still active."""
        try:
            if win and tk.Toplevel.winfo_exists(win):
                win.destroy()
        except Exception:
            pass

    def _handle_quit(self):
        """Closes all popups and stops the mainloop cleanly."""
        self._handle_dismiss_away()
        if self.welcome_window:
            self._safe_destroy(self.welcome_window)
        if self.camera_error_window:
            self._safe_destroy(self.camera_error_window)
        if self.root:
            self.root.quit()
