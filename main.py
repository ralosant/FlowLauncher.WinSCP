# -*- coding: utf-8 -*-
"""
WinSCP session launcher.

This plugin launches your WinSCP sites and workspaces from Flow Launcher.
"""

import os
import sys

# add plugin to local PATH
parent_folder_path = os.path.abspath(os.path.dirname(__file__))
sys.path.append(parent_folder_path)
sys.path.append(os.path.join(parent_folder_path, 'lib'))
sys.path.append(os.path.join(parent_folder_path, 'plugin'))

from plugin.WinSCPLaunch import WinSCPLauncher

if __name__ == "__main__":
    WinSCPLauncher()
