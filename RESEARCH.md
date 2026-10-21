# KEMOVE K87-1980: live investigation results

Date: 21 October 2026

## Conclusion

**A concrete software path exists, and the host-to-keyboard transport has been tested successfully.** This K87 speaks the same live-lighting command that an existing OpenRGB controller uses. Its exact key layout is already represented in that controller. The installed OpenRGB release omits the K87's model ID, explaining why its detector rejects this model.

**The owner confirmed both the red/green/blue sequence with return to normal lighting and the subsequent screen-reactive effect with correct spatial placement.** Live screen-reactive RGB is now demonstrated on this physical K87. The observed screen test sent 596 frames in 60.019 seconds, achieving 9.93 frames/s. The finished standalone application is now available in this project; see README.md. Optional OpenRGB integration remains uncompiled because the build requires missing Windows SDK headers.

## Verified on this PC

| Item | Observed result |
|---|---|
| Installed application | OpenRGB 1.1.0, executable in `C:\Program Files\OpenRGB` |
| Installed source commit | `8e16de27858cf2be6af54a33ce003df74cb9fd3e`, from its launch log |
| USB vendor/product | `258A:010C` |
| USB manufacturer string | `BY Tech` |
| USB product string | `KEMOVE K87-1980` |
| USB release number | `0x0300`, a descriptor value, not a confirmed firmware version |
| Lighting interface | Interface 1, vendor usage page `0xFF00`, usage 1, collection 06 |
| Feature report | ID `0x06`, 519 payload bytes plus report ID, 520 bytes total |
| Model-identification reply | `06 82 01 00 01 00 06 00 03 00 00 00 00 8e` |
| Model ID used by OpenRGB | `0x8E`, response byte 13 |
| Installed release model table | Does not contain `0x8E` |
| Latest downloaded source model table | Also does not contain `0x8E` |
| Official K87 key layout | All 87 ordered key indices match OpenRGB's `aula_f87_layout` |

The normal typing interface was not used for writes. The read-only descriptor inspection and model query target the vendor control interface. The model query uses OpenRGB's existing identification command. An initial diagnostic assumed a full 520-byte response; it was corrected to handle the actual 14-byte response before the experiments continued.

## Why the lighting test was justified

The official K87 driver archive was downloaded from the link on KEMOVE's Driver Center, then extracted without running its installer or application. Its installer contains `KBAccess.dll` and `K87-1980-keyboard.xml`.

The K87 layout enables the vendor music-lighting feature. Static disassembly of the DLL establishes this chain:

- Export `SendMusicData`, RVA `0x15C0`, dispatches through virtual-function offset `0x44`.
- The wired implementation is RVA `0x5510`. It passes command `0x08` to the packet-building routine at RVA `0x5530`.
- That routine builds feature report `0x06`, with an eight-byte header and RGB payload, and submits a 520-byte feature report.
- OpenRGB's `SinowealthKeyboard10cController::SetLEDsDirect` independently uses this command and report format for live RGB.
- Its RGB wrapper sends keepalive frames because the keyboard family returns out of direct mode when the stream stops.

This is substantially stronger evidence than trying another keyboard's commands based only on a shared USB ID. The experiment also requires the exact product/manufacturer strings, descriptor shape, and complete observed model response before enabling lighting writes.

The packet used was:

`06 08 00 00 01 00 7a 01` followed by 378 RGB bytes and 134 zero padding bytes.

`0x017A` is **378 bytes**, or **126 RGB slots**. It is not a 122-key count. Only 87 mapped key positions are used in the screen experiment; unused slots are black. The solid-color diagnostic fills all 126 slots at low brightness.

No profile-save, key-remapping, reset, bootloader, or firmware-update command was sent. This is strong evidence for the intended transient lighting path, but it is not a firmware-level proof of flash behavior on this exact revision. A visual return to the previous lighting after output stops would provide an additional useful check. Disconnecting USB alone is not a complete power-cycle test because this keyboard has a battery.

## Experiment results

| Experiment | Result |
|---|---|
| Dim red, green, blue, three seconds each | 90 reports sent in 9.019 s; mean USB write 8.79 ms; maximum 9.97 ms |
| Primary-screen capture, no keyboard output | 50 frames in 5.009 s; 9.98 frames/s |
| Primary-screen capture mapped to K87 | 300 reports in 30.058 s; 9.98 frames/s |
| Screen capture + mapping + USB write | Mean 59.20 ms, maximum 73.80 ms per iteration |
| Packet and image-mapping checks | Four tests passed in the delivered demo |
| Official layout vs reused OpenRGB layout | All 87 key indices match |

Screenshots were processed in memory. No screenshots or screen pixel data were saved or uploaded. Measurements describe host-side processing, not measured optical latency. No long-duration reliability, HDR accuracy, unplug/replug, sleep/wake, or wireless test was performed.

The lighting experiments ended automatically. No background lighting service, startup entry, or scheduled task was created. The installed OpenRGB files and settings were not changed.

## Deliverables

- `demo/`: small diagnostic and screen-reactive programs, with their tests and a derived K87 key-position map.
- `openrgb-k87.patch`: a small source patch registering model `0x8E` with the existing layout and requiring the K87 product string for this ID.
- `evidence/`: local HID identity, model response, and timing logs. The HID inventory contains machine-specific device paths, so review it before publishing.
- The downloaded source and extracted vendor files remain under the project's `work/` directory for further investigation.

The patch targets downloaded OpenRGB commit `763e325f9b8afda33ed5dd9be73a0eee7be42bff`. The installed release's model table was separately checked at its exact commit. The patch has passed a whitespace check and layout-data comparison, **but has not been compiled or tested inside OpenRGB**. It is a candidate integration, not an installed fix. The standalone experiments exercise the same packet format through the HID library already shipped with OpenRGB.

## Finished application

The original bounded probes have been replaced for everyday use by kemove_rgb.py and Start RGB.cmd. See README.md for startup, settings, installation, and troubleshooting. The application adds continuous operation, reconnect recovery, smoothing, region selection, and duplicate-launch protection. See VALIDATION.md for the final checks and remaining untested cases.

## References

- [KEMOVE Driver Center](https://www.kemove.com/pages/drivers), which links the [K87 software archive](https://download.kemove.com/k87/software/k87.zip).
- [OpenRGB installed-release model table](https://github.com/CalcProgrammer1/OpenRGB/blob/8e16de27858cf2be6af54a33ce003df74cb9fd3e/Controllers/SinowealthController/SinowealthKeyboard10cController/SinowealthKeyboard10cDevices.cpp).
- [OpenRGB live-lighting implementation](https://github.com/CalcProgrammer1/OpenRGB/blob/763e325f9b8afda33ed5dd9be73a0eee7be42bff/Controllers/SinowealthController/SinowealthKeyboard10cController/SinowealthKeyboard10cController.cpp).
- [OpenRGB detector](https://github.com/CalcProgrammer1/OpenRGB/blob/763e325f9b8afda33ed5dd9be73a0eee7be42bff/Controllers/SinowealthController/SinowealthControllerDetect.cpp).
- [OpenRGB Effects plugin](https://openrgb.org/plugin_effects.html), including Ambient Light.
- [innoextract](https://constexpr.org/innoextract/), used to unpack the official software without running its installer.

Hardware facts and timings above come from this session's local measurements. The initial generic 61-key image converter was not needed once the real keyboard's protocol family was identified.

