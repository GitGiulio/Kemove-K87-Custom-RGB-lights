"""Border-free MSS capture, reduced before RGB conversion to avoid full-frame copies."""
import ctypes
import logging
import time

import mss
from mss.exception import ScreenShotError
from PIL import Image


def rgb_sample(image, size):
    if image.info.get('channel_order') == 'BGRX':
        # Mapped raw channels are B,G,R,X. BOX averages each channel independently.
        blue, green, red, _ = image.resize(size, Image.Resampling.BOX).split()
        return Image.merge('RGB', (red, green, blue))
    image = image if image.mode == 'RGB' else image.convert('RGB')
    return image.resize(size, Image.Resampling.BOX)


def _primary_region():
    # Query current primary geometry instead of MSS's cached monitor list.
    user = ctypes.windll.user32
    return dict(left=0, top=0, width=user.GetSystemMetrics(0), height=user.GetSystemMetrics(1))


class ScreenCapture:
    def __init__(self, region=None):
        self.region = (dict(left=region[0], top=region[1], width=region[2]-region[0],
                            height=region[3]-region[1]) if region else None)
        self.source = None
        self.last = Image.new('RGB', (60, 20))
        self.next_retry = 0
        self.available = None

    def __call__(self):
        if time.monotonic() < self.next_retry:
            return self.last
        try:
            if self.source is None:
                self.source = mss.MSS()
            shot = self.source.grab(self.region or _primary_region())
            self.last = Image.frombuffer('RGBX', shot.size, shot.raw, 'raw', 'RGBX', 0, 1)
            self.last.info['channel_order'] = 'BGRX'
            if self.available is not True:
                logging.info('Screen capture: optimized MSS')
            self.available = True
        except (ScreenShotError, OSError) as exc:
            self.close()
            self.next_retry = time.monotonic() + 2
            if self.available is not False:
                logging.warning('Screen unavailable; retaining last colors and retrying: %s', exc)
            self.available = False
        return self.last

    def close(self):
        source, self.source = self.source, None
        if source is not None:
            try:
                source.close()
            except (ScreenShotError, OSError):
                logging.exception('Could not release screen capture resources')
