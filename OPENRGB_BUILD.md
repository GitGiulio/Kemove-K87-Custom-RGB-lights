# Trying the OpenRGB patch

## What uncompiled means

`openrgb-k87.patch` contains edits to C++ source files. It is not an executable, firmware file, or OpenRGB plugin, and cannot be imported into the installed OpenRGB application. Compiling translates the patched source into a separate OpenRGB.exe.

The keyboard protocol was tested successfully by the Python application, but that does not prove the complete OpenRGB integration works. That integration still needs to be built and tested.

## Current blocker and available tools

The build attempt reached the compiler and failed on:

```
fatal error C1083: Cannot open include file: 'crtdbg.h': No such file or directory
```

Visual Studio 2022 Community's C++ compiler is already present. Qt 6.8.3 for MSVC 2022 x64 was downloaded locally. The Windows SDK headers and libraries are missing; the Windows Kits/10 directory currently contains only UnionMetadata.

## Steps to get a runnable build

1. Open **Visual Studio Installer**, select **Modify** for Visual Studio 2022 Community, then **Individual components**. Install an available **Windows 11 SDK** with its C++ headers/libraries and Universal CRT. Retain the installed MSVC x64/x86 build tools. The **Desktop development with C++** workload is another way to obtain the needed components. This changes the development environment and may require administrator approval and a sizable download. [Microsoft's instructions](https://learn.microsoft.com/en-us/visualstudio/install/modify-visual-studio).
2. Rebuild the already-patched source. The prepared build command on this PC is below. The SDK error was the first failure; additional compiler or linker issues may appear once it is resolved.
3. After a successful build, deploy the matching Qt DLLs using `windeployqt` from the downloaded Qt installation. Include the OpenRGB dependency DLLs and the Qt6Core5Compat/Qt6OpenGL DLLs needed by the Effects plugin. Follow the deployment portion of `OpenRGB/scripts/build-windows.bat`, adapting its C:\Qt paths to the local Qt directory below. Do not overwrite the installed application.
4. Quit the Python tray app and stock OpenRGB. Run the new build separately with its own configuration directory (`--config <folder>`). Initially enable only the relevant Sinowealth USB detector when testing; the patch does not require testing motherboard or RAM control.
5. Check that it lists **KEMOVE K87-1980**, exposes the expected keys, and that Direct Mode displays red, green, blue, and a left/right test correctly. Check normal typing and return to built-in lighting when output stops.
6. Install an **Effects plugin matching the new build's architecture, Qt version, and plugin API**. If no compatible binary exists, build the plugin too. Its **Ambient Light** effect provides screen matching. Test mapping and an extended session before switching everyday use to OpenRGB. [Effects documentation](https://openrgb.org/plugin_effects.html).

Existing source, Qt, and build script are in the original investigation workspace:

```
C:\Users\giuli\OneDrive\Documenti\ChatGPT\KEMOVE RGB\work\OpenRGB
C:\Users\giuli\OneDrive\Documenti\ChatGPT\KEMOVE RGB\work\Qt\6.8.3\msvc2022_64
C:\Users\giuli\OneDrive\Documenti\ChatGPT\KEMOVE RGB\work\build-openrgb.cmd
```

From PowerShell, after installing the SDK:

```powershell
& 'C:\Users\giuli\OneDrive\Documenti\ChatGPT\KEMOVE RGB\work\build-openrgb.cmd'
```

The patch is already applied in that source checkout. For a fresh checkout, use commit `763e325f9b8afda33ed5dd9be73a0eee7be42bff`, then `git apply` the patch from this project. [OpenRGB's build instructions](https://github.com/CalcProgrammer1/OpenRGB/blob/master/Documentation/Compiling.md) document the Qt 6.8.3 / MSVC 2022 combination.

Installing the SDK and producing a patched executable have not been performed as part of the tray update. The Python app remains the working solution meanwhile. Both applications would send lighting commands to the same keyboard, so run only one at a time.
