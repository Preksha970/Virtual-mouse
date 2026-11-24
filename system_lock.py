"""
Windows Native System Lock and Keystroke Wake-up Automation.
Calls Win32 LockWorkStation and provides simulated wake-up credentials if configured.
"""

import ctypes
import time
import threading

class SystemLock:
    def __init__(self, config=None):
        self.config = config or {}
        self.user32 = ctypes.windll.user32
        
    def lock_windows_os(self):
        """
        Invokes native Windows LockWorkStation (Win + L behavior).
        """
        try:
            return bool(self.user32.LockWorkStation())
        except Exception as e:
            print(f"Error locking Windows OS: {e}")
            return False

    def simulate_wake_and_unlock(self, pin=None):
        """
        Wakes the Windows Lock Screen by sending Space/Enter and types PIN.
        Note: Windows Secure Desktop may restrict synthetic inputs depending on UAC/elevation,
        which is why AeroShield Fullscreen Guard is also provided as primary interactive lock.
        """
        pin = pin or self.config.get("unlock_pin", "")
        
        def _task():
            time.sleep(0.5)
            # Press Spacebar (VK_SPACE = 0x20) to dismiss lock screen wallpaper
            self.user32.keybd_event(0x20, 0, 0, 0)
            time.sleep(0.05)
            self.user32.keybd_event(0x20, 0, 2, 0)
            time.sleep(0.8)
            
            # Type PIN digits if provided
            if pin:
                for char in str(pin):
                    if char.isdigit():
                        vk = 0x30 + int(char) # 0x30 is '0'
                        self.user32.keybd_event(vk, 0, 0, 0)
                        time.sleep(0.04)
                        self.user32.keybd_event(vk, 0, 2, 0)
                        time.sleep(0.04)
                time.sleep(0.2)
                # Press Enter (VK_RETURN = 0x0D)
                self.user32.keybd_event(0x0D, 0, 0, 0)
                time.sleep(0.05)
                self.user32.keybd_event(0x0D, 0, 2, 0)
                
        threading.Thread(target=_task, daemon=True).start()
