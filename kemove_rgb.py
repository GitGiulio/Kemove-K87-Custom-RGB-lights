"""Screen-reactive lighting for the verified wired KEMOVE K87-1980."""
import argparse
import ctypes
import json
import math
from pathlib import Path
import sys
import time
import threading
from PIL import Image, ImageGrab
from k87 import Keyboard
from settings import Settings


def load_layout():
    keys = json.loads(Path(__file__).with_name('k87-layout.json').read_text(encoding='utf-8'))
    if len(keys) != 87 or len({k['index'] for k in keys}) != 87:
        raise ValueError('Invalid K87 layout')
    for key in keys:
        if type(key['index']) is not int or not 0 <= key['index'] < 126 or not 0 <= key['x'] <= 1 or not 0 <= key['y'] <= 1:
            raise ValueError('Invalid K87 key coordinates')
    return keys


def colors_from_image(image, layout, brightness, mode):
    if not 0 <= brightness <= 1:
        raise ValueError('Brightness must be between 0 and 1')
    image = image if image.mode == 'RGB' else image.convert('RGB')
    if mode == 'average':
        rgb = image.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        return [tuple(round(v * brightness) for v in rgb)] * 126
    if mode != 'spatial':
        raise ValueError('Mode must be spatial or average')
    # ponytail: 60x20 is enough for 87 LEDs; use GPU capture only if measured CPU usage warrants it.
    small = image.resize((60, 20), Image.Resampling.BOX)
    colors = [(0, 0, 0)] * 126
    for key in layout:
        rgb = small.getpixel((round(key['x'] * 59), round(key['y'] * 19)))
        colors[key['index']] = tuple(round(v * brightness) for v in rgb)
    return colors


def smooth_colors(previous, target, elapsed, smoothing):
    if previous is None or smoothing == 0:
        return target
    alpha = 1 - math.exp(-elapsed / smoothing)
    return [tuple(a + alpha * (b - a) for a, b in zip(old, new)) for old, new in zip(previous, target)]


def stream_step(keyboard, capture, layout, brightness, mode, previous, elapsed, smoothing):
    try:
        if not keyboard.is_open:
            keyboard.open()
        colors = colors_from_image(capture(), layout, brightness, mode)
        colors = smooth_colors(previous, colors, elapsed, smoothing)
        keyboard.send([tuple(round(value) for value in rgb) for rgb in colors])
        return colors
    except OSError:
        keyboard.close()
        raise


class FrameEngine:
    """Capture at the selected rate; render keepalives and key effects independently."""
    def __init__(self, capture, layout):
        self.capture, self.layout = capture, layout
        self.sample = None
        self.next_capture = 0
        self.capture_options = None
        self.previous = None
        self.previous_time = None
        self.target_key = None
        self.target = None
        self.base_key = None
        self.base = ()

    def frame(self, now, options, pressed, notifications=None):
        self.advance(now, options)
        return self.render(options, pressed, notifications)

    def advance(self, now, options):
        capture_options = (options['fps'], options['mode'])
        if self.sample is None or now >= self.next_capture or capture_options != self.capture_options:
            self.sample = colors_from_image(self.capture(), self.layout, 1, options['mode'])
            period = 1 / options['fps']
            if capture_options != self.capture_options:
                self.next_capture = now + period
            else:
                self.next_capture += (math.floor((now - self.next_capture) / period) + 1) * period
            self.capture_options = capture_options
        target_key = (self.sample, options['brightness'])
        if target_key != self.target_key:
            self.target = [tuple(v * options['brightness'] for v in rgb) for rgb in self.sample]
            self.target_key = target_key
        elapsed = max(0, now - self.previous_time) if self.previous_time is not None else 0
        self.previous = smooth_colors(self.previous, self.target, elapsed, options['smoothing'])
        self.previous_time = now

    def _base_colors(self, options):
        colors = [tuple(round(v) for v in rgb) for rgb in self.previous]
        for index, rule in options['exceptions'].items():
            if rule['mode'] == 'off':
                colors[int(index)] = (0, 0, 0)
            elif rule['mode'] == 'fixed':
                colors[int(index)] = tuple(round(v * options['brightness']) for v in rule['color'])
        return tuple(colors)

    def render(self, options, pressed, notifications=None):
        exceptions = tuple(sorted((index, rule['mode'], tuple(rule['color']))
                                  for index, rule in options['exceptions'].items()))
        base_key = (self.previous, options['brightness'], exceptions)
        if options['smoothing'] != 0 or self.base_key != base_key:
            self.base = self._base_colors(options)
            self.base_key = base_key
        colors = list(self.base)
        if options['press_enabled']:
            for index in pressed:
                colors[index] = tuple(options['press_color'])
        for index, color in (notifications or {}).items():
            colors[index] = tuple(color)
        return colors


def main(stop_event=None, status=print, settings=None, notifications=None):
    stop_event = stop_event or threading.Event()
    settings = settings or Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brightness', type=float, help='0..1, overrides saved setting')
    parser.add_argument('--fps', type=float, help='Screen samples per second: 0.125..30')
    parser.add_argument('--smoothing', type=float, help='Transition time in seconds, 0 disables smoothing')
    parser.add_argument('--mode', choices=['spatial', 'average'])
    parser.add_argument('--region', type=int, nargs=4, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'), help='Optional desktop rectangle, including a secondary monitor')
    parser.add_argument('--seconds', type=float, default=0, help='Stop after N seconds; 0 runs until Ctrl+C')
    parser.add_argument('--hid-dll', help='Override the installed OpenRGB HIDAPI DLL path')
    args = parser.parse_args()
    if not math.isfinite(args.seconds):
        parser.error('Numeric settings must be finite')
    if args.seconds < 0:
        parser.error('seconds must be >=0')
    options = settings.get()
    options.update({name: getattr(args, name) for name in ('brightness', 'fps', 'smoothing', 'mode') if getattr(args, name) is not None})
    settings.preview(options)
    if args.region and (args.region[2] <= args.region[0] or args.region[3] <= args.region[1]):
        parser.error('Region must have positive width and height')
    if sys.platform != 'win32':
        parser.error('This implementation supports Windows only')

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, 'Local\\KemoveK87ScreenRGB')
    mutex_error = ctypes.get_last_error()
    if not mutex:
        raise OSError('Could not create application lock')
    if mutex_error == 183:
        kernel.CloseHandle(mutex)
        status('KEMOVE RGB is already running. Stop its existing instance first.')
        return 1

    keyboard = None
    presses = None
    from notification_blinker import NotificationService
    notifications = notifications or NotificationService(settings, stop_event)
    frames = 0
    started = time.monotonic()
    waiting = False
    next_output = 0
    options_revision = -1
    try:
        # Match capture coordinates to physical pixels on displays with scaling.
        ctypes.windll.user32.SetProcessDPIAware()
        keyboard = Keyboard(args.hid_dll)
        layout = load_layout()
        capture = lambda: ImageGrab.grab(bbox=tuple(args.region) if args.region else None, all_screens=bool(args.region))
        engine = FrameEngine(capture, layout)
        from pressed_keys import PressedKeys
        presses = PressedKeys(layout, settings, stop_event)
        presses.thread.start()
        notifications.thread.start()
        status('KEMOVE RGB: starting lighting.')
        while not stop_event.is_set() and (not args.seconds or time.monotonic() - started < args.seconds):
            tick = time.monotonic()
            try:
                was_open = keyboard.is_open
                if not was_open:
                    keyboard.open()
                options_revision, updated = settings.snapshot(options_revision)
                if updated is not None:
                    options = updated
                engine.advance(tick, options)
                output_fps = max(10, options['fps'], 30 if options['press_enabled'] else 0)
                if tick >= next_output:
                    colors = engine.render(options, presses.get(), notifications.overlay(tick, options, options_revision))
                    keyboard.send(colors)
                    frames += 1
                    next_output = tick + 1 / output_fps
                if waiting or not was_open:
                    status('Connected. Screen matching is active.')
                waiting = False
                # Repeat unchanged colors as a keepalive; never queue stale frames.
                delay = max(0, min(next_output, engine.next_capture) - time.monotonic())
            except OSError as exc:
                keyboard.close()
                if not waiting:
                    status(f'Paused: {exc} Retrying every two seconds.')
                waiting = True
                engine = FrameEngine(capture, layout)
                next_output = 0
                delay = 2
            if args.seconds:
                delay = min(delay, max(0, args.seconds - (time.monotonic() - started)))
            stop_event.wait(delay)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        settings.wake_waiters()
        if presses and presses.thread.ident is not None:
            presses.thread.join()
        if notifications.thread.ident is not None:
            notifications.thread.join()
        if keyboard:
            keyboard.close()
        kernel.CloseHandle(mutex)
        elapsed = time.monotonic() - started
        status(f'Stopped: {frames} frames in {elapsed:.1f}s. The keyboard returns to its built-in lighting.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

