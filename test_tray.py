import threading
import unittest
from unittest.mock import Mock, patch, MagicMock
import kemove_rgb
import kemove_tray


class TrayTests(unittest.TestCase):
    def test_startup_registers_windowless_command_and_removes_only_own_value(self):
        registry = MagicMock()
        registry.REG_SZ = 1
        key = registry.CreateKey.return_value.__enter__.return_value
        with patch.object(kemove_tray, 'winreg', registry):
            kemove_tray.set_startup(True)
            command = registry.SetValueEx.call_args.args[-1]
            self.assertIn('pythonw.exe', command)
            self.assertIn('kemove_tray.py', command)
            kemove_tray.set_startup(False)
            registry.DeleteValue.assert_called_once_with(key, kemove_tray.RUN_NAME)

    def test_quit_signal_releases_keyboard(self):
        stop = threading.Event()
        keyboard = Mock()

        def frame(*args):
            stop.set()
            return [(0, 0, 0)] * 126

        with patch('sys.argv', ['kemove_rgb.py']), patch.object(kemove_rgb.ctypes, 'get_last_error', return_value=0), patch.object(kemove_rgb, 'Keyboard', return_value=keyboard), patch.object(kemove_rgb.FrameEngine, 'frame', side_effect=frame):
            self.assertEqual(kemove_rgb.main(stop_event=stop, status=Mock()), 0)
        keyboard.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()


