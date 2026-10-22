"""K87-1980 live RGB transport. No persistent-setting or firmware commands."""
import ctypes as c
import os
from pathlib import Path
import time

HEADER = bytes.fromhex('06 08 00 00 01 00 7a 01')
EXPECTED_IDENTITY = bytes.fromhex('06 82 01 00 01 00 06 00 03 00 00 00 00 8e')


def verify_identity(response):
    if response != EXPECTED_IDENTITY:
        raise ValueError('Unrecognized keyboard revision. Refusing lighting writes.')


def validated_colors(colors):
    colors = tuple(tuple(rgb) for rgb in colors)
    if len(colors) != 126 or any(len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb) for rgb in colors):
        raise ValueError('Expected 126 RGB slots with integer channels in 0..255')
    return colors


def _encode_colors(colors):
    return HEADER + bytes(v for rgb in colors for v in rgb) + bytes(134)


def encode_frame(colors):
    return _encode_colors(validated_colors(colors))


class Info(c.Structure):
    pass


Info._fields_ = [
    ('path', c.c_char_p), ('vendor_id', c.c_ushort), ('product_id', c.c_ushort),
    ('serial_number', c.c_wchar_p), ('release_number', c.c_ushort),
    ('manufacturer_string', c.c_wchar_p), ('product_string', c.c_wchar_p),
    ('usage_page', c.c_ushort), ('usage', c.c_ushort), ('interface_number', c.c_int),
    ('next', c.POINTER(Info)), ('bus_type', c.c_int),
]


class Keyboard:
    def __init__(self, dll=None):
        path = Path(dll) if dll else Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'OpenRGB/hidapi-hotplug.dll'
        if not path.is_file():
            raise FileNotFoundError(f'HID library not found: {path}. Install OpenRGB or pass --hid-dll PATH.')
        self.api = c.CDLL(str(path.resolve()))
        for name, args, result in [
            ('hid_enumerate', [c.c_ushort, c.c_ushort], c.POINTER(Info)),
            ('hid_free_enumeration', [c.POINTER(Info)], None),
            ('hid_open_path', [c.c_char_p], c.c_void_p),
            ('hid_close', [c.c_void_p], None),
            ('hid_get_report_descriptor', [c.c_void_p, c.c_void_p, c.c_size_t], c.c_int),
            ('hid_send_feature_report', [c.c_void_p, c.c_void_p, c.c_size_t], c.c_int),
            ('hid_get_feature_report', [c.c_void_p, c.c_void_p, c.c_size_t], c.c_int),
            ('hid_error', [c.c_void_p], c.c_wchar_p),
        ]:
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.handle = None
        self.cached_colors = None
        self.cached_packet = None

    @property
    def is_open(self):
        return self.handle is not None

    def close(self):
        self.cached_colors = None
        self.cached_packet = None
        if self.handle:
            self.api.hid_close(self.handle)
            self.handle = None

    def _write(self, frame):
        buf = c.create_string_buffer(frame, len(frame))
        n = self.api.hid_send_feature_report(self.handle, buf, len(frame))
        if n != len(frame):
            raise OSError(f'Keyboard write failed ({n}): {self.api.hid_error(self.handle)}')

    def open(self):
        self.close()
        head = self.api.hid_enumerate(0x258A, 0x010C)
        current = head
        matches = []
        try:
            while current:
                item = current.contents
                if (item.product_string == 'KEMOVE K87-1980' and item.manufacturer_string == 'BY Tech'
                        and item.interface_number == 1 and item.usage_page == 0xFF00 and item.usage == 1):
                    handle = self.api.hid_open_path(item.path)
                    if handle:
                        try:
                            descriptor = c.create_string_buffer(4096)
                            n = self.api.hid_get_report_descriptor(handle, descriptor, len(descriptor))
                            data = descriptor.raw[:max(0, n)]
                            if b'\x85\x06' in data and b'\x96\x07\x02\xb1' in data:
                                matches.append(bytes(item.path))
                        finally:
                            self.api.hid_close(handle)
                current = item.next
        finally:
            self.api.hid_free_enumeration(head)
        if not matches:
            raise OSError('K87 not available. Connect its USB cable and select wired mode.')
        if len(matches) != 1:
            raise ValueError('Multiple matching keyboards. Connect only one K87.')
        self.handle = self.api.hid_open_path(matches[0])
        if not self.handle:
            self.handle = None
            raise OSError('Cannot open the K87. Close other keyboard lighting software.')
        try:
            self._write(bytes.fromhex('06 82 01 00 01 00 06').ljust(520, b'\0'))
            time.sleep(0.05)
            reply = c.create_string_buffer(520)
            reply[0] = b'\x06'
            n = self.api.hid_get_feature_report(self.handle, reply, len(reply))
            if n < 0:
                raise OSError(f'Keyboard identity read failed: {self.api.hid_error(self.handle)}')
            verify_identity(reply.raw[:n])
        except BaseException:
            self.close()
            raise

    def send(self, colors):
        if not self.is_open:
            raise OSError('Keyboard disconnected')
        colors = validated_colors(colors)
        if colors != getattr(self, 'cached_colors', None):
            self.cached_packet = _encode_colors(colors)
            self.cached_colors = colors
        self._write(self.cached_packet)
