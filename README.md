# WinSCP Launcher

This plugin lets you launch [WinSCP](https://winscp.net/) sites and workspaces from [Flow Launcher](https://www.flowlauncher.com/).

## How to use it

1. Install this plugin via `pm install WinSCP Launcher`
2. Usage examples:
  - `winscp`: Lists all your saved sites and workspaces.
  - `winscp <text>`: Searches by name, folder, host, user or protocol.
    - Example: `winscp web01`
  - `winscp <word> <word>`: Every word must match (in any order).
    - Example: `winscp prod web` finds `Production/web01`
    - Example: `winscp ftps` lists your FTPS sites
    - Example: `winscp workspace` lists your workspaces

Select a result or press Enter to open it in WinSCP.

Press `Shift+Enter` (context menu) on a result to:
  - Open the session
  - Copy the session name to the clipboard
  - Open WinSCP without a session

Sites are read from the registry (installed WinSCP) and from `WinSCP.ini` (portable WinSCP or INI storage). Folders and workspaces are supported.

## Settings

- `winscp_path`: Folder or `.exe` of WinSCP, installed or portable (default: `C:\Program Files (x86)\WinSCP\`). If it is not valid, the default install folders are tried.
- `ini_path` (optional): Path to a `WinSCP.ini` stored elsewhere. `WinSCP.ini` next to `WinSCP.exe` and in `%APPDATA%` is detected automatically.

Environment variables such as `%USERPROFILE%` are allowed in both settings.

> Upgrading from 1.x: `config.json` is no longer used. Set the WinSCP path in the plugin settings if it is not in the default folder.

## Tests

```cmd
python -m unittest discover -s tests
```

Based on [HelloWorldPython](https://github.com/Flow-Launcher/Flow.Launcher.Plugin.HelloWorldPython) and [Wox-Plugin-Kitty](https://github.com/Wox-launcher/Wox.Plugin.Kitty).
