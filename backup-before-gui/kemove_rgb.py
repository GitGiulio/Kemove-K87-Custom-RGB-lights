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
    if mode == 'average':
        rgb = image.convert('RGB').resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        return [tuple(round(v * brightness) for v in rgb)] * 126
    if mode != 'spatial':
        raise ValueError('Mode must be spatial or average')
    # ponytail: 60x20 is enough for 87 LEDs; use GPU capture only if measured CPU usage warrants it.
    small = image.convert('RGB').resize((60, 20), Image.Resampling.BOX)
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


def main(stop_event=None, status=print):
    stop_event = stop_event or threading.Event()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brightness', type=float, default=0.35, help='0..1, default 0.35')
    parser.add_argument('--fps', type=float, default=10, help='1..20, default 10')
    parser.add_argument('--smoothing', type=float, default=0.08, help='Transition time in seconds, 0 disables smoothing')
    parser.add_argument('--mode', choices=['spatial', 'average'], default='spatial')
    parser.add_argument('--region', type=int, nargs=4, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'), help='Optional desktop rectangle, including a secondary monitor')
    parser.add_argument('--seconds', type=float, default=0, help='Stop after N seconds; 0 runs until Ctrl+C')
    parser.add_argument('--hid-dll', help='Override the installed OpenRGB HIDAPI DLL path')
    args = parser.parse_args()
    if not all(math.isfinite(v) for v in [args.brightness, args.fps, args.smoothing, args.seconds]):
        parser.error('Numeric settings must be finite')
    if not 0 <= args.brightness <= 1 or not 1 <= args.fps <= 20 or not 0 <= args.smoothing <= 2 or args.seconds < 0:
        parser.error('brightness: 0..1, fps: 1..20, smoothing: 0..2, seconds: >=0')
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
    frames = 0
    started = time.monotonic()
    previous_time = started
    previous = None
    waiting = False
    try:
        # Match capture coordinates to physical pixels on displays with scaling.
        ctypes.windll.user32.SetProcessDPIAware()
        keyboard = Keyboard(args.hid_dll)
        layout = load_layout()
        capture = lambda: ImageGrab.grab(bbox=tuple(args.region) if args.region else None, all_screens=bool(args.region))
        status(f'KEMOVE RGB: {args.mode}, brightness {args.brightness:.0%}, {args.fps:g} FPS.')
        while not stop_event.is_set() and (not args.seconds or time.monotonic() - started < args.seconds):
            tick = time.monotonic()
            try:
                was_open = keyboard.is_open
                previous = stream_step(keyboard, capture, layout, args.brightness, args.mode, previous,
                                       max(tick - previous_time, 1 / args.fps), args.smoothing)
                if waiting or not was_open:
                    status('Connected. Screen matching is active.')
                waiting = False
                frames += 1
                previous_time = tick
                # Repeat unchanged colors as a keepalive; never queue stale frames.
                delay = max(0, 1 / args.fps - (time.monotonic() - tick))
            except OSError as exc:
                if not waiting:
                    status(f'Paused: {exc} Retrying every two seconds.')
                waiting = True
                previous = None
                delay = 2
            if args.seconds:
                delay = min(delay, max(0, args.seconds - (time.monotonic() - started)))
            stop_event.wait(delay)
    except KeyboardInterrupt:
        pass
    finally:
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

