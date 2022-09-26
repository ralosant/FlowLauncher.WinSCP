# encoding=utf8
"""
WinSCP session launcher.

This plugin launches your sessions in WinSCP from Flow.Launcher
Written the 26/09/2022 by Raul Losantos
"""
import os
import sys
# add plugin to local PATH
parent_folder_path = os.path.abspath(os.path.dirname(__file__))
sys.path.append(parent_folder_path)
sys.path.append(os.path.join(parent_folder_path, 'lib'))
sys.path.append(os.path.join(parent_folder_path, 'plugin'))

from winreg import HKEY_CURRENT_USER
import winreg as reg
import subprocess
import json
from os.path import isfile
from flowlauncher import FlowLauncher

class WinSCPLauncher(FlowLauncher):
    """WinSCP session launcher."""

    def winscp_sessions(self):
        """Locate sessions in registry."""
        # Read from registry
        DEFAULT_WINSCP_INI = r'Software\Martin Prikryl\WinSCP 2\Sessions'
        with reg.OpenKey(HKEY_CURRENT_USER, DEFAULT_WINSCP_INI) as key:
            i = 0
            keys = []
            while True:
               try:
                   keys.append(reg.EnumKey(key, i))
                   i += 1
               except WindowsError: 
                   break
        return json.dumps(keys)
        # Add support for portable app 

    def find_WinSCP_path(self, WinSCP_folder_path):
        """Return the full path to the user's WinSCP executable."""
        for exe_name in os.listdir(WinSCP_folder_path):
            if exe_name.endswith('.exe') and exe_name.startswith('WinSCP'):
                attempted_WinSCP_exe = os.path.join(
                    WinSCP_folder_path, exe_name)
        if isfile(attempted_WinSCP_exe):
            return attempted_WinSCP_exe
        raise Exception("Could not find WinSCP executable in %s" %
                        WinSCP_folder_path)

    def query(self, query):
        """Autocompletion."""
        with open(os.path.join(os.path.dirname(__file__), "config.json"), "r") as content_file:
            config = json.loads(content_file.read())
        WinSCP_folder_path = os.path.expandvars(config["WinSCPPath"])
        WinSCP_path = self.find_WinSCP_path(WinSCP_folder_path)
        session_list = self.winscp_sessions()
        result = []
        for session_name in json.loads(session_list):
            if query.lower() in session_name.lower():
                result.append({"Title": session_name.replace("%20"," "), "IcoPath": "WinSCP.ico",
                               "JsonRPCAction": {"method": "open_session", "parameters": [WinSCP_path, session_name.replace("/","%2F")]}})
        return result

    def open_session(self, WinSCP_path, selected_session_name):
        """Launch WinSCP Session."""
        subprocess.Popen('"{}" "{}" /Desktop /UploadIfAny'.format(WinSCP_path, selected_session_name))


if __name__ == "__main__":
    WinSCPLauncher()
