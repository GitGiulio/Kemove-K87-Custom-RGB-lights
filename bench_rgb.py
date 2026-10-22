"""CPU/wall medians for local RGB work. No hardware writes; --capture is opt-in."""
import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

from PIL import Image, ImageGrab
from kemove_rgb import FrameEngine, colors_from_image, load_layout
from k87 import Keyboard, encode_frame
from settings import Settings


def measure(function, count, repeats=5):
    samples = []
    for _ in range(repeats):
        cpu, wall = time.process_time(), time.perf_counter()
        for _ in range(count):
            function()
        samples.append(((time.process_time() - cpu) * 1000 / count,
                        (time.perf_counter() - wall) * 1000 / count))
    return dict(cpu_ms=round(statistics.median(s[0] for s in samples), 6),
                wall_ms=round(statistics.median(s[1] for s in samples), 6))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    layout = load_layout()
    image = Image.new('RGB', (2560, 1440), (60, 100, 150))
    image.paste((150, 70, 20), (700, 0, 2560, 1440))
    results = {'size': image.size, 'repeats': 5}
    with tempfile.TemporaryDirectory() as folder:
        store = Settings(Path(folder) / 'settings.json')
        options = Settings().get()
        store.preview(options)
        results['configuration'] = {k: options[k] for k in ('fps', 'mode', 'smoothing', 'press_enabled')}
        results['settings_get'] = measure(store.get, 4000)
        if hasattr(store, 'snapshot'):
            revision, _ = store.snapshot()
            results['settings_snapshot_unchanged'] = measure(lambda: store.snapshot(revision), 1000000)
        for mode in ('average', 'spatial'):
            results[f'image_{mode}'] = measure(lambda: colors_from_image(image, layout, 1, mode), 40)
        for fps in (options['fps'], 30):
            opts = dict(options, fps=fps)
            engine = FrameEngine(lambda: image, layout)
            engine.frame(0, opts, set())
            # Repeated output between samples isolates stable-frame overhead.
            results[f'unchanged_frame_fps_{fps}'] = measure(lambda: engine.frame(.001, opts, {54}), 2000)
        tiny = image.resize((60, 20))
        engine = FrameEngine(lambda: tiny, layout)
        tick = 0
        def changing():
            nonlocal tick
            tick += 1
            return engine.frame(tick, options, {54})
        results['resampled_static_frame'] = measure(changing, 1000)
        alternate = Image.new('RGB', (60, 20), (20, 50, 200))
        engine = FrameEngine(lambda: tiny if tick % 2 else alternate, layout)
        results['changing_frame'] = measure(changing, 1000)
        colors = [(100, 50, 20)] * 126
        results['encode_frame'] = measure(lambda: encode_frame(colors), 4000)
        keyboard = Keyboard.__new__(Keyboard)
        keyboard.handle = 1
        keyboard._write = Mock()
        results['send_unchanged_fake_transport'] = measure(lambda: keyboard.send(colors), 4000)
        if args.capture:
            results['native_capture'] = measure(ImageGrab.grab, 10)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
