# -*- coding: utf-8 -*-
"""
WinSCP session launcher.

This plugin launches your WinSCP sites and workspaces from Flow Launcher.
Written the 26/09/2022 by Raul Losantos.
"""

import os
import subprocess
from urllib.parse import unquote

from flowlauncher import FlowLauncher, FlowLauncherAPI

try:
    import winreg
except ImportError:  # Allows importing the module outside Windows (tests)
    winreg = None


ICON = "images/WinSCP.ico"
REGISTRY_SESSIONS = r"Software\Martin Prikryl\WinSCP 2\Sessions"
DEFAULT_WINSCP_FOLDERS = [
    r"%ProgramFiles(x86)%\WinSCP",
    r"%ProgramFiles%\WinSCP",
    r"%LOCALAPPDATA%\Programs\WinSCP",
]
INI_SECTION_PREFIX = "sessions\\"
DEFAULT_SESSION = "Default Settings"
LAUNCH_ARGUMENTS = ["/Desktop", "/UploadIfAny"]
SESSION_VALUES = ("HostName", "UserName", "PortNumber", "FSProtocol", "Ftps", "IsWorkspace")

# FSProtocol values used by WinSCP
PROTOCOLS = {0: "SCP", 1: "SFTP", 2: "SFTP", 5: "FTP", 6: "WebDAV", 7: "S3"}


class WinSCPError(Exception):
    """Error with a user friendly title and subtitle."""

    def __init__(self, title, subtitle=""):
        super().__init__(f"{title}: {subtitle}")
        self.title = title
        self.subtitle = subtitle


def expand(path):
    """Expand environment variables and strip quotes/whitespace."""
    return os.path.expandvars(str(path or "").strip().strip('"'))


def unescape(text):
    """Decode WinSCP escaped names and values (e.g. 'My%20site')."""
    return unquote(str(text), encoding="utf-8", errors="replace")


def to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def read_ini_lines(path):
    """Read an ini file trying the encodings WinSCP may use."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=encoding) as ini_file:
                return ini_file.read().splitlines()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="latin-1") as ini_file:
        return ini_file.read().splitlines()


def parse_ini(lines):
    """Parse ini lines as an ordered list of (section, {key: value})."""
    sections = []
    current = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = (line[1:-1].strip(), {})
            sections.append(current)
        elif current is not None:
            key, _, value = line.partition("=")
            current[1][key.strip()] = value.strip()
    return sections


def describe(values):
    """Return (protocol, 'user@host:port') from the stored session values."""
    protocol = PROTOCOLS.get(to_int(values.get("FSProtocol"), 2), "")
    if to_int(values.get("Ftps"), 0) and protocol in ("FTP", "WebDAV"):
        protocol = "FTPS" if protocol == "FTP" else "WebDAVS"

    host = unescape(values.get("HostName", "")).strip()
    if not host:
        return protocol, ""
    user = unescape(values.get("UserName", "")).strip()
    port = to_int(values.get("PortNumber"))
    target = f"{user}@{host}" if user else host
    return protocol, f"{target}:{port}" if port else target


def build_sessions(stored, source):
    """Build sites and workspaces from {escaped key: values}.

    Keys use '/' as folder separator. Workspaces are stored as several
    sessions 'Workspace/0000' with IsWorkspace=1 and are shown only once.
    """
    sessions = []
    workspaces = set()
    for key, values in stored.items():
        name_path = unescape(key)
        if name_path == DEFAULT_SESSION:
            continue
        folder, _, name = name_path.rpartition("/")
        if to_int(values.get("IsWorkspace"), 0):
            if folder and folder.lower() not in workspaces:
                workspaces.add(folder.lower())
                parent, _, ws_name = folder.rpartition("/")
                sessions.append({
                    "name": ws_name,
                    "folder": parent,
                    "path": folder,
                    "launch": key.rpartition("/")[0].replace("/", "%2F"),
                    "protocol": "",
                    "target": "",
                    "kind": "workspace",
                    "source": source,
                })
            continue
        protocol, target = describe(values)
        sessions.append({
            "name": name,
            "folder": folder,
            "path": name_path,
            # Same format the plugin always used: escaped name with '/' as %2F
            "launch": key.replace("/", "%2F"),
            "protocol": protocol,
            "target": target,
            "kind": "site",
            "source": source,
        })
    return sessions


def sessions_from_ini(lines):
    """Return {escaped key: values} from the [Sessions\\...] sections of WinSCP.ini."""
    stored = {}
    for section, values in parse_ini(lines):
        if section.lower().startswith(INI_SECTION_PREFIX):
            stored[section[len(INI_SECTION_PREFIX):]] = values
    return stored


def sessions_from_registry():
    """Return {escaped key: values} from the registry (installed WinSCP)."""
    stored = {}
    if winreg is None:
        return stored
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_SESSIONS)
    except OSError:
        return stored
    with root:
        index = 0
        while True:
            try:
                key_name = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            values = {}
            try:
                with winreg.OpenKey(root, key_name) as session_key:
                    for value_name in SESSION_VALUES:
                        try:
                            values[value_name] = winreg.QueryValueEx(session_key, value_name)[0]
                        except OSError:
                            pass
            except OSError:
                continue
            stored[key_name] = values
    return stored


def deduplicate(sessions):
    unique, seen = [], set()
    for session in sessions:
        key = (session["kind"], session["path"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(session)
    return unique


def score(session, terms):
    """Return a score (or None if it does not match all the terms)."""
    haystack = " ".join([session["path"], session["target"], session["protocol"], session["kind"]]).lower()
    if not all(term in haystack for term in terms):
        return None
    if not terms:
        return 50
    name = session["name"].lower()
    text = " ".join(terms)
    if name == text:
        return 100
    if name.startswith(text):
        return 80
    if text in name:
        return 60
    return 40


def search(sessions, query):
    terms = (query or "").lower().split()
    matches = [(score(s, terms), s) for s in sessions]
    matches = [m for m in matches if m[0] is not None]
    matches.sort(key=lambda m: (-m[0], m[1]["path"].lower()))
    return matches


class WinSCPLauncher(FlowLauncher):
    """WinSCP session launcher."""

    # ----------------------------------------------------------------- settings
    @property
    def settings(self):
        if hasattr(self, "rpc_request") and isinstance(self.rpc_request, dict):
            return self.rpc_request.get("settings") or {}
        return {}

    def get_setting(self, name):
        value = self.settings.get(name, "")
        return value.strip() if isinstance(value, str) else ""

    # -------------------------------------------------------------- discovery
    def find_executable(self):
        """Return WinSCP.exe (installed or portable)."""
        configured = expand(self.get_setting("winscp_path"))
        if configured.lower().endswith(".exe") and os.path.isfile(configured):
            return configured

        folders = [configured] if configured else []
        folders += [expand(f) for f in DEFAULT_WINSCP_FOLDERS]
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            preferred = os.path.join(folder, "WinSCP.exe")
            if os.path.isfile(preferred):
                return preferred
            for name in sorted(os.listdir(folder)):
                if name.lower().startswith("winscp") and name.lower().endswith(".exe"):
                    return os.path.join(folder, name)

        raise WinSCPError(
            "WinSCP executable not found",
            f"Check the WinSCP path in the plugin settings ({configured or 'empty'})",
        )

    def find_ini_files(self, exe_path):
        """Return the existing WinSCP.ini files (portable or custom storage)."""
        candidates = [
            expand(self.get_setting("ini_path")),
            os.path.join(os.path.dirname(exe_path), "WinSCP.ini"),
            expand(r"%APPDATA%\WinSCP.ini"),
        ]
        files, seen = [], set()
        for candidate in candidates:
            if candidate and os.path.isfile(candidate) and candidate.lower() not in seen:
                seen.add(candidate.lower())
                files.append(candidate)
        return files

    def load_sessions(self, exe_path):
        sessions = []
        for ini_file in self.find_ini_files(exe_path):
            try:
                sessions += build_sessions(sessions_from_ini(read_ini_lines(ini_file)), "ini")
            except OSError:
                continue
        sessions += build_sessions(sessions_from_registry(), "registry")
        return deduplicate(sessions)

    # ------------------------------------------------------------------ query
    @staticmethod
    def message(title, subtitle=""):
        return {"Title": title, "SubTitle": subtitle, "IcoPath": ICON}

    @staticmethod
    def subtitle(session):
        details = [session["folder"] or "Root"]
        if session["kind"] == "workspace":
            details.append("Workspace")
        else:
            details += [session["protocol"], session["target"]]
        return " · ".join(d for d in details if d)

    def query(self, query):
        try:
            exe_path = self.find_executable()
            sessions = self.load_sessions(exe_path)
        except WinSCPError as e:
            return [self.message(e.title, e.subtitle)]
        except Exception as e:
            return [self.message("Error reading WinSCP sessions", str(e))]

        if not sessions:
            return [self.message("No sessions found", "Save some sites in WinSCP first")]

        matches = search(sessions, query)
        if not matches:
            return [self.message(f"No sessions match '{query.strip()}'",
                                 f"{len(sessions)} sessions available")]

        return [{
            "Title": session["name"],
            "SubTitle": self.subtitle(session),
            "IcoPath": ICON,
            "Score": value,
            "ContextData": [exe_path, session["launch"], session["path"]],
            "JsonRPCAction": {"method": "open_session", "parameters": [exe_path, session["launch"]]},
        } for value, session in matches]

    def context_menu(self, data):
        if not isinstance(data, list) or len(data) != 3:
            return []
        exe_path, launch, path = data
        return [
            {
                "Title": "Open session",
                "SubTitle": path,
                "IcoPath": ICON,
                "JsonRPCAction": {"method": "open_session", "parameters": [exe_path, launch]},
            },
            {
                "Title": "Copy session name",
                "SubTitle": path,
                "IcoPath": ICON,
                "JsonRPCAction": {"method": "copy", "parameters": [path]},
            },
            {
                "Title": "Open WinSCP",
                "SubTitle": exe_path,
                "IcoPath": ICON,
                "JsonRPCAction": {"method": "open_winscp", "parameters": [exe_path]},
            },
        ]

    # ---------------------------------------------------------------- actions
    def open_session(self, exe_path, launch):
        """Launch a WinSCP site/workspace (arguments as a list: no shell parsing)."""
        try:
            subprocess.Popen([exe_path, launch] + LAUNCH_ARGUMENTS, cwd=os.path.dirname(exe_path))
        except Exception as e:
            FlowLauncherAPI.show_msg("Could not open session", str(e))

    def open_winscp(self, exe_path):
        try:
            subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        except Exception as e:
            FlowLauncherAPI.show_msg("Could not open WinSCP", str(e))

    def copy(self, text):
        """Copy text to the clipboard using UTF-16 for non-ASCII names."""
        try:
            subprocess.run(["clip"], input=text.strip().encode("utf-16le"), check=True)
            FlowLauncherAPI.show_msg("Copied to clipboard", text)
        except Exception as e:
            FlowLauncherAPI.show_msg("Clipboard Error", str(e))


if __name__ == "__main__":
    WinSCPLauncher()
