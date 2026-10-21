# GUI implementation plan

Goal: Extend the existing tray app with live settings, persistent Save/Cancel, exact keyboard diagram, a color wheel, and a full-brightness pressed-key overlay.
Architecture: Tk owns the main thread, pystray runs on its Windows thread, and the lighting worker reads validated snapshots. Keep screen capture timing separate from USB keepalives. Native Windows key-state polling stores only temporary physical key state, never typed text.
Tech stack: existing Python, Tkinter, Pillow, pystray, ctypes.

- [ ] Add validated settings persistence, independent capture schedule, exception compositing and regression tests.
- [ ] Extend vendor layout with names, rectangles and physical scan codes. Add opt-in press polling. Fn has no normal OS event; keep configurable base exception but disclose unsupported press detection.
- [ ] Add Tk sliders, keyboard selector, HSV wheel, Save/Cancel, startup checkbox and tray Settings command. Closing the window cancels unsaved previews, not the app.
- [ ] Verify offline suite, GUI smoke checks, live USB operation at both rate extremes, and review the complete change.
- [ ] Save code and updated usage instructions in the requested PyCharm folder, then restart the tray app.

Decisions: refresh slider steps 0.125, 0.25, 0.5, and integers 1..30. Base lighting output runs at least 10 Hz for keepalive; press mode uses 30 Hz output independent of screen sampling. Key polling is separate so slow screen capture does not lose ordinary taps; very brief taps are shown for at least 80 ms. Fixed exceptions obey global brightness; press overlay ignores it and is applied after smoothing. Startup remains off unless changed by the user. Tests use isolated staging files before deployment.
