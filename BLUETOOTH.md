# Bluetooth investigation

Date: 22 October 2026

## Confirmed on the connected K87

- Windows identifies the Bluetooth LE device as KEMOVE K87-1980 5.0.
- Bluetooth HID identity is VID:PID 3554:FA07, release 6701. This differs from the wired 258A:010C identity.
- Vendor collection uses usage page FF02, usage 2, report ID 13 hexadecimal, with 19 bytes of input/output payload (20 bytes including report ID). It has no feature reports. The wired 520-byte feature report cannot be reused directly.
- BLE discovery returned Generic Access, Device Information, Battery and HID services. No separate custom service appeared. Direct GATT characteristic discovery for HID returned AccessDenied; the vendor HID collection could still be opened through HIDAPI.
- Static analysis of the downloaded KEMOVE KBAccess.dll confirms a wireless FF02/usage2 transport, 20-byte output reports, additive checksum, and command 88 hexadecimal for SendMusicData. This analysis did not execute vendor code.
- The DLL's command 07 status query received no response within two seconds.
- Its command 05 information query returned a valid 20-byte response with model 8E, matching this K87: `13 05 01 00 0a 03 00 00 00 00 8e 01 00 00 00 00 00 00 00 b5`. The final byte matches the additive checksum.

## Bounded live-color test

Sent dim red, green, blue to key indices 0, 12 and 18 (Esc, F1, F2), at two packets per second. Tested two live-lighting format flags, 0 and 1, for six seconds each. All 24 output writes returned 20 bytes successfully.

Physical color response is awaiting the owner's confirmation. Successful writes alone do not establish functioning RGB control. Bluetooth support has not been added to the production application.

No firmware, keymap, reset, saved lighting profile, or persistent configuration commands were sent. The existing app was not modified. Inspection dependencies are isolated in the investigation workspace.

## Relevant protocol reference

The [keylux protocol investigation](https://github.com/SibteProf/keylux/blob/main/docs/PROTOCOL.md) documents similar 20-byte live-color grouping on an AULA 2.4 GHz receiver. Its observations are evidence for a related protocol, not proof that KEMOVE Bluetooth supports the same behavior. The KEMOVE DLL independently confirms the transport framing and live command.

Next: confirm the physical result. If successful, verify per-key mapping, timeout restoration and conservative throughput before integrating a Bluetooth backend. If unsuccessful, investigate the exact vendor payload construction and whether a Bluetooth-specific live-lighting mode exists, without guessing persistent configuration writes.

## Follow-up after visual feedback

The owner reported that the first compact-payload test made the lighting go dark and then return to the standard automatic effect. This was not a successful RGB test.

Further static analysis of DeviceDriver.exe located its SendMusicData call (RVA 102BF) and confirmed that it supplies 378 bytes of interleaved RGB, indexed as three bytes per LED. KBAccess.dll's wireless SendMusicData implementation (RVA 3B80) sends command 88 with format flag 0; its framing function at RVA 3CA0 splits this into 14-byte chunks.

A second test therefore sent the native payload: 126 copies of a dim RGB triple, 27 chunks per frame, two frames each of red/green/blue, with 50 ms between chunks. All 162 output reports completed successfully in about nine seconds. The exact model-information response was checked again before sending. Visual confirmation of this second test is pending.
