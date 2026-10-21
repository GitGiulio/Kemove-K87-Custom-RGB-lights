import unittest
from unittest.mock import Mock, patch
from settings_ui import SettingsWindow

class SaveTests(unittest.TestCase):
    def test_failed_save_restores_startup_and_keeps_dialog(self):
        dialog=Mock()
        dialog.get_startup.return_value=False
        dialog.startup.get.return_value=True
        dialog.store.save.side_effect=OSError('disk full')
        with patch('settings_ui.messagebox.showerror'):
            SettingsWindow.save(dialog)
        self.assertEqual([c.args[0] for c in dialog.set_startup.call_args_list], [True, False])
        dialog.destroy.assert_not_called()

if __name__ == '__main__': unittest.main()
