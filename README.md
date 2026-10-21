# KEMOVE RGB

Screen-reactive RGB for your **KEMOVE K87-1980**, over USB on Windows.

The red/green/blue test and spatial screen-matching test were confirmed on your physical keyboard. This application turns that tested implementation into a continuous runner. It leaves the keyboard firmware and saved profiles alone.

## Start and stop

1. Connect the keyboard with a USB data cable and select **wired mode**.
2. Double-click **Start RGB Tray** (the Windows shortcut) in this folder. No console window opens.
3. Find the colorful keyboard icon beside the clock. Windows may put it under the hidden-icons arrow. Hover over it to see connection status.
4. Right-click the icon and choose **Quit**. The keyboard returns to its built-in lighting after its live-lighting timeout, as observed during your test.

Automatic startup is **off**, as requested. To enable it, right-click the tray icon and check **Start at sign-in**. Uncheck it to disable. This adds only a current-user Windows Run entry named `KEMOVE Screen RGB`, no service or administrator access. Quit stops this session but leaves your startup preference unchanged. Keep this project folder and its `.venv` in place while startup is enabled. Windows can also disable the entry in Settings > Apps > Startup; if that happens, re-enable it there.

The Python environment is already prepared in `.venv`. You do not need to run the setup commands below on this PC unless that environment is removed.

Default behavior: primary monitor, spatial mapping, 35% brightness, up to 10 updates per second, and gentle 80 ms smoothing. It runs until stopped. No administrator rights should be necessary under normal Windows HID permissions.

The original `Start RGB.cmd` remains available as a console diagnostic launcher; Ctrl+C stops that version. Tray status and errors are recorded in `kemove-rgb.log`, capped at 100 KB plus one backup. No screen images or content are logged.

The application retries every two seconds when the keyboard is unavailable or screen capture fails. On reconnect it rechecks the exact keyboard identity before sending colors. An unknown device revision is rejected instead of tried. A second copy in the same Windows session exits to avoid competing lighting streams.

OpenRGB **does not need to be running**, but must remain installed at `C:\Program Files\OpenRGB` because the application reuses its `hidapi-hotplug.dll`. Close KEMOVE's configuration application and any other program actively controlling this keyboard. Your stock OpenRGB does not recognize the K87, but a future patched version could compete with this application, so use only one controller at a time.

## Change the effect

Open a terminal in this folder. Examples:

```powershell
# Brighter lighting and smoother transitions
.\.venv\Scripts\python.exe .\kemove_rgb.py --brightness 0.6 --smoothing 0.15

# Whole keyboard uses the screen's average color
.\.venv\Scripts\python.exe .\kemove_rgb.py --mode average

# Disable smoothing, try a higher update rate
.\.venv\Scripts\python.exe .\kemove_rgb.py --smoothing 0 --fps 15

# A bounded trial, stops automatically
.\.venv\Scripts\python.exe .\kemove_rgb.py --seconds 30

# Read all options
.\.venv\Scripts\python.exe .\kemove_rgb.py --help
```

You can also pass the same arguments to the launcher:

```powershell
& '.\Start RGB.cmd' --brightness 0.5 --mode average
```

For tray settings, right-click the Start RGB Tray shortcut > Properties and add the same flags after the quoted script path in Target. The Start at sign-in entry uses the default settings. For the console launcher, add flags before `%*` in Start RGB.cmd.

`--brightness` accepts 0..1; `--fps` accepts 1..20; `--smoothing` accepts 0..2 seconds. The actual update rate depends on capture speed. The previous prototype measured about 10 FPS on this PC. There is no queue of old frames and no growing per-frame timing list.

## Secondary monitor or a screen region

By default the primary monitor is captured. For another display or a smaller region, supply its desktop pixel coordinates as left, top, right, bottom:

```powershell
# Example only: a 1920x1080 monitor immediately right of a 1920x1080 primary
.\.venv\Scripts\python.exe .\kemove_rgb.py --region 1920 0 3840 1080
```

Use coordinates matching your actual Windows display arrangement. Negative coordinates work for monitors left of or above the primary. Coordinates use physical pixels; the application requests DPI awareness. The selected rectangle is mapped across the keyboard.

## PyCharm and reproducible setup

Open this folder as a PyCharm project. Select `.venv\Scripts\python.exe` as its interpreter and run `kemove_tray.py` for the tray menu or `kemove_rgb.py` for a console. Add flags in the run configuration's Parameters field if desired. Use the console's Ctrl+C or PyCharm's Stop button to stop output.

For a fresh Windows machine, install **64-bit Python 3.12+** and OpenRGB, then run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\kemove_rgb.py
```

For a portable OpenRGB installation, pass `--hid-dll 'C:\path\to\OpenRGB\hidapi-hotplug.dll'`. Use the x64 DLL with x64 Python. This project does not redistribute that DLL.

Run the offline regression tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

They cover packet boundaries, identity rejection, screen orientation, brightness, black/average colors, smoothing, releasing the device on failure, and reopening on the next attempt. Hardware observations are separate from unit tests.

## Troubleshooting and limits

- **Paused / keyboard missing:** select wired mode, check the USB cable, and close competing lighting programs. The application retries automatically.
- **Unrecognized keyboard revision:** the connected board differs from the exact revision tested here. The program stops deliberately. Do not remove the identity check to try another keyboard.
- **Already running:** stop the first console before launching another copy.
- **Missing HID library:** keep OpenRGB installed or supply its DLL path as described above.
- **High CPU usage:** lower `--fps` to 5 or use a smaller `--region`. Capture uses Pillow's Windows screen capture, which prioritizes simplicity over maximum performance.
- **Protected video / secure desktop / HDR:** protected content may capture black; secure desktop may pause capture; HDR color accuracy is not validated. SDR desktop use is the tested case.
- Wireless/Bluetooth control and automatic monitor discovery are not included. Startup changes only when you choose Start at sign-in.

Screenshots are processed in memory only. The application saves no screenshots, sends no network requests, and logs no screen content or keystrokes. Stopping only closes the HID handle, it does not write a replacement profile or reset the keyboard.

## Files and protocol

- `kemove_tray.py`: tray menu, graceful Quit, optional sign-in startup, and bounded status log.
- `kemove_rgb.py`: capture, mapping, smoothing, retry loop, command-line settings, and single-instance lock.
- `k87.py`: restricted HID transport and exact identity checks.
- `k87-layout.json`: 87 physical key positions derived from the official K87 layout.
- `test_kemove_rgb.py`: offline regression checks.
- `openrgb-k87.patch`: optional upstream-source integration, not needed to run this application.
- `RESEARCH.md`: investigation and measured prototype results.

The supported keyboard reports VID:PID `258A:010C`, manufacturer `BY Tech`, product `KEMOVE K87-1980`, model ID `0x8E`. The control interface has report ID 6 and 520 total bytes. Lighting uses the vendor music/live-lighting command `0x08`, independently found in KEMOVE's `SendMusicData` routine and OpenRGB's Sinowealth 010C implementation. The 378-byte payload holds 126 RGB slots. The spatial effect populates the 87 mapped key slots; unused slots remain black. Repeating the current frame also supplies the required keepalive.

Only the identification query and live-lighting packets are sent. No flash, reset, keymap, or profile-save commands are implemented.

## Optional OpenRGB integration

The supplied patch adds model `0x8E`, requires the K87 product string, and reuses OpenRGB's existing AULA F87 layout because all 87 key indices match the vendor K87 layout. It targets source commit `763e325f9b8afda33ed5dd9be73a0eee7be42bff`.

The attempted build on this PC stopped on missing Windows SDK header `crtdbg.h`. The patch is therefore **not a compiled or installed OpenRGB fix**. The standalone application above is the completed usable solution. A future OpenRGB build requires the Windows C++ SDK, Visual Studio C++ tools, and Qt; after validating detection and Direct Mode, the matching Effects plugin's Ambient Light effect can replace this application.

References: [OpenRGB live controller](https://github.com/CalcProgrammer1/OpenRGB/blob/763e325f9b8afda33ed5dd9be73a0eee7be42bff/Controllers/SinowealthController/SinowealthKeyboard10cController/SinowealthKeyboard10cController.cpp), [KEMOVE driver downloads](https://www.kemove.com/pages/drivers), [OpenRGB Effects](https://openrgb.org/plugin_effects.html).

For the exact next steps to try the OpenRGB patch, see [OPENRGB_BUILD.md](OPENRGB_BUILD.md).

