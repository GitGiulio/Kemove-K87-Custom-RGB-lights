"""Local notification metadata and temporary LED alerts; never reads message text."""
import asyncio
import ctypes as c
import threading
import time


APP_CATALOG = {
    'chatgpt': dict(name='ChatGPT', aumid='OpenAI.Codex_2p2nqsd0c76g0!App',
                    key_index=54, color=[255, 0, 0]),
}
POLL_SECONDS = 10
FOREGROUND_SECONDS = 1


class AlertState:
    def __init__(self, catalog=None):
        self.catalog = APP_CATALOG if catalog is None else catalog
        self.rules = {}
        self.pending = {}
        self.acknowledged = {}

    def configure(self, options):
        self.rules = {app: rule for app, rule in options['notification_apps'].items()
                      if options['notifications_enabled'] and app in self.catalog and rule['enabled']}
        self.pending = {app: started for app, started in self.pending.items() if app in self.rules}

    def observe(self, app_id, notification_id, created_at, now):
        if app_id in self.rules and created_at > self.acknowledged.get(app_id, float('-inf')):
            self.pending.setdefault(app_id, now)

    def acknowledge(self, app_id, through_time):
        self.pending.pop(app_id, None)
        self.acknowledged[app_id] = max(through_time, self.acknowledged.get(app_id, float('-inf')))

    def clear(self):
        self.pending.clear()

    def overlay(self, now):
        # Choose each key's owner before computing its phase so an older alert cannot leak through.
        owners = {}
        for app in sorted(self.pending, key=lambda app: (self.pending[app], app)):
            owners[self.rules[app]['key_index']] = app
        return {index: tuple(self.rules[app]['color']) for index, app in owners.items()
                if (now - self.pending[app]) % 1 < .5}


class ForegroundApp:
    def __init__(self):
        self.user = c.WinDLL('user32', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.user.GetForegroundWindow.restype = c.c_void_p
        self.user.GetWindowThreadProcessId.argtypes = [c.c_void_p, c.POINTER(c.c_ulong)]
        self.kernel.OpenProcess.argtypes = [c.c_ulong, c.c_bool, c.c_ulong]
        self.kernel.OpenProcess.restype = c.c_void_p
        self.kernel.GetApplicationUserModelId.argtypes = [c.c_void_p, c.POINTER(c.c_uint), c.c_wchar_p]
        self.kernel.GetApplicationUserModelId.restype = c.c_long
        self.kernel.CloseHandle.argtypes = [c.c_void_p]

    def __call__(self):
        window = self.user.GetForegroundWindow()
        if not window:
            return None
        pid = c.c_ulong()
        if not self.user.GetWindowThreadProcessId(window, c.byref(pid)):
            return None
        handle = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return None
        try:
            size = c.c_uint()
            if self.kernel.GetApplicationUserModelId(handle, c.byref(size), None) != 122:
                return None
            if not 0 < size.value <= 4096:
                return None
            name = c.create_unicode_buffer(size.value)
            if self.kernel.GetApplicationUserModelId(handle, c.byref(size), name) == 0:
                return name.value
        finally:
            self.kernel.CloseHandle(handle)
        return None


class WinRTSource:
    def __init__(self):
        # PyWinRT projections are split into packages, including async/collection support.
        import winrt.windows.foundation
        import winrt.windows.foundation.collections
        import winrt.windows.applicationmodel
        from winrt.windows.ui.notifications import NotificationKinds
        from winrt.windows.ui.notifications.management import UserNotificationListener
        self.listener = UserNotificationListener.current
        self.kind = NotificationKinds.TOAST

    async def snapshot(self):
        if self.listener.get_access_status() != 1:
            raise PermissionError('Notification access required. Use Allow access / Retry in Settings.')
        items = await self.listener.get_notifications_async(self.kind)
        if self.listener.get_access_status() != 1:
            raise PermissionError('Notification access was revoked during the query.')
        allowed = {app['aumid'] for app in APP_CATALOG.values()}
        result = []
        for item in items:
            try:
                aumid = item.app_info.app_user_model_id
                if aumid in allowed:
                    result.append((aumid, item.id, item.creation_time.timestamp()))
            except (OSError, AttributeError):
                # A toast can disappear between enumeration and metadata access.
                continue
        return result


class NotificationService:
    def __init__(self, settings, stop_event, foreground=None):
        self.settings, self.stop = settings, stop_event
        self.foreground = foreground
        self.state = AlertState()
        self.lock = threading.Lock()
        self.message = 'Disabled'
        self.seen = set()
        self.enabled_apps = set()
        self.recovering = False
        self.enabled_since = {}
        self.retry = threading.Event()
        self.access_operation = None
        self.options_revision = -1
        self.options = None
        self.configuration = None
        self.thread = threading.Thread(target=self.run, name='K87 notification alerts')

    def _options(self):
        self.options_revision, updated = self.settings.snapshot(self.options_revision)
        if updated is not None:
            self.options = updated
        return self.options

    def overlay(self, now, options=None, revision=None):
        with self.lock:
            if options is None or revision is None:
                options = self._options()
            elif revision < self.options_revision:
                options = self.options
            else:
                self.options_revision, self.options = revision, options
            self._configure(options, time.time())
            return self.state.overlay(now)

    def _configure(self, options, wall_time):
        configuration = (options['notifications_enabled'], tuple(
            (app, rule['enabled'], rule['key_index'], tuple(rule['color']))
            for app, rule in options['notification_apps'].items()))
        if configuration == self.configuration:
            return
        self.configuration = configuration
        self.state.configure(options)
        enabled = set(self.state.rules)
        for app in enabled - self.enabled_apps:
            self.state.acknowledge(app, wall_time)
            self.enabled_since[app] = wall_time
        self.enabled_apps = enabled

    def status(self):
        with self.lock:
            return self.message

    def unavailable(self, message, clear=True):
        with self.lock:
            self.message = message
            if clear:
                self.state.clear()
                self.recovering = True
                self.seen.clear()

    def tick(self, now, wall_time, snapshot=None, snapshot_started=None):
        with self.lock:
            self._configure(self._options(), wall_time)
            enabled = self.enabled_apps
            try:
                foreground = self.foreground() if enabled and self.foreground else None
            except OSError:
                foreground = None
            if snapshot is not None:
                apps = {info['aumid']: app for app, info in APP_CATALOG.items()}
                started = wall_time if snapshot_started is None else snapshot_started
                observed = {item for item in snapshot if apps.get(item[0]) not in enabled
                            or self.enabled_since[apps[item[0]]] <= started}
                if self.recovering:
                    for app in enabled:
                        self.state.acknowledge(app, wall_time)
                    self.recovering = False
                for aumid, identifier, created in observed - self.seen:
                    app = apps.get(aumid)
                    if app in enabled:
                        self.state.observe(app, identifier, created, now)
                self.seen = observed
                self.message = f'Connected (checks every {POLL_SECONDS} seconds)' if enabled else 'Disabled'
            for app in enabled:
                if foreground == APP_CATALOG[app]['aumid']:
                    self.state.acknowledge(app, wall_time)
            if not enabled:
                self.message = 'Disabled'

    def request_access(self):
        """Called only by the Tk UI thread; completion never touches Tk widgets."""
        try:
            from winrt.runtime import init_apartment, ApartmentType
            init_apartment(ApartmentType.SINGLE_THREADED)
            source = WinRTSource()
            if source.listener.get_access_status() == 1:
                self.retry.set()
                with self.lock:
                    self.message = 'Access allowed; checking notifications'
                return
            if self.access_operation is not None:
                return
            operation = source.listener.request_access_async()
            self.access_operation = operation

            def completed(op, status):
                try:
                    allowed = op.get_results() == 1
                    with self.lock:
                        self.message = ('Access allowed; checking notifications' if allowed else
                                        'Access denied. Allow notification access in Windows privacy settings.')
                    self.retry.set()
                except OSError:
                    self.unavailable('Access request failed. Check Windows notification privacy settings.')
                finally:
                    self.access_operation = None

            operation.completed = completed
        except ImportError:
            self.unavailable('Unavailable: install the WinRT packages from requirements.txt.')
        except OSError:
            self.unavailable('Access request failed. Check Windows notification privacy settings.')

    def run(self):
        try:
            self.foreground = self.foreground or ForegroundApp()
            asyncio.run(self._run())
        except Exception:
            # Optional notification support must never terminate the lighting worker.
            self.unavailable('Notification listener failed. Use Allow access / Retry in Settings.')

    async def _run(self):
        source, query, next_query = None, None, 0
        try:
            while not self.stop.is_set():
                self.tick(time.monotonic(), time.time())
                with self.lock:
                    enabled = bool(self.enabled_apps)
                    idle_revision = self.options_revision
                if query is not None and (query.done() or not enabled):
                    if not enabled:
                        query.cancel()
                    else:
                        try:
                            snapshot = query.result()
                            self.tick(time.monotonic(), time.time(), snapshot, query_started)
                        except PermissionError:
                            self.unavailable('Access required. Use Allow access / Retry in Settings.')
                        except Exception:
                            self.unavailable('Notification query failed. Retrying automatically.', clear=False)
                    await asyncio.gather(query, return_exceptions=True)
                    query = None
                if not enabled:
                    next_query = 0
                    await asyncio.to_thread(self.settings.wait_for_change, idle_revision, self.stop)
                    continue
                if self.retry.is_set():
                    self.retry.clear()
                    next_query = 0
                if enabled and query is None and time.monotonic() >= next_query:
                    try:
                        source = source or WinRTSource()
                        query_started = time.time()
                        query = asyncio.create_task(self._snapshot(source))
                    except ImportError:
                        self.unavailable('Unavailable: install the WinRT packages from requirements.txt.')
                    except OSError:
                        self.unavailable('Notification listener unavailable. Use Allow access / Retry.')
                    next_query = time.monotonic() + POLL_SECONDS
                # Poll infrequently, but use stop.wait off-thread so quitting stays prompt.
                await asyncio.to_thread(self.stop.wait, FOREGROUND_SECONDS)
        finally:
            if query is not None:
                query.cancel()
                await asyncio.gather(query, return_exceptions=True)
            self.unavailable('Stopped')

    async def _snapshot(self, source):
        return await asyncio.wait_for(source.snapshot(), timeout=5)
