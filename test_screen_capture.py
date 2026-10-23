import random
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from mss.exception import ScreenShotError

from kemove_rgb import colors_from_image, load_layout
from screen_capture import ScreenCapture, rgb_sample


class CaptureTests(unittest.TestCase):
    def shot(self, size=(2, 1)):
        return Mock(size=size, raw=bytearray([44, 70, 34, 255] * (size[0]*size[1])))

    def test_primary_capture_reuses_mss_and_maps_raw_bytes_without_copy(self):
        source = Mock()
        primary = dict(left=0, top=0, width=2, height=1)
        shot = self.shot()
        source.grab.return_value = shot
        with patch('screen_capture.mss.MSS', return_value=source) as create, \
             patch('screen_capture._primary_region', return_value=primary):
            capture = ScreenCapture()
            image = capture()
            self.assertEqual(rgb_sample(image, (1,1)).getpixel((0,0)), (34,70,44))
            shot.raw[:4] = bytes([1,2,3,255])
            self.assertEqual(image.getpixel((0,0)), (1,2,3,255))
            capture()
            create.assert_called_once_with()
            source.grab.assert_called_with(primary)
            capture.close(); capture.close()
        source.close.assert_called_once()

    def test_raw_sample_matches_previous_rgb_colors_for_modes_and_brightness(self):
        layout = load_layout()
        for size in [(101,61), (2560,1440)]:
            raw = bytearray(random.Random(42).randbytes(size[0]*size[1]*4))
            reference = Image.frombytes('RGB', size, raw, 'raw', 'BGRX')
            source = Mock()
            source.grab.return_value = Mock(size=size, raw=raw)
            with patch('screen_capture.mss.MSS', return_value=source):
                capture = ScreenCapture()
                mapped = capture()
                with patch.object(mapped, 'convert', wraps=mapped.convert) as convert:
                    for mode in ['average', 'spatial']:
                        for brightness in [0, .35, 1]:
                            self.assertEqual(colors_from_image(mapped,layout,brightness,mode),
                                             colors_from_image(reference,layout,brightness,mode))
                    convert.assert_not_called()
                capture.close()

    def test_ordinary_rgbx_images_are_not_treated_as_bgra(self):
        source = Image.new('RGBX', (9,7), (20,40,60,255))
        self.assertEqual(rgb_sample(source,(1,1)).getpixel((0,0)), (20,40,60))

    def test_primary_capture_tracks_display_geometry_changes(self):
        source = Mock()
        source.grab.return_value = self.shot()
        small = dict(left=0, top=0, width=1280, height=720)
        large = dict(left=0, top=0, width=1920, height=1080)
        with patch('screen_capture.mss.MSS', return_value=source), \
             patch('screen_capture._primary_region', side_effect=[small,large], create=True):
            capture = ScreenCapture()
            capture(); capture()
            self.assertEqual([call.args[0] for call in source.grab.call_args_list], [small,large])
            capture.close()

    def test_regions_keep_negative_and_cross_monitor_coordinates(self):
        source = Mock()
        source.grab.return_value = self.shot()
        with patch('screen_capture.mss.MSS', return_value=source):
            capture = ScreenCapture((-100,20,100,80))
            capture()
            source.grab.assert_called_once_with(dict(left=-100,top=20,width=200,height=60))
            capture.close()

    def test_failure_retains_last_image_then_reopens_after_bounded_backoff(self):
        clock = [0]
        first, second = Mock(), Mock()
        first.grab.side_effect = [self.shot(), ScreenShotError('locked')]
        second.grab.return_value = self.shot()
        with patch('screen_capture.mss.MSS', side_effect=[first,second]) as create, \
             patch('screen_capture.time.monotonic', side_effect=lambda: clock[0]):
            capture = ScreenCapture()
            initial = capture()
            self.assertIs(capture(), initial)
            self.assertIs(capture(), initial)
            self.assertEqual(create.call_count,1)
            first.close.assert_called_once()
            clock[0] = 2
            self.assertIsNot(capture(),initial)
            self.assertEqual(create.call_count,2)
            capture.close()

    def test_unavailable_startup_is_dark_and_keeps_effects_running(self):
        with patch('screen_capture.mss.MSS', side_effect=OSError('no desktop')):
            capture = ScreenCapture()
            self.assertEqual(rgb_sample(capture(),(1,1)).getpixel((0,0)),(0,0,0))
            capture.close()


if __name__ == '__main__':
    unittest.main()
