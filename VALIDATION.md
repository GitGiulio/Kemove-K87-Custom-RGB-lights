# Current validation

## Runtime and regression checks

All 61 tests pass. Run `.\.venv\Scripts\python.exe -m unittest -v` to exercise color mapping, smoothing, frame scheduling/caching, USB packet validation, settings persistence and rollback, worker shutdown, notification acknowledgement, and actual Tk controls. Tests use fake keyboard transport and temporary settings.

Screen capture tests cover reuse of the MSS session, mapping raw bytes without a full-frame copy, exact RGB results in both lighting modes at multiple brightness settings, primary-display geometry changes, negative and cross-monitor regions, failure/backoff/recovery, dark startup, and idempotent cleanup.

## Screen capture, 23 October 2026

- MSS 10.2.0 is the sole capture backend for both primary-monitor and explicit-region capture. There is no background capture thread, backend fallback, DXcam compatibility patch, or Windows Graphics Capture session.
- Raw BGRA storage is mapped into a Pillow image without copying. BOX reduction runs before swapping the color channels on the small result: 60x20 pixels for spatial mode, 1x1 for average mode. Tests compare the resulting LED colors exactly against full RGB conversion on deterministic 101x61 and 2560x1440 images.
- Pillow remains necessary for reduction, color operations, and the tray icon. NumPy, comtypes, DXcam, and capture-only WinRT dependencies have been removed. Notification WinRT bindings remain in use.
- Capture failures release the session and retry after two seconds, retaining the last image while overlays and USB keepalives continue. The primary-monitor dimensions are queried on each sample to avoid stale cached geometry after a display change.
- Native checks captured the 2560x1440 primary screen and a 160x120 region. The complete lighting loop ran for three seconds with fake USB transport, produced 27 output frames, and released capture resources on shutdown. No keyboard writes were made.
- A short 30-frame native capture-plus-spatial-reduction benchmark measured approximately 16 to 17 ms process CPU per frame on this machine. This is a component measurement, excluding actual USB transport and complete tray overhead.
- Protected content, HDR accuracy, and desktop/session transitions still require the manual checks below.

## Keyboard and notification behavior

The wired K87 model identity and transient 520-byte RGB frame format are checked before lighting writes. Keepalives still occur at a minimum of 10 FPS; press-to-light requests 30 FPS output independently of screen sampling. The app does not send firmware, keymap, reset, or profile-save commands.

Native ChatGPT notification metadata was verified under `OpenAI.Codex_2p2nqsd0c76g0!App`. Notification queries remain every 10 seconds and foreground checks every 1 second. Blink acknowledgement is application-wide, including ChatGPT/Codex windows, and does not require dismissing a toast. Transient notification-query failures preserve active alerts.

## Remaining manual checks

- Physical end-to-end confirmation of a new ChatGPT notification causing the chosen key to blink and foregrounding ChatGPT stopping it.
- Prolonged operation, lock/unlock, sleep/wake, monitor unplug/replug, rotated displays, and full HDR/game combinations on each target system.
- Full Windows sign-out/sign-in startup behavior and physical press feedback on every key. Windows key state does not distinguish keyboards or expose Fn.

No saved user settings, startup registry entries, keyboard firmware, or running tray process were changed by the automated tests. Historical plans, obsolete pre-GUI backups, and the unused OpenRGB source patch were removed; current code and regression tests remain.
