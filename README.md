# KEMOVE RGB

Make your **KEMOVE K87** keyboard match the colors on your screen. KEMOVE RGB is a Windows tray app with adjustable lighting, per-key colors, and an optional effect that lights keys as you press them.

It runs in the background without a console window. Open Settings from the tray icon to customize the lighting, or choose Quit to stop.

## Requirements

- **KEMOVE K87**, connected by USB in wired mode. Other models and device revisions are not verified; the app checks the keyboard identity before controlling it.
- **Windows 10/11** and **64-bit Python 3.12–3.14**, with Tkinter installed. Tkinter is included in the standard Windows Python installer.
- **64-bit OpenRGB**, installed at `C:\Program Files\OpenRGB`. The app uses its `hidapi-hotplug.dll`; OpenRGB does not need to be running or detect the keyboard.

Bluetooth and wireless connections are not supported. Close other programs that are actively controlling the keyboard's lighting.

## Install and launch

1. Download or clone this repository and open PowerShell in its folder.
2. Create a Python environment and install the dependencies:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Connect the keyboard in wired mode, then launch the tray app:

   ```powershell
   .\.venv\Scripts\pythonw.exe .\kemove_tray.py
   ```

4. Find the colorful keyboard icon beside the Windows clock. It may be under the hidden-icons arrow. Right-click it and choose **Settings...**.

For a double-click launcher, create a Windows shortcut to `.venv\Scripts\pythonw.exe`, with the full path to `kemove_tray.py` as its argument. Quote both paths if they contain spaces. Shortcuts created on another computer may need their paths updated.

To stop the app, right-click its tray icon and choose **Quit**. The keyboard returns to its built-in lighting after its live-lighting timeout.

## Customize the lighting

Changes preview immediately. **Save** remembers your settings for future launches. **Cancel**, or closing the Settings window, restores the last saved lighting settings. Closing Settings leaves the tray app running.

### Screen lighting

| Control | What it does |
|---|---|
| **Brightness** | Adjusts screen colors and fixed-key colors from 0 to 100%. |
| **Screen refresh rate** | Sets how often the screen is sampled: 0.125, 0.25, 0.5, or 1–30 FPS. |
| **Smoothing** | Softens transitions between screen colors. Set it to zero for immediate changes. |
| **Spatial mode** | Maps different screen regions to corresponding parts of the keyboard. |
| **Average mode** | Gives the keyboard one color based on the screen's average color. |

The three slow refresh settings sample every **8, 4, or 2 seconds**, respectively. The app still sends lighting keepalives between samples. Higher rates depend on screen-capture performance; selecting 30 FPS does not guarantee 30 updates per second.

### Per-key exceptions

Click any key in the keyboard diagram and choose:

- **Follow screen:** use the current screen-lighting mode.
- **Fixed color:** choose a color with the color wheel and value slider.
- **OFF:** keep the key dark.

Fixed colors follow the global brightness setting. Each key's choice is saved independently.

### Press-to-light

Enable **Light pressed keys at full brightness**, then choose a press color. Pressed keys temporarily use that color without the global brightness reduction, overriding even fixed-color and OFF exceptions. Their underlying lighting returns after release; short detected taps remain visible for at least 80 ms.

This effect preserves your other settings. Turn it off to return to normal screen lighting and exceptions.

The effect uses Windows key state, so another connected keyboard can also trigger it. The **Fn key itself** is not detected by this method, although Fn shortcuts can still work normally. Fn can still have a fixed color, follow the screen, or be switched off.

### Start automatically

Enable **Start at sign-in** in the tray menu, or check it in Settings and click Save. Disable it the same way. Automatic startup is off by default.

Keep the project folder and its `.venv` in place while startup is enabled. Quitting the app stops the current session without disabling startup.

### ChatGPT notification blinkers

Open **Settings > Notifications** and enable **Enable notification blinkers**. Each supported application has its own enable switch, key selector, and color picker. Currently ChatGPT is the only supported app; its default is **F8, red**. The master switch is off by default, including when upgrading an existing settings file.

New ChatGPT Windows notifications start a blink that continues until a ChatGPT application window becomes foreground, for example by clicking it or using Alt+Tab. Dismissing a notification does not stop blinking. Notifications received while ChatGPT is foreground do not start an alert. Foreground acknowledgement applies to the whole installed ChatGPT application, including its Codex surfaces, rather than one conversation.

The app checks notifications every **10 seconds** and foreground every **1 second**. Very brief foreground visits can be missed, as can notifications that are created and removed between notification checks. Only notifications actually delivered to Windows are detected; this does not guarantee an alert for every response.

The selected key alternates every half second between the selected notification color and its normal lighting. Notification color uses its selected intensity, independently of global brightness, and takes precedence over fixed colors, OFF exceptions, and press-to-light during the colored phase. Changing the key or color previews immediately. Disabling the master switch or app clears its pending alert; enabling it again and restarting do not replay old notifications.

If the tab reports **Access required**, click **Allow access / Retry**. Permission requests only happen through this button. Windows grants access to notifications generally; this app filters supported application identities and uses only notification IDs and creation times, without reading or logging message text. Access can be revoked in Windows privacy settings. Missing bindings or unavailable access disable notification effects while ordinary lighting continues. Packaging may be required on Windows installations that do not grant listener access to ordinary Python applications; that setup is not included or verified here.

Install updated dependencies with `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and restart the tray app after updating. The existing wired USB requirement also applies to blinkers. Save/Cancel controls configuration; Cancel cannot resurrect an alert already acknowledged or cleared during a disabled preview.

## Advanced use

For console output and troubleshooting, run `Start RGB.cmd` or:

```powershell
.\.venv\Scripts\python.exe .\kemove_rgb.py --help
```

Command-line options override saved lighting values for that session. For example:

```powershell
.\.venv\Scripts\python.exe .\kemove_rgb.py --brightness 0.6 --fps 15 --smoothing 0.15
```

Screen capture uses **MSS** at your selected refresh rate, without the Windows Graphics Capture yellow border. Raw screen pixels are reduced to the keyboard sampling grid before RGB conversion, avoiding a full-resolution color conversion. Pillow remains required for this reduction and the tray icon.

The app releases capture resources on Quit. If the desktop cannot be captured, it retains the last screen colors and retries after two seconds while key effects and USB keepalives continue. Startup uses a dark base until a frame is available. Capture availability changes are recorded in `kemove-rgb.log`.

To capture another monitor or a region, pass its desktop pixel coordinates as left, top, right, bottom:

```powershell
.\.venv\Scripts\pythonw.exe .\kemove_tray.py --region 1920 0 3840 1080
```

Those coordinates are an example; use your actual display arrangement. Negative coordinates are supported.

For a portable or custom OpenRGB installation, add:

```powershell
--hid-dll 'C:\path\to\OpenRGB\hidapi-hotplug.dll'
```

Custom region and DLL arguments are not stored by the Settings window. Quit any existing instance before launching with different arguments.

## Troubleshooting

- **No tray icon:** check the hidden-icons arrow. Run the console version to see startup errors.
- **Keyboard unavailable:** check wired mode and the USB cable, and close competing lighting software. The app retries automatically.
- **Unsupported keyboard revision:** the device does not match the tested identity. Other revisions need separate verification.
- **High CPU usage or slow updates:** lower the refresh rate or capture a smaller region.
- **Missing colors in video or games:** protected content can capture black. HDR accuracy and restricted desktops are not verified.

Settings are stored in `settings.json`. Status and errors are recorded in `kemove-rgb.log`. Screen images are processed in memory only; the app does not save screenshots, record typed text, or send screen content over the network. It does not modify keyboard firmware or saved hardware profiles.

## Development and background

Run the regression tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

See [VALIDATION.md](VALIDATION.md) for current verification results and remaining manual checks.

For CPU/wall-time microbenchmarks without keyboard writes, run `.\.venv\Scripts\python.exe bench_rgb.py`. Add `--capture` to measure native screen capture in memory; images are not saved. Capture measurements report the backend used. Component timings are not a measurement of the whole tray app's CPU usage.
