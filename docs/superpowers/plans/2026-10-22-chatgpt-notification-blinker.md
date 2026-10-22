# ChatGPT Notification Blinker Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Track progress using the checkboxes. Implementation is underway; see the companion progress ledger and VALIDATION.md for evidence and remaining physical checks.

**Goal:** Blink a configurable key and color for new ChatGPT notifications until the user brings ChatGPT to the foreground, with GUI controls designed to accommodate additional supported apps.

**Architecture:** A Windows notification worker supplies metadata to a small in-memory alert state controller. The existing lighting loop applies that controller's overlay after other effects. Settings contain a master switch and a mapping of supported app settings; the GUI builds its application rows from the same small application catalog.

**Tech Stack:** Existing Python 3.12+, Tkinter/ttk, Pillow, threading, ctypes, and unittest. Use Windows UserNotificationListener through Python WinRT bindings if the initial access test succeeds. A packaged C# listener helper is the fallback if reliable access requires a packaged Windows component.

**Spec:** The behavioral design below is the specification for this plan. Defaults and implementation choices marked as proposed can be revised before execution.

Latest steering: query Windows notifications every **10 seconds** and monitor foreground every **1 second**. This supersedes the original faster polling proposal.

## Global constraints

- Windows and the existing verified wired K87 transport only.
- ChatGPT is the only supported application in this release; do not add Telegram integration or a placeholder Telegram row.
- Use Engineering Suite Ponytail for code changes. Reuse the existing settings store, color wheel, layout, worker lifecycle, and lighting transport.
- Do not install dependencies, register packages, request notification access, or change product code during planning.
- Do not read message bodies, log notification content, dismiss notifications, modify ChatGPT, or write keyboard firmware or saved profiles.
- No em dashes in prose.

## Behavioral design

### User-visible behavior

1. Proposed initial settings: master notification switch off; ChatGPT row enabled; key F8 (layout LED index 54); color red [255, 0, 0]. The master switch makes the feature opt-in for existing installations.
2. A new Windows notification attributed to the installed ChatGPT application activates one pending alert if both switches are enabled and ChatGPT is not foreground.
3. Blink once per second: 500 ms at the chosen color, then 500 ms at the key's current underlying lighting. Apply the notification color at its selected RGB intensity, independently of screen brightness, matching the existing press overlay's behavior. A black selected color intentionally produces a dark phase.
4. Keep blinking indefinitely until any window belonging to the configured ChatGPT application becomes foreground. Opening the app, clicking a notification, and Alt+Tab all qualify if they actually foreground ChatGPT. Merely hovering or having it visible behind another app does not.
5. Clearing a Windows notification or Notification Center does not acknowledge the alert. App exit or notification expiry does not acknowledge it either.
6. Notifications received while ChatGPT is already foreground are considered acknowledged and do not start a blink. After foreground acknowledgement, switching away does not restart an old alert; only a new notification can do that.
7. Multiple new notifications coalesce into one alert. They do not queue, multiply blink speed, or reset its phase.
8. Disabling the master switch or ChatGPT row clears its pending alert immediately. Re-enabling starts from new notifications only. Key/color edits apply immediately to any active alert and release the old key.
9. RGB app restart, listener recovery, and re-enabling reject notifications created before their enable boundary without replaying them; fresh notifications after enabling are eligible even in the first snapshot. Permission recovery establishes a new baseline. Pending alerts are session-only and are not persisted.
10. USB disconnection retains pending state while the process runs; reconnect resumes blinking unless ChatGPT has been foregrounded meanwhile. Disabling, permission loss, and shutdown clear output overrides; a transient query failure preserves pending alerts.

### Foreground detection and identity

- Use GetForegroundWindow, GetWindowThreadProcessId, OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION), and GetApplicationUserModelId through ctypes. Close every process handle; cache by current window/PID, never by PID alone across process lifetime.
- Match the exact application identity, not window titles or a loose executable-name substring. The identity observed on this computer is OpenAI.Codex_2p2nqsd0c76g0!App. Verify it against a real notification and each relevant ChatGPT window in Task 1.
- The installed app exposes ChatGPT/Codex surfaces under one package. Proposed acknowledgement scope is any foreground window with that application identity, rather than one particular conversation. Record if real foreground identities do not distinguish these surfaces.
- Poll foreground every 1 second in the notification worker. This intentionally trades detection of extremely brief focus changes for avoiding global hooks; verify ordinary switching clears the light within about 1 second plus rendering delay. A NULL window or inaccessible process means unknown, never acknowledgement.
- Process notification observations first and foreground acknowledgement last on each worker tick. Keep an acknowledgement time boundary so delayed observations of notifications created before acknowledgement cannot re-arm the alert. Use source notification creation times for this comparison, not the time a callback is delivered.

### Notification capture and access

- First prove real notifications are observable using the supported UserNotificationListener API. Installing ChatGPT alone does not prove its notifications reach this API.
- Prefer a Python listener in the current process if Task 1 proves permissions, actual capture, and normal startup all work. Keep a blocked/denied state visible instead of assuming an empty notification list means success.
- If that fails because application identity/capability packaging is required, use one minimal packaged C# listener helper. It emits newline-delimited JSON metadata over redirected stdout to its parent, with no network listener or shared file. Python owns its lifetime. It must not inherit another application's identity or alter another package's manifest.
- Prefer change events where reliable. A ten-second GetNotificationsAsync snapshot comparison is the fallback if event subscription fails. Polling can miss notifications created and removed between snapshots; document this ceiling if used.
- Identify observations by application identity, notification ID, and creation time; replacements with the same identifier/time do not count as new. Establish a baseline at startup and after access recovery. Dismissals update source bookkeeping only, never pending-alert state.
- Retain deduplication records only for notifications in the current source snapshot plus acknowledgement boundaries; avoid an unbounded history. Reject stale asynchronous snapshots after a newer baseline or acknowledgement.
- Query only app identity, notification ID, and creation time. Filter unrelated applications immediately. Permission scope remains broader than the filter because Windows grants notification-listener access generally.
- Request access only from an explicit GUI action, on a supported UI thread. Do not prompt on background startup. Show unavailable, access required, denied, connected, or failed status; provide an explicit retry/setup action.
- Permission revocation clears the active overlay, leaves other lighting running, and shows a concise status. Recover with a new baseline so stale notifications do not replay. Transient query failures preserve pending alerts while retrying, so they do not silently acknowledge notifications.

### GUI and settings

- Convert the current Settings body to a ttk.Notebook with Lighting and Notifications tabs. Preserve existing lighting controls; keep Save and Cancel outside the tabs.
- Notifications contains an Enable notification blinkers master checkbox, access status/setup controls, and an application table with Application, Enabled, Key, and Color columns.
- Initially show one ChatGPT row. Populate rows from a plain supported-app dictionary keyed by stable IDs such as chatgpt. Adding another supported app later should add catalog data and source matching, without rewriting GUI row construction.
- Use a read-only ttk.Combobox populated from all 87 named layout keys. Store the LED index, not its position in the list. Reuse ColorWheel and show a color swatch and hexadecimal value.
- Store notifications_enabled and notification_apps, with each app entry containing enabled, key_index, and color. Merge nested defaults so older settings files and future added app entries work without resetting current preferences.
- Validate booleans strictly, indices against real layout keys, and RGB integers in 0..255. Keep unknown app entries inert and preserve them through save, while validating their structure, so changing versions does not activate unsupported applications.
- Future apps may share a key. Define deterministic arbitration now without a UI feature: most recently activated pending app owns the key until cleared; ties use stable catalog order.
- Existing Save/Cancel semantics apply to configuration and live previews. Cancel restores saved switches/key/color. It does not rewind real notifications or resurrect pending alerts cleared during a disabled preview; explain that runtime acknowledgement is not an editable preference.
- Include text: Blinks until the application is brought to the foreground. Dismissing its notification does not stop blinking.
- Do not add blink-rate controls, arbitrary application discovery, plugin interfaces, message filters, or per-conversation rules.

## Files and interfaces

- Create notification_blinker.py: plain app catalog, small alert controller, Windows foreground matching, and notification worker. Keep the pure state portion testable without Windows calls.
- Modify settings.py: nested defaults and validation; retain atomic save and thread-safe snapshots.
- Modify kemove_rgb.py: accept a snapshot of active notification colors in FrameEngine.frame; compose after press-to-light. Start/stop the notification worker alongside the existing key-state worker, even during keyboard reconnect waits.
- Modify settings_ui.py: notebook and reusable application rows, existing color picker, access action, and status refresh using Tk after callbacks.
- Modify kemove_tray.py: pass notification service access/status callbacks to SettingsWindow and manage startup/shutdown without blocking Tk.
- Modify requirements.txt only after Task 1 selects and verifies the capture route.
- Add test_notifications.py; extend test_settings.py and test_ui_save.py where appropriate.
- Update README.md and VALIDATION.md with setup, semantics, limitations, and actual live-test results.
- Conditional only: notification_helper/ contains the smallest C# listener project and manifest plus reproducible build/install/uninstall instructions if the capture checkpoint requires packaging.

Target Python interfaces:

- APP_CATALOG: dictionary from stable app ID to display name, Windows AUMID, and default key/color. Notification identity strings do not live in settings.json.
- AlertState.observe(app_id, notification_id, created_at, now): consume metadata with no body text.
- AlertState.acknowledge(app_id, through_time): clear pending state and ignore delayed older observations.
- AlertState.configure(options): apply enable state and key/color preferences.
- AlertState.overlay(now): return a dictionary mapping LED index to RGB tuple for currently illuminated blink phases; absent entries retain underlying lighting.
- NotificationService(settings, stop_event): owns worker thread and thread-safe snapshots; exposes overlay(now), status(), and request_access(). GUI access requests are marshalled to the capture route's required UI context.
- FrameEngine.frame(now, options, pressed, notifications=None): optional overlay mapping preserves existing callers and tests.

## Review focus

- A notification dismissed before foreground acknowledgement must leave the blinker running. Test in Task 2 and live in Task 5.
- Delayed or repeated observations after acknowledgement must not restart blinking. Test in Task 2.
- Foreground queries can fail or return NULL during switching; they must not acknowledge or stop lighting. Test in Task 2.
- Missing nested settings fields and future unsupported application entries must survive upgrades safely. Test in Task 3.
- Permission loss, unavailable listener, and malformed helper output must not terminate the lighting loop or block GUI shutdown. Test in Tasks 1 and 5.

## Implementation tasks

### Task 1: Prove capture and foreground matching on this machine

**Files:** notification_blinker.py capture adapter; conditional notification_helper/; requirements.txt; VALIDATION.md.

- [x] Confirm real ChatGPT notification AUMID and foreground-window identity through metadata-only diagnostics. Trigger a genuine completion notification and ordinary window focus changes. Do not send messages to another chat without user authorization; request a manual trigger if necessary.
- [x] Test Python WinRT access from the required UI context, including a real captured notification. AccessStatus=Allowed by itself is insufficient evidence.
- [ ] If the ordinary Python route cannot reliably read notifications, implement the packaged helper route and prove the same test before continuing. Record exact capability declaration, package/signing/setup needs, build command, and uninstall steps. Do not silently replace native capture with database scraping or UI scraping.
- [x] Test event subscription; if broken, demonstrate ten-second snapshot polling and record its latency/missed-short-notification limitation.
- [x] Establish the adapter contract: added notification metadata, source status, and initial/recovery baseline. Removed notifications do not emit acknowledgements.
- [ ] Add adapter checks for denied/revoked access, malformed metadata, retry, and bounded shutdown; run the corresponding unittest cases. Test denied access on a disposable/mock adapter rather than changing unrelated permissions.
- [ ] Record actual evidence and selected runtime dependencies. If neither supported route captures ChatGPT notifications, stop integration and report the specific blocker instead of shipping a nonfunctional toggle.

### Task 2: Implement and test alert lifecycle and foreground acknowledgement

**Files:** notification_blinker.py; test_notifications.py.

- [x] Write deterministic tests with a fake clock/source for first notification, duplicate/coalesced events, ignored unrelated apps, foreground-at-arrival, dismiss-without-clear, foreground clear, delayed observations, and fresh notification after switching away.
- [x] Add tests for half-second phases, key/color changes during an alert, master/app disable, restart/recovery baselines, failing foreground queries, and deterministic same-key arbitration using synthetic catalog entries only.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest -v test_notifications` and confirm tests fail for the missing behavior.
- [x] Implement the specified state/controller interfaces with pending timestamps and minimal source bookkeeping. Use a lock for alert state and configuration transitions shared between the worker and rendering thread; GUI callbacks update only settings or request access.
- [x] Implement foreground checks and acknowledgement ordering; test process handles close on success and failure.
- [ ] Run the same test command and require all cases to pass.

### Task 3: Add validated persistence and Notifications GUI

**Files:** settings.py; settings_ui.py; kemove_tray.py; test_settings.py; test_ui_save.py.

- [x] Add failing tests for loading existing settings, deep merging missing app fields, invalid RGB/key/bools, inert unsupported app entries, independent app preferences, atomic save, and preview/cancel restoration.
- [x] Implement master/app defaults and nested validation using the existing store. Default master off, ChatGPT enabled, F8/index 54, red [255, 0, 0].
- [x] Add the notebook and catalog-driven application rows. Reuse the existing ColorWheel and expose all layout keys in a read-only selector.
- [x] Add explicit access setup/retry and status display. Keep access state separate from persisted enabled preference; enabled-without-access clearly reports Access required.
- [ ] Exercise Save, Cancel, window close, and save failure. Test that status refresh stops when the window is destroyed and that worker callbacks never directly touch Tk widgets.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest -v test_settings test_ui_save` and require passing results. Visually inspect both tabs at normal and increased Windows scaling, keyboard navigation, and a synthetic multi-row catalog.

### Task 4: Compose alert colors into the current lighting stream

**Files:** kemove_rgb.py; notification_blinker.py; test_settings.py; test_notifications.py.

- [x] Add failing frame tests for notification precedence over pressed/fixed/OFF keys, normal lighting in the off phase, unchanged unrelated keys, and restoration after acknowledgement.
- [x] Extend FrameEngine.frame with the optional notifications mapping and apply it last, outside smoothing. Leave hardware transport unchanged.
- [x] Integrate NotificationService snapshots and shutdown with the existing run loop. Use monotonic time for blink phase and retain existing minimum 10 FPS output, so the 0.125 FPS screen sampling option does not slow blinking.
- [ ] Verify notification state and foreground monitoring continue while the lighting loop waits two seconds between USB reconnect attempts. Worker failure is reported separately and does not set the global application stop event.
- [ ] Run `.\.venv\Scripts\python.exe -m unittest -v test_settings test_notifications test_kemove_rgb` and require passing results.

### Task 5: Verify the complete user flow and document setup

**Files:** test_notifications.py; README.md; VALIDATION.md; capture/setup files selected in Task 1.

- [x] Run `.\.venv\Scripts\python.exe -m unittest -v` and record the result.
- [ ] Live test: enabled + background ChatGPT + genuine notification starts red F8; dismiss notification and confirm it continues; foreground ChatGPT by click and Alt+Tab and confirm it stops within about 1 second plus rendering delay under normal load.
- [ ] Live test: notification while ChatGPT is foreground does not blink; switching away does not replay it; a genuinely new background notification starts another alert.
- [ ] Change key/color while pending; confirm the old key restores and the new key blinks. Verify Save persists across restart and Cancel restores configuration.
- [ ] Verify app-only and master switches each stop a pending alert and re-enable without replay. Check both OFF/fixed key exceptions and press-to-light conflicts.
- [ ] Verify listener unavailable, permission denied/revoked, helper failure if used, sleep/wake, USB unplug/replug, settings reopen, startup, and clean tray Quit. No unrelated lighting regression or orphan helper process is acceptable.
- [x] Record whether any ChatGPT/Codex window acknowledges the alert under this installed identity. State clearly that foreground acknowledgement is application-wide, not proof a particular conversation was read.
- [x] Document permission breadth, actual setup/package requirements, native-notification dependency, polling ceiling if used, indefinite blink semantics, full selected color intensity, and wired-only support.
- [x] Review the final diff for scope and run the full suite once more only if review caused changes. No production-complete claim until real notification and physical keyboard behavior have been observed.

## Estimate and handoff

Expect approximately 1 to 3 working days after capture is proven; Windows packaging can add time. Supporting only ChatGPT reduces integration and UI testing, but does not remove listener access requirements. The foreground acknowledgement rule is straightforward once identity matching is verified.

Implementation status: code is implemented, 40 automated tests pass, native capture and identity matching work, and the GUI preview was visually checked. Physical end-to-end confirmation remains pending, as documented in VALIDATION.md and the companion progress ledger. The user authorized implementation after this plan was delivered. Execute inline using the existing repository conventions; no parallel agents are required for these dependent tasks. The directory currently has no .git metadata, so commit steps apply only if a Git checkout is available at execution time.

## References

- [Microsoft notification listener](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener): capability, permission, notification metadata, and change handling.
- [GetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow): foreground detection and possible NULL results.
- [GetWindowThreadProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowthreadprocessid): foreground process lookup.
- [GetApplicationUserModelId](https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getapplicationusermodelid): identity lookup using limited process-query rights.
- [Windows App SDK event-subscription issue](https://github.com/microsoft/WindowsAppSDK/issues/6172): reported unpackaged event failure; an implementation risk to verify, not proof of this machine's behavior.
