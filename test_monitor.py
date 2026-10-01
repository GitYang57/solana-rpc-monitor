"""Exercise API failures and report integrity without using public RPC quota."""

import io
import json
import unittest
from unittest.mock import patch
import urllib.error

import monitor


class MonitorTests(unittest.TestCase):
    def response(self, body):
        return patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(body).encode()))

    def test_success_and_finalized_commitment(self):
        with self.response({"jsonrpc": "2.0", "id": 1, "result": 42}) as mocked:
            result = monitor.rpc_call("https://example.com", "getSlot")
            payload = json.loads(mocked.call_args.args[0].data)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"], 42)
        self.assertEqual(payload["params"], [{"commitment": "finalized"}])

    def test_rpc_error_is_not_healthy(self):
        with self.response({"jsonrpc": "2.0", "id": 1, "error": {"code": -32005, "message": "Node unhealthy"}}):
            result = monitor.rpc_call("https://example.com", "getHealth")
        self.assertFalse(result["ok"])
        self.assertIn("-32005", result["error"])

    def test_rate_limit_and_timeout(self):
        failures = [urllib.error.HTTPError("https://example.com", 429, "Too Many Requests", {}, None), TimeoutError("timeout")]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch("urllib.request.urlopen", side_effect=failure):
                result = monitor.rpc_call("https://example.com", "getHealth")
                self.assertFalse(result["ok"])
                self.assertIsNotNone(result["error"])

    def test_malformed_json(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"not json")):
            result = monitor.rpc_call("https://example.com", "getHealth")
        self.assertFalse(result["ok"])

    def test_invalid_result_and_envelope(self):
        cases = [("getSlot", True), ("getSlot", -1), ("getVersion", {}), ("getHealth", "unhealthy")]
        for method, value in cases:
            with self.subTest(method=method, value=value), self.response({"jsonrpc": "2.0", "id": 1, "result": value}):
                self.assertFalse(monitor.rpc_call("https://example.com", method)["ok"])
        with self.response({"jsonrpc": "2.0", "id": 2, "result": "ok"}):
            self.assertFalse(monitor.rpc_call("https://example.com", "getHealth")["ok"])

    def test_failed_health_does_not_become_pass_or_html(self):
        def fake_call(url, method, timeout):
            return {"method": method, "ok": False, "result": None, "error": "<script>alert(1)</script>", "elapsed_ms": 1}
        with patch("monitor.rpc_call", side_effect=fake_call):
            report = monitor.collect(["devnet"], 1)
        self.assertEqual(report["clusters"][0]["status"], "CHECK FAILED")
        page = monitor.render_html(report)
        self.assertIn("0/1 endpoints", page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
