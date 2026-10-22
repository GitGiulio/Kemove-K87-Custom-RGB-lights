# CPU Optimizations Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, task by task, using the checkboxes. Implemented and verified with 56 passing tests; see the companion progress ledger, baseline/optimized measurements, and VALIDATION.md for evidence and remaining manual checks.

**Goal:** Reduce avoidable CPU work while preserving the existing lighting, notifications, GUI behavior, and configured update rates.

**Architecture:** Keep Pillow ImageGrab and the current worker structure. Add revision-aware settings reads, cache stable lighting results and encoded reports, separate state advancement from final frame assembly, and wait for settings changes when a feature is disabled.

**Tech Stack:** Existing Python, threading, asyncio, ctypes, Pillow, Tkinter, and unittest. No new dependencies or capture backend.

**Spec:** The behavior contract below and the user's requested five optimizations are the specification for this plan.

## Behavior contract and global constraints

- Implement all five: avoid redundant RGB image copies, avoid repeated full settings copies, cache unchanged lighting calculations and packets, assemble frames only when output is due, and park disabled feature workers.
- Keep ImageGrab, monitor/region selection, resolution, RGB processing, and BOX resampling unchanged. Do not add GPU capture, DXGI, hooks, or raw-input monitoring.
- Preserve screen sampling from 0.125 through 30 FPS, including non-divisor rates such as 7 and 20 FPS. Do not slow configured rates or increase capture frequency.
- Preserve output rate `max(10, fps, 30 if press_enabled else 0)` and repeated USB keepalives even when every color is unchanged. A keepalive must still perform the HID write.
- Preserve the current exponential smoothing calculation, its state at capture boundaries, and rounding. Do not stop smoothing early using an approximation or brightness threshold.
- Preserve pressed-key scans every 8 ms while enabled, the minimum 80 ms tap visibility, layout changes, and current Fn limitations.
- Preserve notification queries every 10 seconds, foreground checks every 1 second while any supported app is enabled, and half-second blink phases rendered by the existing output loop.
- Continue foreground monitoring while notifications are enabled even if no alert is pending. Its acknowledgement time boundary prevents delayed notifications from blinking after the user already visited the app.
- Preserve overlay priority: screen and exceptions, then pressed keys, then the notification color during its illuminated phase. The other blink phase uses normal underlying lighting.
- Preserve notification dismissal semantics, enable/disable epochs, no replay of old notifications, transient-query-error behavior, permission recovery, and application-wide foreground acknowledgement.
- Keep GUI preview, Save, Cancel, failed-save behavior, current JSON schema, strict input validation, and defensive copying for editable GUI settings.
- Cached results must not be mutable aliases visible to callers. Bound caches to the latest useful entry; no unbounded histories or generic caching framework.
- Stop and reconnect paths must release the keyboard and wake/join parked workers without waiting for a settings change. Do not change firmware or persistent keyboard profiles.
- Use Engineering Suite Ponytail when implementing. No em dashes in prose. No unrelated refactors or new user-facing settings.

## Measurement context

The previous investigation sampled approximately 1.5% total machine CPU over 10 seconds on a 12-logical-processor machine. Current saved settings at investigation time were 5 FPS, average mode, smoothing zero, press-to-light enabled, and ChatGPT notifications enabled. These are observations, not hard-coded assumptions for implementation or a reliable long-term CPU baseline.

At 2560x1440, native capture used roughly 34 ms CPU per image. Average-color processing measured about 7.8 ms with the redundant RGB copy and 4.7 ms without it. This plan leaves the largest capture cost unchanged, so expect incremental improvements rather than promising a particular percentage reduction.

## File map and interfaces

- `settings.py`: keep `get()` as an independently editable deep copy; add revision-aware worker snapshots, atomic flag reads, and a condition for parked workers.
- `pressed_keys.py`: use the flag API and wait on settings changes while disabled; keep enabled polling unchanged.
- `notification_blinker.py`: reuse a worker-owned settings snapshot, accept a caller-provided snapshot during rendering, and park only when all supported notification rows are effectively disabled.
- `kemove_rgb.py`: skip unnecessary RGB conversion, cache stable base colors, split state advancement from final composition, and use the settings snapshot API in the main loop.
- `k87.py`: cache only the last validated colors and encoded report; preserve public validation and every requested HID send.
- `test_performance.py`: focused regression tests for the new settings APIs, cache invalidation, scheduler boundaries, disabled-worker wakeup, and packet reuse.
- Existing `test_settings.py`, `test_notifications.py`, `test_notification_ui.py`, `test_tray.py`, and `test_kemove_rgb.py`: extend or adapt meaningful existing behavior checks rather than duplicate them.
- `bench_rgb.py`: a small stdlib benchmark harness, with no hardware writes by default. Measure synthetic frame processing, settings reads, and encoding; explicit `--capture` measures native captures in memory without saving images.
- `VALIDATION.md`: record verification commands and comparable before/after measurements. Update README only if developer benchmark instructions need documenting.

Settings API additions:

- `snapshot(last_revision: int = -1) -> tuple[int, dict | None]`: under the existing settings lock, return the revision and a deep copy only when the revision differs. `None` means the consumer reuses its own previous snapshot. Workers treat their private snapshots as read-only.
- `read_flag(name: str) -> tuple[int, bool]`: return one boolean and its revision atomically, without copying the full dictionary. Restrict this to known boolean settings.
- `wait_for_change(revision: int, stop_event: threading.Event) -> None`: condition wait until revision changes or shutdown is requested. Check the predicate under the condition lock to prevent a missed settings update between reading and parking.
- `wake_waiters() -> None`: notify parked workers after their shared stop event is set. It does not alter settings or revision.
- Increment revision and notify the condition when `preview()` or `cancel()` changes effective configuration. Saving unchanged configuration does not increment it. Invalid preview and failed save do not publish partial configuration.

Rendering interfaces:

- `FrameEngine.advance(now, options) -> None`: perform capture when due, update deadlines, and advance target/smoothing state once for that loop timestamp. Do not round or apply overlays here.
- `FrameEngine.render(options, pressed, notifications=None) -> list[tuple[int, int, int]]`: assemble the current output using the cached base when valid, returning a caller-owned list.
- Retain `FrameEngine.frame(now, options, pressed, notifications=None)` as the compatibility wrapper calling advance then render, so tests and direct callers keep their current interface.
- `NotificationService.overlay(now, options=None, revision=None)`: optionally consume the main loop's already-read snapshot and its revision, rejecting snapshots older than the applied configuration. Standalone calls retain correct behavior using a service-owned revision-aware snapshot. Continue synchronizing enable/disable transitions under the existing lock.
- Preserve the public `Keyboard.send(colors)` and `encode_frame(colors)` interfaces, strict channel validation, and existing packet bytes.

## Review focus

1. A rapid disable/re-enable or Cancel must not be hidden by settings caching and replay a stale notification. Pin this to Task 2's existing notification epoch tests and Task 4's wakeup tests.
2. A capture deadline occurring between USB deadlines must update sampling and smoothing without building an unused final frame. Pin this to Task 5's independent-clock tests.
3. A cached returned color list modified by an overlay or a caller must not corrupt later output. Pin this to Task 3's ownership tests.
4. Invalid values equal to cached integers, such as booleans and floats, must still fail validation. Pin this to Task 3's packet-cache tests.
5. Shutdown while disabled, a settings update just before parking, or an outstanding notification query must not strand a thread. Pin this to Task 4's deterministic race/cancellation tests.

## Task 1: Capture reproducible baseline and protect image equivalence

**Files:** create `bench_rgb.py`, create `test_performance.py`, modify `kemove_rgb.py`, record in `VALIDATION.md`.

- [x] Run `.\.venv\Scripts\python.exe -m unittest -q`; record the starting result, expected currently 40 passing tests. If the repository changed, inspect the differences before proceeding.
- [x] Add `bench_rgb.py` using `time.process_time`, `time.perf_counter`, and repeated medians. Report settings reads, repeated average/spatial image processing, unchanged and changing frames, and repeated packet encoding. Use the current configuration plus a 30 FPS case and no screenshots saved. Native capture is opt-in and does not write to the keyboard.
- [x] Run `.\.venv\Scripts\python.exe bench_rgb.py` before optimization and save the printed baseline in VALIDATION.md. Record configuration, resolution, workload, repetitions, and CPU versus wall time.
- [x] Add `test_rgb_input_is_not_converted_or_copied`: pass a real RGB image with its `convert` method instrumented, call both lighting modes, require no conversion and unchanged expected colors.
- [x] Add non-RGB equivalence tests for L, RGBA, and palette images, plus nonuniform RGB images at odd dimensions and brightness values 0, 0.36, and 1. Expected colors must match the old conversion/BOX algorithm exactly; the input image must remain unmodified.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance`; confirm the no-copy test fails before implementation.
- [x] Change `colors_from_image` to reuse RGB input directly and convert only other modes. Keep all other processing and validation intact.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance test_kemove_rgb`; require all tests to pass.

## Task 2: Eliminate repeated settings copies in hot paths

**Files:** `settings.py`, `pressed_keys.py`, `notification_blinker.py`, `kemove_rgb.py`, `test_performance.py`, existing settings/notification tests.

- [x] Add failing tests named `test_snapshot_copies_only_on_revision_change`, `test_flag_and_revision_are_atomic`, `test_gui_get_remains_independently_editable`, and `test_preview_cancel_and_failed_save_preserve_revisions`. Assert unchanged reads return `(same_revision, None)` without deepcopy; a new snapshot cannot mutate the store or another consumer's snapshot.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance`; confirm the new API tests fail.
- [x] Implement snapshot/read_flag and revision publication inside the existing store lock. Reuse that lock in a threading.Condition for Task 4, rather than adding a second competing settings lock. Validate before publication.
- [x] Change the main loop to retain a private snapshot and refresh it only on revision changes. Pass the same snapshot to notification overlay rendering, avoiding its current extra copy on every lighting iteration.
- [x] Use read_flag in the enabled press scanner. Give the notification worker its own retained snapshot; avoid rebuilding its configured rules on unchanged options while retaining the state lock and epoch synchronization.
- [x] Preserve enable/disable boundaries observed by rendering between one-second notification ticks. When supplied options differ from the service's last applied configuration, process transitions before returning its overlay; do not rely solely on the worker's cached revision.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance test_settings test_notifications test_notification_ui test_ui_save test_tray`; require all tests to pass, including the existing between-monitor-ticks regression.

## Task 3: Cache stable base colors and encoded reports

**Files:** `kemove_rgb.py`, `k87.py`, `test_performance.py`, `test_kemove_rgb.py`.

- [x] Add failing tests `test_unchanged_zero_smoothing_reuses_base`, `test_base_cache_invalidates_all_dependencies`, `test_overlay_or_caller_mutation_cannot_corrupt_cache`, and `test_packet_cache_reuses_bytes_but_still_writes`. Instrument expensive work rather than asserting wall-clock speed in unit tests.
- [x] Add `test_cached_packet_still_rejects_invalid_channels`: warm the cache, then submit booleans, floats numerically equal to valid channels, out-of-range values, and malformed frame lengths; all must still raise ValueError. Add failed-send, reconnect, and first-send tests.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance`; confirm the cache instrumentation tests fail.
- [x] Cache brightness-scaled target values until the sample or brightness changes. Cache rounded base colors plus exceptions only when smoothing is zero. Continue each scheduled capture even if the previous result was unchanged.
- [x] Invalidate the base on mode/sample, brightness, smoothing-mode, or exception changes, including Cancel. Keep exception comparison independent of dict insertion order. Retain full smoothing advancement when smoothing is nonzero; do not introduce convergence shortcuts.
- [x] Retain the cached base as immutable tuples and return a fresh list for overlays. Evaluate pressed keys and notification phase for every actual output, regardless of cache hits.
- [x] Split existing packet validation from byte construction only as needed: normalize and strictly validate every public send, then reuse the last encoded bytes when normalized integer RGB values match. Keep one cache entry per keyboard instance and clear it on close/reopen. Do not skip writes on a cache hit.
- [x] Keep encode_frame's packet header, 520-byte size, RGB ordering, and zero padding identical. Do not use functools memoization with unbounded keys or equality checks that bypass type validation.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance test_kemove_rgb test_settings test_notifications`; require passing results and unchanged packet bytes.

## Task 4: Park disabled workers and wake safely

**Files:** `settings.py`, `pressed_keys.py`, `notification_blinker.py`, `kemove_rgb.py`, `kemove_tray.py`, `test_performance.py`, worker/lifecycle tests.

- [x] Add failing deterministic tests `test_disabled_press_worker_waits_for_change`, `test_disabled_notifications_never_query_foreground_or_source`, `test_change_before_wait_is_not_lost`, `test_cancel_wakes_workers`, and `test_shutdown_wakes_all_parked_workers`.
- [x] Implement wait_for_change and wake_waiters with the shared settings condition. Tests must coordinate with Events or a fake condition, not arbitrary long sleeps.
- [x] When press-to-light is disabled, publish an empty active set once and park using the revision returned atomically with its flag. On wake, reread the flag before querying key state. Preserve the 8 ms scan interval and 80 ms minimum visibility while enabled.
- [x] When no supported notification row is effectively enabled, cancel/drain any outstanding query, clear pending effects through normal configuration handling, and wait for settings changes. Do not call GetForegroundWindow or WinRT snapshot while parked.
- [x] Keep notification access actions usable while disabled: the explicit GUI permission callback can update status without starting background polling. Enabling a row wakes the worker and initiates a fresh source check with the existing enable-time boundary. Retry while enabled still works.
- [x] Use asyncio.to_thread for the notification condition wait so Tk and the notification event loop are not blocked. Ensure shutdown sets stop and calls wake_waiters before joins, including CLI --seconds, Ctrl+C, tray Quit, worker error, and startup cleanup paths.
- [x] Do not park an enabled notification worker merely because no alert is pending. Keep one-second foreground checks for acknowledgement boundaries and ten-second source checks.
- [x] Test disabling with a pending slow query, reenabling, rapid toggles, and shutdown with both workers parked. Require threads to join within one second in controlled unit tests without waiting for a notification poll.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance test_settings test_notifications test_tray test_notification_ui`; require all tests to pass.

## Task 5: Assemble final frames only when output is due

**Files:** `kemove_rgb.py`, `test_performance.py`, `test_settings.py`, `test_tray.py`.

- [x] Add failing tests `test_capture_between_output_deadlines_does_not_render`, `test_capture_count_is_independent_of_output_rate`, `test_smoothing_matches_reference_at_output_times`, and `test_long_capture_does_not_trigger_busy_spin_or_catchup_queue`.
- [x] Use a fake clock, deterministic image sequence, and fake keyboard. Exercise screen rates 0.125, 5, 7, 20, and 30 FPS; press enabled/disabled; smoothing 0, 0.08, and 2 seconds; changed configuration; and late/overslept deadlines. Record the pre-refactor engine's outputs as the reference at identical timestamps.
- [x] Split FrameEngine into advance and render as specified. Call advance once at every current loop wake so capture deadlines and smoothing integration remain unchanged. Call render and fetch pressed/notification overlay snapshots only if the existing output deadline is due.
- [x] Keep frame as the backward-compatible advance-plus-render wrapper. Do not add another periodic loop or move capture into a separate thread.
- [x] Retain the current minimum-deadline wait and missed-capture skip logic. Preserve output rate calculation and reconnect behavior; discard stale work rather than queueing missed frames.
- [x] Preserve the first frame after startup/reconnect, live edits between capture samples, key release, notification acknowledgement, and blink phase transitions at slow screen rates. Tests must prove unchanged output colors at corresponding deadlines, not merely a plausible average FPS.
- [x] Run `.\.venv\Scripts\python.exe -m unittest -v test_performance test_settings test_notifications test_tray test_kemove_rgb`; require passing results and fewer render calls than state-advance calls in the between-deadlines case.

## Task 6: Verify behavior and measure the actual improvement

**Files:** `bench_rgb.py`, `VALIDATION.md`; README benchmark instructions only if useful.

- [x] Run `.\.venv\Scripts\python.exe -m unittest -v`; require all existing and added tests to pass.
- [x] Rerun `.\.venv\Scripts\python.exe bench_rgb.py` with the same before/after workload and configuration. Report medians for image processing, unchanged/changing frames, settings, and encoding. Separate CPU savings from wall-clock/HID waiting and do not sum overlapping microbenchmarks into a claimed whole-app percentage.
- [ ] Compare the running app's process CPU counters in matching conditions for three 30-second windows before and after, with the same resolution, current settings, foreground workload, and keyboard activity. Report both percent of one logical core and percent of the whole machine; avoid profiling another Python process or a stale tray instance.
- [ ] Include static desktop, changing screen content, pressed keys, and pending notification scenarios. Confirm actual capture counts and output cadence did not decrease to produce the apparent saving. No claim of native capture savings is expected because its backend is unchanged.
- [ ] Inspect the Notifications and Lighting tabs: preview/Save/Cancel, toggles, custom colors/keys, and access status must behave as before. Verify disabling and reenabling does not replay old alerts.
- [ ] Live check USB keepalives, slow sampling, key tap visibility, notification foreground acknowledgement, and clean quit. Record checks requiring physical observation as pending if they were not observed; do not substitute successful writes for visual evidence.
- [x] Review the complete change for stale caches, shared mutable state, missed condition notifications, and weakened validation. Fix substantive findings with a failing regression first, then rerun the full suite.
- [x] Record the final measured benefit and remaining dominant costs in VALIDATION.md. Do not promise a total CPU reduction if whole-app measurements are inconclusive. Keep saved user preferences unchanged.

## Execution notes

The tasks share settings and rendering interfaces and should be implemented inline in order. No parallel agents are required for implementation. Work in the existing folder if it still has no Git metadata; do not create a repository or duplicate the environment just for this optimization. If a Git checkout is available at execution time, follow its instructions and commit coherent verified tasks.

The user subsequently authorized implementation. Product changes, automated verification, microbenchmarks, and native worker verification are complete. The existing tray process was left running; matched whole-app CPU measurements, physical lighting confirmation, and live sleep/reconnect remain manual checks. Saved preferences and the capture backend are unchanged.
