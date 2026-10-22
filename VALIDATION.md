# Validation, 21 October 2026

The finished application is saved in `C:\Users\giuli\PycharmProjects\KEMOVE_RGB`, with its own prepared `.venv` and pinned dependency.

## Completed checks

- The owner confirmed the physical red/green/blue sequence and return to built-in lighting.
- The owner confirmed screen colors and left/right placement on the keyboard.
- The earlier screen prototype delivered 596 frames in about 60 seconds.
- The finished application ran from this PyCharm project for 30 seconds, sending 300 frames without reported transport errors.
- A concurrent second launch exited with the expected already-running message.
- After the final smoothing correction, all eight offline tests passed in the destination environment.
- A final hardware run with slow smoothing sent 100 frames in 10 seconds and exited successfully. The application was left stopped.

The smoothing regression check verifies that long fades reach black instead of stalling because of repeated integer rounding. Frames are rounded only when sent to the keyboard.

## Limits of verification

Reconnect and capture-failure handling are covered with simulated failures in unit tests. A physical unplug/replug, extended endurance session, secondary-monitor setup, HDR capture, and an individual visual check of every key were not performed. The user confirmed spatial mapping overall.

The optional OpenRGB source patch was not compiled or installed. Its build stopped because Windows SDK header crtdbg.h was unavailable. This does not affect the standalone application's verified operation.

## Tray update

Ten offline tests passed, including the graceful stop signal and scoped startup-registration behavior. A real pythonw.exe integration run verified that no console was attached, displayed the tray icon, sent 32 frames, invoked the actual Quit menu callback, and returned cleanly. This was a programmatic callback check, not a physical mouse-click check. Startup is left off at the owner's request. A full Windows sign-out/sign-in startup test has not been performed.


## GUI update, completed 22 October 2026

- All 17 offline regression tests passed from the destination project environment.
- GUI smoke tests exercised all 87 rendered key positions, both slider endpoints, fixed-color editing, press-mode toggle, HSV wheel selection, Save/reload, and Cancel rollback. The window was rendered and visually inspected; the apostrophe label was corrected.
- Review found and corrected non-divisor sampling-rate drift and a failed-Save startup rollback issue. Both fixes have regression tests.
- Physical keyboard trials completed without USB errors: 87 keepalive/output frames in 10 seconds with 0.125 FPS screen sampling, and 74 output frames in five seconds with 30 FPS selected. These are output counts, not claims of achieved capture FPS.
- The final integration check used a real windowless tray and Tk window with simulated keyboard transport to preserve the already-running live app. It invoked Settings, previewed key exceptions and press mode, cancelled them, invoked Quit, and verified transport cleanup. Temporary settings were used. The first attempt correctly refused a competing live instance.
- No real startup entries or user settings were changed by these tests. The existing running application was left in place.

The physical pressed-key overlay has not been individually confirmed for every key. State sampling, short-tap visibility, exception priority, and disabling the overlay are covered by regression tests. Windows-wide key state cannot distinguish keyboards and does not expose Fn. Full sign-in, HDR, restricted-application and prolonged endurance testing remain outside these checks.
# ChatGPT notification blinker validation, 22 October 2026

- Native Python WinRT capture verified outside the sandbox: access Allowed and seven existing ChatGPT metadata records returned under `OpenAI.Codex_2p2nqsd0c76g0!App`. Notification text was not accessed.
- `NotificationChanged` subscription failed with HRESULT `0x80070490` on this machine. The implementation uses snapshot queries every 10 seconds, as requested, with independent foreground checks every 1 second.
- Native service smoke test verified successful capture, existing-access GUI action, Connected status, no replay of existing notifications, and clean worker shutdown. No packaged helper was needed on this installation.
- All 40 automated tests pass. Checks cover dismiss-without-acknowledgement, foreground acknowledgement, old/delayed notification suppression, fresh notifications in the first query after enabling, transient query failures without clearing pending alerts, disable/re-enable baselines including between monitor ticks, key/color changes, overlay priority, slow capture rates, nested settings migration, persistence/Cancel, revoked access during a query, cancellation of a slow source, and actual Tk controls including a synthetic second application row.
- Metadata-only checks of 19 existing ChatGPT windows all matched the configured application identity. A temporary Notifications GUI preview was visually inspected, with no clipped controls or text at the current display scaling; saved user settings were not changed. Increased display scaling and physical sleep/reconnect behavior remain manual checks.
- Physical end-to-end confirmation of a newly arriving notification and the keyboard's resulting F8 blink is still pending. No synthetic Windows notification was sent under ChatGPT's identity, no existing notification was dismissed, and the user's existing tray process was not terminated during verification.
- Notification metadata can disappear between 10-second queries; this polling limitation is deliberate. Application-wide foreground acknowledgement cannot establish that a particular conversation was read.

# CPU optimization validation, 22 October 2026

All five approved optimizations are implemented, with the ImageGrab backend, configured rates, and JSON settings schema unchanged. The full suite now has 56 passing tests, up from the 40-test baseline.

`bench_rgb.py` uses five repeated medians, a 2560x1440 RGB image, current saved options (5 FPS, average, smoothing zero, press-to-light enabled), and fake USB writes. The baseline was collected before changing production code. Raw measurements are in `docs/superpowers/plans/cpu-baseline.json` and `cpu-optimized.json`.

| Operation | Before CPU ms/call | After CPU ms/call | Interpretation |
|---|---:|---:|---|
| Average image colors | 8.593750 | 3.515625 | About 59% less processing CPU; capture itself is excluded |
| Spatial image colors | 9.765625 | 4.687500 | About 52% less processing CPU |
| Unchanged zero-smoothing frame | 0.250000 | 0.007812 | About 97% less frame-processing CPU in this stable workload |
| Settings deep copy vs unchanged worker snapshot | 0.042969 | 0.000516 | Workers avoid copies; GUI get() remains defensive |
| Unchanged send with fake transport | 0.160156 | 0.136719 | About 15% less CPU; every actual send still writes a keepalive |
| Public uncached encode_frame | 0.148438 | 0.152344 | Slight overhead from normalization, preserving strict validation |

The old benchmark's changing_frame case actually recaptured an unchanged image. Its recorded value is now labeled resampled_static_frame without alteration. A genuinely alternating-color capture case was added separately; its current CPU time is 0.281250 ms/call and has no comparable pre-change measurement. Do not present stable-cache savings as savings on every changing frame. Small CPU timings are affected by Windows timer granularity and concurrent system activity; wall medians are included in the raw files.

Tests verify image equivalence for RGB, L, RGBA, palette, odd dimensions and brightness; defensive snapshots and revisions; cache invalidation and caller ownership; packet validation even for cached-equivalent bool/float values; keepalive writes and reconnect cache reset; independent capture/output deadlines; exact output against the frozen old smoothing engine across 0.125, 5, 7, 20, and 30 FPS and smoothing 0, 0.08, and 2; disabled worker parking; Preview/Cancel wakeup; shutdown; query cancellation; and rejection of stale render-side notification settings.

A native smoke test outside the sandbox used temporary settings and no lighting writes. Notification status reached Connected, existing notifications did not replay, disabling reached Disabled, and both native key/notification workers stopped in approximately 1.5 ms after stop plus condition notification.

Whole-app before/after CPU usage under controlled matching desktop and typing workloads has not been measured. The existing user tray process was left running, so it is not evidence of optimized-code CPU usage. Restart the tray app to load these changes. Physical key/blink/keepalive confirmation and live sleep/reconnect remain manual checks. No saved user preferences were changed, and no new dependency was installed for these optimizations.

