"""
Ultra-low-latency Windows Mouse Controller with velocity-adaptive smoothing.
Uses native Win32 ctypes for sub-millisecond cursor positioning and clicks.
"""

import ctypes
from ctypes import wintypes
import time
import math

# Windows API constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x000A
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class MouseController:
    def __init__(self, config=None):
        self.user32 = ctypes.windll.user32
        
        # Enable DPI awareness so coordinate mapping matches physical monitor resolution
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
        except Exception:
            try:
                self.user32.SetProcessDPIAware()
            except Exception:
                pass
                
        self.screen_width = self.user32.GetSystemMetrics(0)
        self.screen_height = self.user32.GetSystemMetrics(1)
        
        self.config = config or {}
        self.smoothing = self.config.get("smoothing", 0.65)
        self.cursor_speed = self.config.get("cursor_speed", 1.25)
        self.margin_x = self.config.get("active_margin_x", 0.15)
        self.margin_y = self.config.get("active_margin_y", 0.15)
        self.scroll_sensitivity = self.config.get("scroll_sensitivity", 25)
        
        self.current_x = self.screen_width / 2
        self.current_y = self.screen_height / 2
        
        self.is_dragging = False
        self.last_click_time = 0
        self.enabled = True
        
    def get_screen_size(self):
        return self.screen_width, self.screen_height

    def get_cursor_pos(self):
        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def map_coords(self, norm_x, norm_y):
        """
        Maps normalized camera coordinates [0..1] with margin bounds to screen pixels.
        Camera is usually mirrored horizontally for natural user perception.
        """
        # Clamp within active tracking box
        clamped_x = max(self.margin_x, min(1.0 - self.margin_x, norm_x))
        clamped_y = max(self.margin_y, min(1.0 - self.margin_y, norm_y))
        
        # Scale to 0.0 - 1.0 within margins
        rel_x = (clamped_x - self.margin_x) / (1.0 - 2 * self.margin_x)
        rel_y = (clamped_y - self.margin_y) / (1.0 - 2 * self.margin_y)
        
        target_x = rel_x * self.screen_width
        target_y = rel_y * self.screen_height
        return target_x, target_y

    def update_position(self, norm_x, norm_y):
        """
        Calculates smoothed screen position with velocity-adaptive filtering.
        """
        if not self.enabled:
            return int(self.current_x), int(self.current_y)
            
        target_x, target_y = self.map_coords(norm_x, norm_y)
        
        # Compute movement delta
        dx = target_x - self.current_x
        dy = target_y - self.current_y
        dist = math.hypot(dx, dy)
        
        # Adaptive smoothing: if moving fast, reduce smoothing (high responsiveness).
        # If moving slow, increase smoothing (stable precision pointer).
        adaptive_factor = min(1.0, max(0.15, (dist / 120.0)))
        effective_alpha = (1.0 - self.smoothing) * (0.4 + 0.6 * adaptive_factor) * self.cursor_speed
        effective_alpha = min(0.95, max(0.05, effective_alpha))
        
        self.current_x += dx * effective_alpha
        self.current_y += dy * effective_alpha
        
        screen_x = int(round(self.current_x))
        screen_y = int(round(self.current_y))
        
        # Clamp to screen boundary
        screen_x = max(0, min(self.screen_width - 1, screen_x))
        screen_y = max(0, min(self.screen_height - 1, screen_y))
        
        self.user32.SetCursorPos(screen_x, screen_y)
        return screen_x, screen_y

    def left_down(self):
        if not self.enabled or self.is_dragging:
            return
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.is_dragging = True

    def left_up(self):
        if not self.enabled or not self.is_dragging:
            return
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_dragging = False

    def left_click(self):
        if not self.enabled:
            return
        now = time.time()
        if now - self.last_click_time < 0.15: # Debounce
            return
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.015)
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.last_click_time = now

    def right_click(self):
        if not self.enabled:
            return
        now = time.time()
        if now - self.last_click_time < 0.2:
            return
        self.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        self.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        self.last_click_time = now

    def double_click(self):
        if not self.enabled:
            return
        self.left_click()
        time.sleep(0.05)
        self.left_click()

    def scroll(self, delta_steps):
        if not self.enabled:
            return
        wheel_amount = int(delta_steps * self.scroll_sensitivity)
        self.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_amount, 0)

    def release_all(self):
        if self.is_dragging:
            self.left_up()
