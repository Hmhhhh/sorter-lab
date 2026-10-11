from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from sorter_lab.simulation import SortingLine
from sorter_lab.web import make_handler


class WebApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.line = SortingLine(seed=11)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.line))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_dashboard_and_state_endpoints(self) -> None:
        with urlopen(self.base + "/") as response:
            self.assertIn(b"Sorter Lab", response.read())
        with urlopen(self.base + "/api/state") as response:
            state = json.loads(response.read())
        self.assertEqual(state["state"], "stopped")

    def test_action_and_reset_endpoints(self) -> None:
        request = Request(self.base + "/api/action", data=b'{"action":"start"}',
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            self.assertEqual(json.loads(response.read())["state"], "stopped")
        with urlopen(self.base + "/api/tick") as response:
            self.assertEqual(json.loads(response.read())["state"], "running")
        request = Request(self.base + "/api/reset", data=b'{"seed":11}',
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            state = json.loads(response.read())
        self.assertEqual(state["state"], "stopped")
        self.assertEqual(state["time_s"], 0.0)

    def test_unknown_action_is_rejected(self) -> None:
        request = Request(self.base + "/api/action", data=b'{"action":"explode"}',
                          headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
