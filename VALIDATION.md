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
