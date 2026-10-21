import unittest
from unittest.mock import Mock
from PIL import Image
from kemove_rgb import colors_from_image, load_layout, smooth_colors, stream_step
from k87 import encode_frame, verify_identity, EXPECTED_IDENTITY


class Tests(unittest.TestCase):
    def test_frame_bounds_and_command(self):
        packet = encode_frame([(40, 0, 0)] * 126)
        self.assertEqual(packet[:8], bytes.fromhex('06 08 00 00 01 00 7a 01'))
        self.assertEqual(len(packet), 520)
        self.assertEqual(packet[8:386], bytes([40, 0, 0]) * 126)
        self.assertEqual(packet[386:], bytes(134))
        for colors in [[(1, 2, 3)], [(256, 0, 0)] * 126, [(1.5, 0, 0)] * 126]:
            with self.assertRaises(ValueError):
                encode_frame(colors)

    def test_identity_rejects_other_models_and_short_reads(self):
        verify_identity(EXPECTED_IDENTITY)
        for response in [EXPECTED_IDENTITY[:-1], EXPECTED_IDENTITY[:-1] + b'\xcd', bytes(14)]:
            with self.assertRaises(ValueError):
                verify_identity(response)

    def test_spatial_layout_and_brightness(self):
        layout = load_layout()
        self.assertEqual(len(layout), 87)
        image = Image.new('RGB', (100, 60), (100, 0, 0))
        image.paste((0, 0, 100), (50, 0, 100, 60))
        colors = colors_from_image(image, layout, 0.5, 'spatial')
        self.assertEqual(colors[0], (50, 0, 0))
        self.assertEqual(colors[101], (0, 0, 50))
        self.assertEqual(colors[6], (0, 0, 0))

    def test_average_and_black(self):
        colors = colors_from_image(Image.new('RGB', (100, 60), (20, 40, 80)), load_layout(), 1, 'average')
        self.assertTrue(all(rgb == (20, 40, 80) for rgb in colors))
        dark = colors_from_image(Image.new('RGB', (100, 60)), load_layout(), 1, 'spatial')
        self.assertTrue(all(rgb == (0, 0, 0) for rgb in dark))

    def test_smoothing_and_initial_frame(self):
        colors = [(100, 50, 0)] * 126
        self.assertEqual(smooth_colors(None, colors, 0.1, 0.2), colors)
        self.assertEqual(smooth_colors([(0, 0, 0)] * 126, colors, 0.1, 0), colors)
        mid = smooth_colors([(0, 0, 0)] * 126, colors, 0.1, 0.2)
        self.assertTrue(0 < mid[0][0] < 100)

    def test_slow_smoothing_reaches_black(self):
        state = [(255, 255, 255)] * 126
        for _ in range(1000):
            state = smooth_colors(state, [(0, 0, 0)] * 126, 0.05, 2)
        self.assertTrue(all(round(v) == 0 for rgb in state for v in rgb))

    def test_failed_write_closes_connection_and_next_step_reopens(self):
        keyboard = Mock()
        keyboard.is_open = True
        keyboard.send.side_effect = [OSError('unplugged'), None]
        image = Image.new('RGB', (30, 20))
        with self.assertRaises(OSError):
            stream_step(keyboard, lambda: image, load_layout(), 0.35, 'spatial', None, 0.1, 0)
        keyboard.close.assert_called_once()
        keyboard.is_open = False
        stream_step(keyboard, lambda: image, load_layout(), 0.35, 'spatial', None, 0.1, 0)
        keyboard.open.assert_called_once()

    def test_capture_failure_releases_keyboard(self):
        keyboard = Mock()
        keyboard.is_open = True
        with self.assertRaises(OSError):
            stream_step(keyboard, Mock(side_effect=OSError('locked')), load_layout(), 1, 'spatial', None, 0.1, 0)
        keyboard.close.assert_called_once()
        keyboard.send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
