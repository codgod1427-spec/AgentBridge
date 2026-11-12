"""Tests for AgentBridge workflow validation and safe defaults."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agentbridge import server

class AgentBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root, self.old_db, self.old_work, self.old_exec = server.ROOT, server.DB, server.WORK, server.EXECUTION
        server.ROOT = Path(self.tmp.name)
        server.DB = server.ROOT / "db.sqlite3"
        server.WORK = server.ROOT / "workspace"
        server.EXECUTION = False
        server.database().close()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        server.ROOT, server.DB, server.WORK, server.EXECUTION = self.old_root, self.old_db, self.old_work, self.old_exec
        self.tmp.cleanup()

    def post(self, data):
        request = Request(self.base + "/api/workflows", data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="POST")
        return urlopen(request)

    def test_execution_disabled_by_default(self):
        with self.assertRaises(HTTPError) as error:
            self.post({"prompt": "test", "agents": ["claude"]})
        self.assertEqual(error.exception.code, 403)

    def test_dashboard_and_config(self):
        with urlopen(self.base) as response:
            self.assertIn(b"AgentBridge", response.read())
        with urlopen(self.base + "/api/config") as response:
            self.assertFalse(json.load(response)["execution_enabled"])

    def test_invalid_agent_rejected(self):
        server.EXECUTION = True
        with self.assertRaises(HTTPError) as error:
            self.post({"prompt": "test", "agents": ["arbitrary-shell"]})
        self.assertEqual(error.exception.code, 400)

    def test_handoff_uses_real_prior_output(self):
        server.EXECUTION = True
        calls = []
        def fake_run(agent, prompt):
            calls.append((agent, prompt))
            return "completed", "FIRST RESULT" if agent == "claude" else "SECOND RESULT"
        with patch.object(server, "agent_run", side_effect=fake_run):
            with self.post({"prompt": "Build a sample", "agents": ["claude", "codex"]}) as response:
                wid = json.load(response)["id"]
            import time
            for _ in range(100):
                with server.database() as db:
                    status = db.execute("SELECT status FROM workflows WHERE id=?", (wid,)).fetchone()["status"]
                if status == "completed": break
                time.sleep(.02)
            self.assertEqual(status, "completed")
            self.assertEqual([x[0] for x in calls], ["claude", "codex"])
            self.assertIn("FIRST RESULT", calls[1][1])

if __name__ == "__main__":
    unittest.main()
