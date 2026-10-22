"""Exercise actual Tk controls against a temporary settings file."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from kemove_rgb import load_layout
from settings import Settings
from settings_ui import SettingsWindow
from notification_blinker import APP_CATALOG


class NotificationUITests(unittest.TestCase):
    def test_rows_key_color_preview_cancel_and_cleanup(self):
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        with tempfile.TemporaryDirectory() as folder:
            store = Settings(Path(folder) / 'settings.json')
            service = Mock()
            service.status.return_value = 'Connected'
            window = SettingsWindow(root, store, load_layout(), lambda: False, Mock(), service)
            try:
                root.update()
                self.assertEqual(len(window.tabs.tabs()), 2)
                row = window.notification_rows['chatgpt']
                self.assertEqual(str(row['key']['state']), 'disabled')
                window.notifications_enabled.set(True)
                window.notification_changed()
                self.assertEqual(str(row['key']['state']), 'readonly')
                self.assertEqual(len(row['key']['values']), 87)
                row['key'].current(next(i for i, key in enumerate(window.layout) if key['name'] == 'F5'))
                window.notification_changed()
                def choose(parent, initial, accept):
                    accept([1, 2, 3])
                with patch('settings_ui.ColorWheel', side_effect=choose):
                    window.pick_notification_color('chatgpt')
                self.assertEqual(store.get()['notification_apps']['chatgpt'],
                                 dict(enabled=True, key_index=36, color=[1, 2, 3]))
                window.request_notification_access()
                service.request_access.assert_called_once()
                callback = window.notification_after
                window.cancel()
                self.assertIsNone(window.notification_after)
                self.assertNotIn(callback, root.tk.call('after', 'info'))
                self.assertFalse(store.get()['notifications_enabled'])
                self.assertEqual(store.get()['notification_apps']['chatgpt']['key_index'], 54)
            finally:
                if window.winfo_exists():
                    window.destroy()
                root.destroy()

    def test_catalog_addition_produces_an_independent_row(self):
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        future = dict(name='Synthetic app', aumid='test', key_index=36, color=[1, 2, 3])
        with tempfile.TemporaryDirectory() as folder, patch.dict(APP_CATALOG, synthetic=future):
            store = Settings(Path(folder) / 'settings.json')
            window = SettingsWindow(root, store, load_layout(), lambda: False, Mock())
            try:
                self.assertEqual(set(window.notification_rows), {'chatgpt', 'synthetic'})
                window.notifications_enabled.set(True)
                window.notification_rows['chatgpt']['enabled'].set(False)
                window.notification_changed()
                self.assertFalse(store.get()['notification_apps']['chatgpt']['enabled'])
                self.assertTrue(store.get()['notification_apps']['synthetic']['enabled'])
            finally:
                window.destroy()
                root.destroy()


if __name__ == '__main__':
    unittest.main()
