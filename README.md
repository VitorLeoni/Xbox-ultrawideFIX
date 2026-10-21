# Xbox Stretch (Ultrawide Fix)

**Xbox Stretch** is a lightweight Windows utility designed to stretch 16:9 video streams from the **Xbox App (Cloud Gaming / Remote Play)** or windowed applications to fit ultrawide displays (21:9 or higher), eliminating lateral black bars in real time.

The application functions by creating a transparent overlay on top of the target window using the native **Windows DWM Thumbnail API**. It crops the 16:9 video content and stretches it across the full width of the overlay while preserving full controller and input responsiveness.

## Features

* **Zero External Dependencies:** Built using Python's standard library and native Windows APIs (`ctypes`, `tkinter`). No third-party packages or `pip install` commands are required.
* **No Input Lag:** Leverages hardware-accelerated window duplication via the Windows Desktop Window Manager (DWM).
* **Command Pass-Through:** Prevents focus hijacking to ensure controller and keyboard inputs reach the underlying game or stream uninterrupted.
* **Global Hotkey (`Ctrl + Alt + X`):** Instantly toggle the overlay on or off during gameplay.

## Requirements

* **Operating System:** Windows 10 or Windows 11.
* **Python:** Version 3.8 or higher (standard installation).

## Usage Instructions

1. **Configure the Target Application:**
   * Open the Xbox application (or any other game/app) and start your stream or game.
   * **Important:** The target application must be running in **Windowed** mode (not Exclusive Fullscreen) for the DWM API to capture the window frame properly.

2. **Run the Utility:**
   * xboxultrawide.py
   

3. **Activate the Overlay:**
   * Select the target window from the dropdown menu (the Xbox app is detected automatically). To capture other games or applications, check the **"Show all windows"** option.
   * Click **Start** or press the **`Ctrl + Alt + X`** hotkey.
   * The overlay will stretch the central 16:9 region across the entire window area.

4. **Deactivate:**
   * Press **`Ctrl + Alt + X`** again to toggle the overlay off.

## Anti-Cheat and Security Warning

**Use with native PC games and multiplayer titles at your own risk.**

* **Streaming Apps (Xbox Cloud / Remote Play):** Safe to use. The utility interacts with the streaming client window rather than game memory or local game files.
* **Native PC Games with Kernel Anti-Cheat (e.g., *Valorant*, *Apex Legends*, *CS2*):** Running this utility against active native game executables carries a risk of detection or account penalties. Anti-cheat systems (such as Riot Vanguard, Easy Anti-Cheat, or BattlEye) closely monitor window manipulation, DWM duplication, and thread focus hooks (`AttachThreadInput`). Using this tool on competitive multiplayer games running natively on PC is strongly discouraged.

## Technical Architecture

* **`DwmRegisterThumbnail`:** Registers a live, hardware-accelerated preview thumbnail of the target window.
* **Aspect Ratio Adjustment:** Dynamically crops letterboxed $16:9$ content and maps the source coordinates to the target overlay dimensions.
* **Extended Window Styles (`WS_EX_TRANSPARENT` & `WS_EX_NOACTIVATE`):** Configures the overlay as pass-through and non-activating, allowing mouse and keyboard inputs to route directly to the window beneath.
