import asyncio
import math
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from kemove_rgb import FrameEngine, colors_from_image, load_layout, smooth_colors
from k87 import Keyboard, encode_frame
from settings import Settings, defaults
from pressed_keys import PressedKeys
from notification_blinker import NotificationService
import kemove_rgb


class ImageTests(unittest.TestCase):
    def test_rgb_input_is_not_converted_or_copied(self):
        image = Image.new('RGB', (101, 61), (20, 40, 60))
        with patch.object(image, 'convert', wraps=image.convert) as convert:
            for mode in ('average', 'spatial'):
                colors_from_image(image, load_layout(), .36, mode)
        convert.assert_not_called()

    def test_non_rgb_and_odd_images_keep_exact_colors(self):
        image = Image.new('RGB', (101, 61), (23, 47, 171))
        image.paste((193, 14, 35), (37, 13, 101, 61))
        for mode in ('RGB', 'L', 'RGBA', 'P'):
            source = image.convert(mode)
            original = source.tobytes()
            for lighting in ('average', 'spatial'):
                for brightness in (0, .36, 1):
                    with self.subTest(mode=mode, lighting=lighting, brightness=brightness):
                        expected = colors_from_image(source.convert('RGB'), load_layout(), brightness, lighting)
                        self.assertEqual(colors_from_image(source, load_layout(), brightness, lighting), expected)
            self.assertEqual(source.tobytes(), original)


class CacheTests(unittest.TestCase):
    def test_unchanged_zero_smoothing_reuses_base(self):
        opts = defaults(); opts.update(smoothing=0, fps=.125)
        engine = FrameEngine(lambda: Image.new('RGB', (60,20), (100,50,20)), load_layout())
        engine.frame(0, opts, set())
        with patch.object(engine, '_base_colors', wraps=engine._base_colors) as build:
            for i in range(1, 5): engine.frame(i/10, opts, set())
            build.assert_not_called()

    def test_base_cache_invalidates_and_is_not_mutated(self):
        opts = defaults(); opts.update(smoothing=0, fps=.125, press_enabled=True)
        capture = Mock(return_value=Image.new('RGB', (60,20), (100,50,20)))
        engine = FrameEngine(capture, load_layout())
        base = engine.frame(0, opts, set())
        modified = engine.frame(.1, opts, {54}, {36:(1,2,3)})
        modified[0] = (0,0,0)
        self.assertEqual(engine.frame(.2, opts, set()), base)
        opts['brightness'] = .7
        self.assertEqual(engine.frame(.3, opts, set())[0], (70,35,14))
        opts['exceptions']['0'] = dict(mode='off', color=[0,0,0])
        self.assertEqual(engine.frame(.4, opts, set())[0], (0,0,0))
        opts['exceptions'].clear()
        capture.return_value = Image.new('RGB', (60,20), (20,40,60))
        self.assertEqual(engine.frame(8, opts, set())[0], (14,28,42))
        opts['mode'] = 'average'
        self.assertEqual(engine.frame(8.1, opts, set())[6], (14,28,42))

    def test_packet_cache_reuses_bytes_but_still_writes(self):
        keyboard = Keyboard.__new__(Keyboard); keyboard.handle = 1; keyboard._write = Mock()
        colors = [(1,2,3)] * 126
        keyboard.send(colors); keyboard.send(list(colors))
        self.assertEqual(keyboard._write.call_count, 2)
        self.assertIs(keyboard._write.call_args_list[0].args[0], keyboard._write.call_args_list[1].args[0])
        self.assertEqual(keyboard._write.call_args.args[0], encode_frame(colors))
        for value in (True, 1.0, -1, 256):
            invalid = [(value,2,3)] * 126
            with self.assertRaises(ValueError): keyboard.send(invalid)
        with self.assertRaises(ValueError): keyboard.send(colors[:-1])
        keyboard.api = Mock()
        keyboard.close()
        self.assertIsNone(keyboard.cached_colors)
        keyboard.handle = 2
        keyboard.send(colors)
        self.assertIsNot(keyboard._write.call_args_list[0].args[0], keyboard._write.call_args.args[0])


class SchedulingTests(unittest.TestCase):
    def test_main_only_renders_when_report_is_due(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Settings(Path(folder) / 'settings.json')
            options = store.get(); options.update(fps=7, smoothing=0)
            store.preview(options)
            stop = threading.Event()
            clock = [0.0]
            keyboard = Mock(); keyboard.is_open = True
            notifications = Mock(); notifications.thread.ident = None
            notifications.overlay.return_value = {}
            presses = Mock(); presses.thread.ident = None; presses.get.return_value = set()
            times = []
            def wait(delay):
                times.append(delay)
                clock[0] += delay
                if clock[0] > .5: stop.set()
            stop.wait = wait
            with patch('sys.argv', ['kemove_rgb.py']), patch.object(kemove_rgb.ctypes, 'get_last_error', return_value=0), \
                 patch.object(kemove_rgb, 'Keyboard', return_value=keyboard), \
                 patch('pressed_keys.PressedKeys', return_value=presses), \
                 patch.object(kemove_rgb.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(kemove_rgb, 'ScreenCapture', return_value=Mock(return_value=Image.new('RGB',(60,20)))), \
                 patch.object(FrameEngine, 'render', autospec=True, wraps=FrameEngine.render) as render:
                # autospec+wraps returns a mock; these checks concern loop scheduling, not pixels.
                kemove_rgb.main(stop_event=stop, settings=store, status=Mock(), notifications=notifications)
            self.assertEqual(render.call_count, keyboard.send.call_count)
            self.assertEqual(notifications.overlay.call_count, keyboard.send.call_count)
            self.assertLess(render.call_count, len(times))
            self.assertTrue(all(delay > 0 for delay in times))

    def test_advance_without_render_preserves_exact_reference(self):
        for fps in (.125, 5, 7, 20, 30):
            for smoothing in (0, .08, 2):
                opts = defaults(); opts.update(fps=fps, smoothing=smoothing, press_enabled=True)
                images = [Image.new('RGB', (60,20), rgb) for rgb in ((100,30,0),(0,90,255),(10,80,20))]
                def capture_factory():
                    count = [0]
                    def capture():
                        image = images[count[0] % 3]; count[0] += 1
                        return image
                    return capture
                engine = FrameEngine(capture_factory(), load_layout())
                reference = ReferenceEngine(capture_factory(), load_layout())
                for n in range(100):
                    now = n * .017
                    if n == 30: opts['brightness'] = .61
                    if n == 50: opts['exceptions']['0'] = dict(mode='off', color=[0,0,0])
                    pressed = {54} if n % 3 else set()
                    overlay = {36: (255,0,0)} if n % 5 else {}
                    expected = reference.frame(now, opts, pressed, overlay)
                    engine.advance(now, opts)
                    if n % 2 == 0:
                        self.assertEqual(engine.render(opts, pressed, overlay), expected)
                self.assertEqual(engine.next_capture, reference.next_capture)

    def test_late_capture_skips_old_samples(self):
        opts = defaults(); opts.update(fps=7)
        capture = Mock(return_value=Image.new('RGB',(60,20)))
        engine = FrameEngine(capture, load_layout())
        engine.advance(0, opts); engine.advance(2.01, opts)
        self.assertEqual(capture.call_count, 2)
        self.assertGreater(engine.next_capture, 2.01)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Settings(Path(self.folder.name) / 'settings.json')

    def test_change_before_wait_is_not_lost(self):
        revision, _ = self.store.snapshot()
        options = self.store.get(); options['press_enabled'] = True
        self.store.preview(options)
        thread = threading.Thread(target=self.store.wait_for_change, args=(revision, threading.Event()), daemon=True)
        thread.start(); thread.join(.5)
        self.assertFalse(thread.is_alive())

    def test_stale_render_settings_cannot_undo_new_notification_epoch(self):
        from notification_blinker import APP_CATALOG
        revision, old = self.store.snapshot()
        service = NotificationService(self.store, threading.Event(), foreground=lambda: None)
        service.tick(10, 100, [])
        newer = self.store.get(); newer['notifications_enabled'] = True
        self.store.preview(newer)
        service.tick(11, 101, [])
        service.tick(12, 102, [(APP_CATALOG['chatgpt']['aumid'], 1, 101.5)])
        self.assertEqual(service.overlay(12, old, revision), {54: (255,0,0)})
        self.assertEqual(service.enabled_since['chatgpt'], 101)

    def test_disabled_workers_park_and_shutdown_wakes_them(self):
        stop = threading.Event()
        press_parked, notify_parked = threading.Event(), threading.Event()
        original = getattr(self.store, 'wait_for_change', None)
        def wait(revision, event):
            (press_parked if threading.current_thread().name == 'K87 press state' else notify_parked).set()
            original(revision, event)
        foreground = Mock(return_value=None)
        presses = PressedKeys(load_layout(), self.store, stop)
        presses.user = Mock()
        service = NotificationService(self.store, stop, foreground=foreground)
        try:
            with patch.object(self.store, 'wait_for_change', side_effect=wait, create=True), patch('notification_blinker.WinRTSource') as source:
                presses.thread.start(); service.thread.start()
                self.assertTrue(press_parked.wait(.5))
                self.assertTrue(notify_parked.wait(.5))
                foreground.assert_not_called(); source.assert_not_called()
                presses.user.GetAsyncKeyState.assert_not_called()
        finally:
            stop.set()
            if hasattr(self.store, 'wake_waiters'): self.store.wake_waiters()
            presses.thread.join(1); service.thread.join(1)
        self.assertFalse(presses.thread.is_alive())
        self.assertFalse(service.thread.is_alive())

    def test_preview_and_cancel_wake_parked_worker(self):
        stop = threading.Event()
        changed = threading.Event()
        revision, _ = self.store.snapshot()
        def waiter():
            self.store.wait_for_change(revision, stop)
            changed.set()
        worker = threading.Thread(target=waiter, daemon=True)
        worker.start()
        draft = self.store.get(); draft['press_enabled'] = True
        self.store.preview(draft)
        self.assertTrue(changed.wait(.5)); worker.join(.5)
        revision, _ = self.store.snapshot()
        changed.clear(); worker = threading.Thread(target=waiter, daemon=True); worker.start()
        self.store.cancel()
        self.assertTrue(changed.wait(.5)); worker.join(.5)

    def test_reenable_while_query_cancels_does_not_park_at_new_revision(self):
        stop = threading.Event()
        first, second = threading.Event(), threading.Event()
        options = self.store.get(); options['notifications_enabled'] = True
        self.store.preview(options)
        service = NotificationService(self.store, stop, foreground=lambda: None)
        calls = []
        class Source:
            async def snapshot(inner):
                calls.append(1)
                if len(calls) == 1:
                    first.set()
                    try:
                        await asyncio.sleep(60)
                    finally:
                        options = self.store.get(); options['notifications_enabled'] = True
                        self.store.preview(options)
                        service.overlay(1)
                else:
                    second.set()
                return []
        try:
            with patch('notification_blinker.WinRTSource', Source), patch('notification_blinker.FOREGROUND_SECONDS', .01):
                service.thread.start()
                self.assertTrue(first.wait(1))
                options = self.store.get(); options['notifications_enabled'] = False
                self.store.preview(options)
                self.assertTrue(second.wait(1))
        finally:
            stop.set(); self.store.wake_waiters(); service.thread.join(1)
        self.assertFalse(service.thread.is_alive())


class SettingsPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Settings(Path(self.folder.name) / 'settings.json')

    def test_snapshot_copies_only_on_revision_change(self):
        revision, options = self.store.snapshot()
        with patch('settings.deepcopy', wraps=__import__('copy').deepcopy) as copy:
            self.assertEqual(self.store.snapshot(revision), (revision, None))
            copy.assert_not_called()
        options['press_color'][0] = 0
        self.assertEqual(self.store.get()['press_color'][0], 255)
        self.assertEqual(self.store.snapshot()[1]['press_color'][0], 255)

    def test_flag_and_revision_are_atomic(self):
        revision, enabled = self.store.read_flag('press_enabled')
        self.assertFalse(enabled)
        options = self.store.get(); options['press_enabled'] = True
        self.store.preview(options)
        self.assertEqual(self.store.read_flag('press_enabled'), (revision + 1, True))
        with self.assertRaises(ValueError):
            self.store.read_flag('fps')

    def test_preview_cancel_and_failed_save_preserve_revisions(self):
        revision, options = self.store.snapshot()
        self.store.preview(options)
        self.assertEqual(self.store.snapshot(revision), (revision, None))
        options['fps'] = 5
        self.store.preview(options)
        self.assertEqual(self.store.snapshot()[0], revision + 1)
        with patch.object(Path, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.store.save()
        self.assertEqual(self.store.snapshot()[0], revision + 1)
        self.store.cancel()
        self.assertEqual(self.store.snapshot()[0], revision + 2)
        self.assertEqual(self.store.get()['fps'], 10)
        options['fps'] = 0
        with self.assertRaises(ValueError): self.store.preview(options)
        self.assertEqual(self.store.snapshot()[0], revision + 2)




# Frozen pre-optimization algorithm for exact output and smoothing comparisons.
class ReferenceEngine:
    """Capture at the selected rate; render keepalives and key effects independently."""
    def __init__(self, capture, layout):
        self.capture, self.layout = capture, layout
        self.sample = None
        self.next_capture = 0
        self.capture_options = None
        self.previous = None
        self.previous_time = None

    def frame(self, now, options, pressed, notifications=None):
        capture_options = (options['fps'], options['mode'])
        if self.sample is None or now >= self.next_capture or capture_options != self.capture_options:
            self.sample = colors_from_image(self.capture(), self.layout, 1, options['mode'])
            period = 1 / options['fps']
            if capture_options != self.capture_options:
                self.next_capture = now + period
            else:
                self.next_capture += (math.floor((now - self.next_capture) / period) + 1) * period
            self.capture_options = capture_options
        target = [tuple(v * options['brightness'] for v in rgb) for rgb in self.sample]
        elapsed = max(0, now - self.previous_time) if self.previous_time is not None else 0
        self.previous = smooth_colors(self.previous, target, elapsed, options['smoothing'])
        self.previous_time = now
        colors = [tuple(round(v) for v in rgb) for rgb in self.previous]
        for index, rule in options['exceptions'].items():
            if rule['mode'] == 'off':
                colors[int(index)] = (0, 0, 0)
            elif rule['mode'] == 'fixed':
                colors[int(index)] = tuple(round(v * options['brightness']) for v in rule['color'])
        if options['press_enabled']:
            for index in pressed:
                colors[index] = tuple(options['press_color'])
        for index, color in (notifications or {}).items():
            colors[index] = tuple(color)
        return colors


if __name__ == '__main__':
    unittest.main()
