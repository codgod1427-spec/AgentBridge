"""Integration tests that execute fake Claude/Codex binaries without API access."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentbridge import server


class LocalAdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_work = server.WORK
        self.old_execution = server.EXECUTION
        server.WORK = self.root / "workspace"
        server.EXECUTION = True

    def tearDown(self):
        server.WORK = self.old_work
        server.EXECUTION = self.old_execution
        self.temp.cleanup()

    def make_fake_cli(self, name, output, exit_code=0):
        executable = self.root / name
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print(" + repr(output) + ")\n"
            "sys.exit(" + str(exit_code) + ")\n",
            encoding="utf-8",
        )
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    def test_claude_cli_subprocess_runs(self):
        self.make_fake_cli("claude", "CLAUDE_OK")
        with patch.dict(os.environ, {"PATH": str(self.root) + os.pathsep + os.environ["PATH"]}):
            status, output = server.agent_run("claude", "Write a safe summary")
        self.assertEqual(status, "completed")
        self.assertIn("CLAUDE_OK", output)

    def test_codex_cli_subprocess_runs(self):
        self.make_fake_cli("codex", "CODEX_OK")
        with patch.dict(os.environ, {"PATH": str(self.root) + os.pathsep + os.environ["PATH"]}):
            status, output = server.agent_run("codex", "Review a safe summary")
        self.assertEqual(status, "completed")
        self.assertIn("CODEX_OK", output)

    def test_failed_cli_is_reported(self):
        self.make_fake_cli("claude", "SIMULATED_FAILURE", 2)
        with patch.dict(os.environ, {"PATH": str(self.root) + os.pathsep + os.environ["PATH"]}):
            status, output = server.agent_run("claude", "Task")
        self.assertEqual(status, "failed")
        self.assertIn("SIMULATED_FAILURE", output)

    def test_uninstalled_cli_is_reported(self):
        with patch.dict(os.environ, {"PATH": str(self.root)}):
            status, output = server.agent_run("codex", "Task")
        self.assertEqual(status, "failed")
        self.assertIn("not found", output)


if __name__ == "__main__":
    unittest.main()
