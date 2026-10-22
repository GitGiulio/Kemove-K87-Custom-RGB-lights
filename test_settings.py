import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from settings import Settings, defaults, validate
from kemove_rgb import FrameEngine, load_layout
from pressed_keys import PressedKeys

class SettingsTests(unittest.TestCase):
    def test_capture_rate_does_not_round_down_to_output_divisor(self):
        for fps, output_fps in [(7, 10), (20, 30)]:
            capture = Mock(return_value=Image.new('RGB', (60,20)))
            engine = FrameEngine(capture, load_layout())
            options = defaults(); options.update(fps=fps, smoothing=0)
            for tick in range(output_fps * 10):
                engine.frame(tick / output_fps, options, set())
            self.assertGreaterEqual(capture.call_count, fps * 10 - 1)

    def test_layout_covers_keys_and_keeps_fn_unmapped(self):
        layout = load_layout()
        self.assertEqual(sum(bool(k['scan']) for k in layout), 86)
        self.assertEqual(next(k['scan'] for k in layout if k['name']=='Fn'), 0)
        self.assertTrue(all('&apos;' not in k['name'] for k in layout))

    def test_press_state_has_brief_visibility_and_no_history(self):
        stop = Mock(); stop.is_set.side_effect = [False, False, False, True]
        settings = Mock(); settings.read_flag.return_value = (0, True)
        presses = PressedKeys([{'index':0, 'scan':1}], settings, stop)
        presses.user = Mock()
        presses.user.GetKeyboardLayout.return_value = 1
        presses.user.MapVirtualKeyExW.return_value = 27
        snapshots = []
        presses.user.GetAsyncKeyState.side_effect = lambda vk: -32768 if vk==27 and not snapshots else 0
        stop.wait.side_effect = lambda delay: snapshots.append(presses.get())
        with patch('pressed_keys.time.monotonic', side_effect=[0, .04, .2]):
            presses.run()
        self.assertEqual(snapshots, [{0}, {0}, set()])

    def test_disabled_overlay_never_queries_key_state(self):
        stop = Mock(); stop.is_set.side_effect = [False, True]
        settings = Mock(); settings.read_flag.return_value = (0, False)
        presses = PressedKeys(load_layout(), settings, stop)
        presses.user = Mock()
        presses.run()
        presses.user.GetAsyncKeyState.assert_not_called()

    def test_save_preview_cancel_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Settings(Path(folder) / 'settings.json')
            draft = store.get(); draft['fps'] = .125
            store.preview(draft)
            self.assertEqual(store.get()['fps'], .125)
            store.cancel(); self.assertEqual(store.get()['fps'], 10)
            store.preview(draft); store.save()
            self.assertEqual(Settings(store.path).get()['fps'], .125)
            for value in [0, 31, float('nan')]:
                draft['fps'] = value
                with self.assertRaises(ValueError): validate(draft)

    def test_slow_sampling_keeps_output_and_overlay_independent(self):
        capture = Mock(return_value=Image.new('RGB', (60,20), (100,100,100)))
        engine = FrameEngine(capture, load_layout())
        options = defaults(); options.update(fps=.125, brightness=.2, smoothing=0, press_enabled=True)
        options['exceptions'] = {'0': {'mode':'off', 'color':[1,2,3]}, '12': {'mode':'fixed', 'color':[100,50,0]}}
        initial = engine.frame(0, options, {0})
        self.assertEqual(initial[0], tuple(options['press_color']))
        self.assertEqual(initial[12], (20,10,0))
        self.assertEqual(engine.frame(.1, options, set())[0], (0,0,0))
        engine.frame(7.9, options, set()); self.assertEqual(capture.call_count, 1)
        engine.frame(8, options, set()); self.assertEqual(capture.call_count, 2)
        options['press_enabled'] = False
        self.assertEqual(engine.frame(8.1, options, {0})[0], (0,0,0))

if __name__ == '__main__': unittest.main()
