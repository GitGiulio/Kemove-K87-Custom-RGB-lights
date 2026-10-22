"""Temporary key-down state for lighting only; no text, history, or key logging."""
import ctypes as c
import threading
import time


class PressedKeys:
    def __init__(self, layout, settings, stop):
        self.layout, self.settings, self.stop = layout, settings, stop
        self.lock = threading.Lock()
        self.active = set()
        self.user = c.WinDLL('user32', use_last_error=True)
        self.user.GetAsyncKeyState.argtypes = [c.c_int]
        self.user.GetAsyncKeyState.restype = c.c_short
        self.user.GetForegroundWindow.restype = c.c_void_p
        self.user.GetWindowThreadProcessId.argtypes = [c.c_void_p, c.c_void_p]
        self.user.GetKeyboardLayout.argtypes = [c.c_ulong]
        self.user.GetKeyboardLayout.restype = c.c_void_p
        self.user.MapVirtualKeyExW.argtypes = [c.c_uint, c.c_uint, c.c_void_p]
        self.thread = threading.Thread(target=self.run, name='K87 press state')

    def get(self):
        with self.lock:
            return set(self.active)

    def run(self):
        held, expiry, mapping, previous_layout = set(), {}, {}, None
        while not self.stop.is_set():
            revision, enabled = self.settings.read_flag('press_enabled')
            now = time.monotonic()
            if enabled:
                window = self.user.GetForegroundWindow()
                tid = self.user.GetWindowThreadProcessId(window, None)
                language = self.user.GetKeyboardLayout(tid)
                if language != previous_layout:
                    mapping = {k['index']: self.user.MapVirtualKeyExW(k['scan'], 3, language)
                               for k in self.layout if k.get('scan')}
                    # Pause and PrintScreen have unusual multi-byte physical sequences.
                    mapping.update({96: 0x13, 84: 0x2c})
                    previous_layout = language
                down = {index for index, vk in mapping.items() if vk and self.user.GetAsyncKeyState(vk) < 0}
                for index in down - held:
                    expiry[index] = now + .08
                held = down
                expiry = {index: until for index, until in expiry.items() if until > now}
                active = down | expiry.keys()
            else:
                held, expiry, active = set(), {}, set()
            with self.lock:
                self.active = set(active)
            # ponytail: polling avoids a global hook; taps shorter than 8 ms can be missed.
            if enabled:
                self.stop.wait(.008)
            else:
                self.settings.wait_for_change(revision, self.stop)
