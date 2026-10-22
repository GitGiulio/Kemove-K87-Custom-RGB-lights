import asyncio
import threading
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from PIL import Image

from settings import defaults, validate, Settings
from kemove_rgb import FrameEngine, load_layout
from notification_blinker import (APP_CATALOG, AlertState, NotificationService, ForegroundApp,
                                  WinRTSource, POLL_SECONDS, FOREGROUND_SECONDS)


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.options = defaults()
        self.options['notifications_enabled'] = True
        self.state = AlertState()
        self.state.configure(self.options)

    def test_dismissal_coalescing_and_foreground_acknowledgement(self):
        self.state.observe('chatgpt', 1, 100, 10)
        self.assertEqual(self.state.overlay(10), {54: (255, 0, 0)})
        self.state.observe('chatgpt', 2, 101, 10.3)
        self.assertEqual(self.state.overlay(10.6), {})
        # No dismissal action exists: removing a toast never clears pending state.
        self.assertEqual(self.state.overlay(12), {54: (255, 0, 0)})
        self.state.acknowledge('chatgpt', 102)
        self.assertEqual(self.state.overlay(12), {})
        self.state.observe('chatgpt', 2, 101, 13)
        self.assertEqual(self.state.overlay(13), {})
        self.state.observe('chatgpt', 3, 103, 14)
        self.assertEqual(self.state.overlay(14), {54: (255, 0, 0)})

    def test_reconfigure_moves_color_and_disabling_clears(self):
        self.state.observe('chatgpt', 1, 100, 10)
        self.options['notification_apps']['chatgpt'].update(key_index=36, color=[1, 2, 3])
        self.state.configure(self.options)
        self.assertEqual(self.state.overlay(11), {36: (1, 2, 3)})
        self.options['notification_apps']['chatgpt']['enabled'] = False
        self.state.configure(self.options)
        self.assertEqual(self.state.overlay(11), {})
        self.options['notification_apps']['chatgpt']['enabled'] = True
        self.state.configure(self.options)
        self.assertEqual(self.state.overlay(11), {})
        self.state.observe('unknown', 1, 100, 11)
        self.assertEqual(self.state.overlay(11), {})

    def test_shared_key_has_one_owner_including_its_off_phase(self):
        catalog = dict(APP_CATALOG, other=dict(APP_CATALOG['chatgpt'], aumid='other'))
        options = deepcopy(self.options)
        options['notification_apps']['other'] = dict(enabled=True, key_index=54, color=[0, 0, 255])
        state = AlertState(catalog)
        state.configure(options)
        state.observe('chatgpt', 1, 100, 10)
        state.observe('other', 1, 101, 10.6)
        self.assertEqual(state.overlay(11), {54: (0, 0, 255)})
        self.assertEqual(state.overlay(11.2), {})
        state.acknowledge('other', 102)
        self.assertEqual(state.overlay(12), {54: (255, 0, 0)})

    def test_notification_overlay_wins_without_disturbing_other_keys(self):
        options = self.options
        options.update(fps=.125, brightness=.2, smoothing=0, press_enabled=True)
        options['exceptions']['54'] = dict(mode='off', color=[0, 0, 0])
        capture = Mock(return_value=Image.new('RGB', (60, 20), (100, 100, 100)))
        engine = FrameEngine(capture, load_layout())
        colors = engine.frame(0, options, {54}, {54: (255, 0, 0)})
        self.assertEqual(colors[54], (255, 0, 0))
        self.assertEqual(colors[36], (20, 20, 20))
        self.assertEqual(engine.frame(.6, options, {54}, {})[54], (255, 255, 255))
        self.assertEqual(engine.frame(1, options, set(), {})[54], (0, 0, 0))
        self.assertEqual(capture.call_count, 1)


class NotificationSettingsTests(unittest.TestCase):
    def test_requested_polling_intervals(self):
        self.assertEqual((POLL_SECONDS, FOREGROUND_SECONDS), (10, 1))

    def test_notification_settings_persist_and_cancel(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            store = Settings(Path(folder) / 'settings.json')
            draft = store.get()
            draft['notifications_enabled'] = True
            draft['notification_apps']['chatgpt'].update(key_index=36, color=[3, 2, 1])
            store.preview(draft)
            store.save()
            self.assertEqual(Settings(store.path).get(), draft)
            draft['notification_apps']['chatgpt']['enabled'] = False
            store.preview(draft)
            store.cancel()
            self.assertTrue(store.get()['notification_apps']['chatgpt']['enabled'])

    def test_defaults_and_nested_migration(self):
        options = validate({'notification_apps': {'chatgpt': {'color': [2, 3, 4]}}})
        self.assertFalse(options['notifications_enabled'])
        self.assertEqual(options['notification_apps']['chatgpt'],
                         dict(enabled=True, key_index=54, color=[2, 3, 4]))
        self.assertEqual(defaults()['notification_apps']['chatgpt']['color'], [255, 0, 0])

    def test_strict_validation_and_unknown_apps_remain_inert(self):
        for change in [dict(enabled=1), dict(key_index=True), dict(key_index=125),
                       dict(color=[0, 0, 256]), dict(color=[True, 0, 0])]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({'notification_apps': {'chatgpt': change}})
        for value in [1, None, 'yes']:
            with self.assertRaises(ValueError):
                validate({'notifications_enabled': value})
        future = dict(enabled=True, key_index=36, color=[0, 0, 1])
        options = validate({'notifications_enabled': True, 'notification_apps': {'future': future}})
        self.assertEqual(options['notification_apps']['future'], future)
        state = AlertState()
        state.configure(options)
        state.observe('future', 1, 100, 1)
        self.assertEqual(state.overlay(1), {})


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.options = defaults()
        self.options['notifications_enabled'] = True
        self.store.get.side_effect = lambda: deepcopy(self.options)
        self.store.snapshot.side_effect = lambda revision=-1: (0, deepcopy(self.options))
        self.foreground = Mock(return_value=None)
        self.service = NotificationService(self.store, threading.Event(), foreground=self.foreground)
        self.aumid = APP_CATALOG['chatgpt']['aumid']

    def snapshot(self, *items):
        return [(self.aumid, identifier, created) for identifier, created in items]

    def test_baseline_dedup_dismissal_and_delayed_snapshot(self):
        self.service.tick(10, 100, self.snapshot((1, 99)))
        self.assertEqual(self.service.overlay(10), {})
        self.service.tick(11, 101, self.snapshot((1, 99), (2, 101)))
        self.assertEqual(self.service.overlay(11), {54: (255, 0, 0)})
        self.service.tick(12, 102, [])
        self.assertEqual(self.service.overlay(12), {54: (255, 0, 0)})
        self.foreground.return_value = self.aumid
        self.service.tick(12.1, 102.1)
        self.assertEqual(self.service.overlay(12.1), {})
        self.foreground.return_value = None
        self.service.tick(13, 103, self.snapshot((2, 101)))
        self.assertEqual(self.service.overlay(13), {})

    def test_foreground_at_arrival_and_reenable_baseline(self):
        self.service.tick(0, 100, [])
        self.foreground.return_value = self.aumid
        self.service.tick(1, 101, self.snapshot((1, 101)))
        self.assertEqual(self.service.overlay(1), {})
        self.foreground.return_value = None
        self.options['notifications_enabled'] = False
        self.service.tick(2, 102)
        self.options['notifications_enabled'] = True
        self.service.tick(3, 103, self.snapshot((2, 102)))
        self.assertEqual(self.service.overlay(3), {})
        self.service.tick(4, 104, self.snapshot((2, 102), (3, 104)))
        self.assertEqual(self.service.overlay(4), {54: (255, 0, 0)})

    def test_permission_loss_and_recovery_clear_and_rebaseline(self):
        self.service.tick(0, 100, [])
        self.service.tick(1, 101, self.snapshot((1, 101)))
        self.service.unavailable('Access required')
        self.assertEqual(self.service.overlay(1), {})
        self.assertEqual(self.service.status(), 'Access required')
        self.service.tick(2, 102, self.snapshot((1, 101)))
        self.assertEqual(self.service.overlay(2), {})

    def test_foreground_failure_never_acknowledges(self):
        self.service.tick(0, 100, [])
        self.foreground.side_effect = OSError('unavailable')
        self.service.tick(1, 101, self.snapshot((1, 101)))
        self.assertEqual(self.service.overlay(1), {54: (255, 0, 0)})

    def test_snapshot_started_before_enable_does_not_finish_baseline(self):
        self.service.tick(10, 100, [], snapshot_started=99)
        self.service.tick(11, 101, self.snapshot((1, 101)), snapshot_started=101)
        self.assertEqual(self.service.overlay(11), {54: (255, 0, 0)})
        self.service.tick(12, 102, self.snapshot((2, 102)), snapshot_started=102)
        self.assertEqual(self.service.overlay(12), {54: (255, 0, 0)})

    def test_first_poll_captures_notifications_created_after_enabling(self):
        self.service.tick(10, 100)
        self.service.tick(11, 101, self.snapshot((1, 99), (2, 100.5)), snapshot_started=100)
        self.assertEqual(self.service.overlay(11), {54: (255, 0, 0)})

    def test_transient_query_failure_preserves_pending_alert(self):
        self.service.tick(10, 100, [])
        self.service.tick(11, 101, self.snapshot((1, 101)))
        self.service.unavailable('Query failed; retrying', clear=False)
        self.assertEqual(self.service.overlay(12), {54: (255, 0, 0)})
        self.service.tick(12, 102, self.snapshot((1, 101)))
        self.assertEqual(self.service.overlay(12), {54: (255, 0, 0)})

    def test_disable_and_reenable_between_monitor_ticks_rebaselines(self):
        self.service.tick(10, 100, [])
        self.options['notifications_enabled'] = False
        with patch('notification_blinker.time.time', return_value=100.1):
            self.assertEqual(self.service.overlay(10.1), {})
        self.options['notifications_enabled'] = True
        with patch('notification_blinker.time.time', return_value=100.2):
            self.assertEqual(self.service.overlay(10.2), {})
        self.service.tick(11, 101, self.snapshot((1, 100.15)))
        self.assertEqual(self.service.overlay(11), {})

    def test_source_denied_never_queries_and_async_cancellation_stops(self):
        source = WinRTSource()
        source.listener = Mock()
        source.listener.get_access_status.return_value = 2
        with self.assertRaises(PermissionError):
            asyncio.run(source.snapshot())
        source.listener.get_notifications_async.assert_not_called()
        entered = threading.Event()
        class SlowSource:
            async def snapshot(self):
                entered.set()
                await asyncio.sleep(60)
        with patch('notification_blinker.WinRTSource', SlowSource):
            self.service.thread.start()
            self.assertTrue(entered.wait(2))
            self.service.stop.set()
            self.service.thread.join(2)
        self.assertFalse(self.service.thread.is_alive())
        self.assertEqual(self.service.status(), 'Stopped')

    def test_permission_revoked_during_query_cannot_deliver_alert(self):
        source = WinRTSource()
        source.listener = Mock()
        source.listener.get_access_status.side_effect = [1, 2]
        async def items(_):
            return []
        source.listener.get_notifications_async.side_effect = items
        with self.assertRaises(PermissionError):
            asyncio.run(source.snapshot())

    def test_disabled_worker_does_not_load_winrt_and_stops(self):
        self.options['notifications_enabled'] = False
        with patch('notification_blinker.WinRTSource') as source:
            self.service.thread.start()
            self.service.stop.set()
            self.service.thread.join(2)
        self.assertFalse(self.service.thread.is_alive())
        source.assert_not_called()

    def test_source_filters_metadata_without_reading_body(self):
        notification = Mock(id=7, app_info=Mock(app_user_model_id=self.aumid))
        notification.creation_time.timestamp.return_value = 123.0
        source = WinRTSource()
        source.listener = Mock()
        async def items(_):
            return [notification]
        source.listener.get_notifications_async.side_effect = items
        source.listener.get_access_status.return_value = 1
        self.assertEqual(asyncio.run(source.snapshot()), [(self.aumid, 7, 123.0)])
        self.assertNotIn('notification', [call[0] for call in notification.mock_calls])

    def test_foreground_query_closes_handle_on_failure(self):
        foreground = ForegroundApp()
        foreground.user = Mock()
        foreground.kernel = Mock()
        foreground.user.GetForegroundWindow.return_value = 5
        def pid(window, out):
            out._obj.value = 42
            return 1
        foreground.user.GetWindowThreadProcessId.side_effect = pid
        foreground.kernel.OpenProcess.return_value = 123
        foreground.kernel.GetApplicationUserModelId.return_value = 5
        self.assertIsNone(foreground())
        foreground.kernel.CloseHandle.assert_called_once_with(123)


if __name__ == '__main__':
    unittest.main()
