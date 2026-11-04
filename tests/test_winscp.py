"""Tests for the WinSCP Launcher parser and search (run: python -m unittest)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from WinSCPLaunch import (WinSCPLauncher, build_sessions, describe, search,  # noqa: E402
                          sessions_from_ini)

INI = r"""
[Configuration\Interface]
RandomSeedFile=%25APPDATA%25%5Cwinscp.rnd

[Sessions\Default%20Settings]
HostName=

[Sessions\My%20server]
HostName=10.0.0.5
UserName=root
PortNumber=2222

[Sessions\Production/web01]
HostName=web01.prod
UserName=deploy
FSProtocol=0

[Sessions\Production/Clientes/ftp%20cli%C3%B1on]
HostName=ftp.example.com
UserName=user
FSProtocol=5
Ftps=3

[Sessions\Backup%20WS/0000]
HostName=a.example
IsWorkspace=1

[Sessions\Backup%20WS/0001]
HostName=b.example
IsWorkspace=1
""".splitlines()


def sessions():
    return build_sessions(sessions_from_ini(INI), "ini")


class WinSCPTests(unittest.TestCase):
    def test_reads_sites_and_skips_default(self):
        names = [s["name"] for s in sessions()]
        self.assertEqual(names, ["My server", "web01", "ftp cliñon", "Backup WS"])

    def test_folders_and_launch_argument(self):
        web = sessions()[1]
        self.assertEqual(web["folder"], "Production")
        self.assertEqual(web["launch"], "Production%2Fweb01")
        self.assertEqual(sessions()[0]["launch"], "My%20server")

    def test_protocol_and_target(self):
        s = sessions()
        self.assertEqual((s[0]["protocol"], s[0]["target"]), ("SFTP", "root@10.0.0.5:2222"))
        self.assertEqual((s[1]["protocol"], s[1]["target"]), ("SCP", "deploy@web01.prod"))
        self.assertEqual((s[2]["protocol"], s[2]["folder"]), ("FTPS", "Production/Clientes"))
        self.assertEqual(describe({})[1], "")

    def test_workspace_listed_once(self):
        ws = [s for s in sessions() if s["kind"] == "workspace"]
        self.assertEqual(len(ws), 1)
        self.assertEqual((ws[0]["name"], ws[0]["launch"]), ("Backup WS", "Backup%20WS"))

    def test_search(self):
        self.assertEqual([s["name"] for _, s in search(sessions(), "prod web")], ["web01"])
        self.assertEqual([s["name"] for _, s in search(sessions(), "ftps")], ["ftp cliñon"])
        self.assertEqual([s["name"] for _, s in search(sessions(), "root@10")], ["My server"])
        self.assertEqual(search(sessions(), "workspace")[0][1]["name"], "Backup WS")
        self.assertEqual(len(search(sessions(), "")), 4)

    def test_plugin_query_with_portable_install(self):
        folder = tempfile.mkdtemp()
        open(os.path.join(folder, "WinSCP.exe"), "w").close()
        with open(os.path.join(folder, "WinSCP.ini"), "w", encoding="utf-8") as f:
            f.write("\n".join(INI))
        plugin = WinSCPLauncher.__new__(WinSCPLauncher)
        plugin.rpc_request = {"settings": {"winscp_path": folder}}

        results = plugin.query("web")
        self.assertEqual(results[0]["Title"], "web01")
        self.assertEqual(results[0]["SubTitle"], "Production · SCP · deploy@web01.prod")
        self.assertEqual(results[0]["JsonRPCAction"]["parameters"][1], "Production%2Fweb01")
        self.assertEqual(len(plugin.context_menu(results[0]["ContextData"])), 3)

        plugin.rpc_request = {"settings": {"winscp_path": "/nope"}}
        self.assertEqual(plugin.query("x")[0]["Title"], "WinSCP executable not found")


if __name__ == "__main__":
    unittest.main()
