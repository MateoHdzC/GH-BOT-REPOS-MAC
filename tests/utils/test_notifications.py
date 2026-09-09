"""Unit tests for macOS notification dispatcher."""

import unittest
from unittest.mock import MagicMock, patch

from src.utils.notifications import send_macos_notification


class TestNotifications(unittest.TestCase):
    @patch("subprocess.run")
    def test_send_macos_notification_command_structure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        success = send_macos_notification(
            message="Push realizado con éxito",
            title="GH-BOT-REPOS-MAC",
            subtitle="RepoA",
            sound=True,
        )
        self.assertTrue(success)
        mock_run.assert_called_once()

        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "/usr/bin/osascript")
        self.assertEqual(call_args[1], "-e")
        script_arg = call_args[2]
        self.assertIn("display notification", script_arg)
        self.assertIn("Push realizado con éxito", script_arg)
        self.assertIn("GH-BOT-REPOS-MAC", script_arg)
        self.assertIn("subtitle", script_arg)


if __name__ == "__main__":
    unittest.main()
