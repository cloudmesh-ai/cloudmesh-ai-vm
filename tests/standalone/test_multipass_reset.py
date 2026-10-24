import os
import platform
import unittest
from unittest.mock import MagicMock, patch


# Mock the exceptions since we are running standalone
class VMProviderError(Exception):
    pass


# Minimal mock of LocalBaseManager and MultipassManager for testing
class LocalBaseManager:
    def _run_command(self, command, stream=False):
        pass

    def print(self, msg):
        print(f"LOG: {msg}")


class MultipassManager(LocalBaseManager):
    def reset(self, name=None):

        if platform.system() != "Darwin":
            self.print("Daemon reset via launchctl is only supported on macOS.")
            return False

        self.print("Resetting Multipass daemon...")
        if os.geteuid() == 0:
            cmd = ["launchctl", "kickstart", "-k", "system/com.canonical.multipassd"]
        else:
            # Try non-interactive sudo first to avoid hanging in CI/scripts
            try:
                self._run_command(
                    [
                        "sudo",
                        "-n",
                        "launchctl",
                        "kickstart",
                        "-k",
                        "system/com.canonical.multipassd",
                    ]
                )
                return True
            except Exception:
                if not os.isatty(0):
                    self.print(
                        "Error: sudo privileges are required to reset the Multipass daemon, but no TTY is available for password entry."
                    )
                    return False
                cmd = [
                    "sudo",
                    "launchctl",
                    "kickstart",
                    "-k",
                    "system/com.canonical.multipassd",
                ]

        try:
            self._run_command(cmd)
            return True
        except Exception as e:
            self.print(f"Error resetting Multipass daemon: {e}")
            return False


class TestMultipassReset(unittest.TestCase):
    def setUp(self):
        self.mgr = MultipassManager()
        self.mgr._run_command = MagicMock()

    @patch("platform.system", return_value="Linux")
    def test_reset_non_macos(self, mock_sys):
        self.assertFalse(self.mgr.reset())

    @patch("platform.system", return_value="Darwin")
    @patch("os.geteuid", return_value=0)
    def test_reset_as_root(self, mock_uid, mock_sys):
        self.assertTrue(self.mgr.reset())
        self.mgr._run_command.assert_called_once_with(
            ["launchctl", "kickstart", "-k", "system/com.canonical.multipassd"]
        )

    @patch("platform.system", return_value="Darwin")
    @patch("os.geteuid", return_value=1000)
    def test_reset_passwordless_sudo(self, mock_uid, mock_sys):
        # sudo -n succeeds
        self.mgr._run_command.return_value = True
        self.assertTrue(self.mgr.reset())
        self.mgr._run_command.assert_called_once_with(
            [
                "sudo",
                "-n",
                "launchctl",
                "kickstart",
                "-k",
                "system/com.canonical.multipassd",
            ]
        )

    @patch("platform.system", return_value="Darwin")
    @patch("os.geteuid", return_value=1000)
    @patch("os.isatty", return_value=True)
    def test_reset_interactive_sudo(self, mock_tty, mock_uid, mock_sys):
        # sudo -n fails, but TTY is available
        def run_cmd(cmd, **kwargs):
            if "-n" in cmd:
                raise RuntimeError("Password required")
            return True

        self.mgr._run_command.side_effect = run_cmd
        self.assertTrue(self.mgr.reset())
        # Should be called twice: once with -n, once without
        self.assertEqual(self.mgr._run_command.call_count, 2)
        self.mgr._run_command.assert_called_with(
            ["sudo", "launchctl", "kickstart", "-k", "system/com.canonical.multipassd"]
        )

    @patch("platform.system", return_value="Darwin")
    @patch("os.geteuid", return_value=1000)
    @patch("os.isatty", return_value=False)
    def test_reset_non_interactive_sudo_fail(self, mock_tty, mock_uid, mock_sys):
        # sudo -n fails and no TTY
        self.mgr._run_command.side_effect = Exception("Password required")
        self.assertFalse(self.mgr.reset())
        self.mgr._run_command.assert_called_once_with(
            [
                "sudo",
                "-n",
                "launchctl",
                "kickstart",
                "-k",
                "system/com.canonical.multipassd",
            ]
        )


if __name__ == "__main__":
    unittest.main()
