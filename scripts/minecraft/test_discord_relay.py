import importlib.util
import io
import json
import pathlib
import sys
import threading
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

path = pathlib.Path(__file__).resolve().parents[2] / "kubernetes/apps/minecraft/discord/discord-relay.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("relay", path)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class RelayTest(unittest.TestCase):
    def test_url_restrictions(self):
        self.assertTrue(relay.valid_url("https://discord.com/api/webhooks/123/abc_DEF-42"))
        for url in ("http://discord.com/api/webhooks/123/key", "https://discord.com.evil/api/webhooks/123/key", "https://discord.com/api/webhooks/123/key?wait=true", "https://discord.com:443/api/webhooks/123/key"):
            self.assertFalse(relay.valid_url(url))

    def test_events_and_failure_redaction(self):
        server = relay.Server(("127.0.0.1", 0), relay.Handler)
        temporary = tempfile.TemporaryDirectory()
        server.webhook_file = str(pathlib.Path(temporary.name) / 'webhook')
        pathlib.Path(server.webhook_file).write_text("https://discord.com/api/webhooks/123/SYNTHETIC_SECRET")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:%d/events" % server.server_port
        try:
            with patch.object(relay, "send", return_value=True) as send:
                for text in ("🟢  Alex joined! (1 online)\nPlayers online: Alex", "🔴  Alex left.. (0 online)"):
                    request = urllib.request.Request(url, data=json.dumps({"content": text}).encode())
                    self.assertEqual(urllib.request.urlopen(request).status, 204)
                self.assertEqual(send.call_count, 2)
                request = urllib.request.Request(url, data=b'{"content":"chat message"}')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(send.call_count, 2)
            with patch.object(relay, "send", return_value=False), patch("sys.stdout", new_callable=io.StringIO) as output:
                request = urllib.request.Request(url, data=json.dumps({"content": "🔴  Alex left.. (0 online)"}).encode())
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(request)
                self.assertNotIn("SYNTHETIC_SECRET", output.getvalue())
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            temporary.cleanup()

    def test_missing_invalid_and_replaced_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / 'webhook'
            server = relay.Server(('127.0.0.1', 0), relay.Handler)
            server.webhook_file = str(path)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = 'http://127.0.0.1:%d/events' % server.server_port
            event = json.dumps({'content': '🔴  Alex left.. (0 online)'}).encode()
            try:
                with patch.object(relay, 'send', return_value=True) as send, patch('sys.stdout', new_callable=io.StringIO):
                    for value in (None, 'invalid'):
                        if value is not None:
                            path.write_text(value)
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(urllib.request.Request(url, data=event))
                        self.assertEqual(error.exception.code, 502)
                    send.assert_not_called()
                    path.write_text('https://discord.com/api/webhooks/123/synthetic')
                    self.assertEqual(urllib.request.urlopen(urllib.request.Request(url, data=event)).status, 204)
                    send.assert_called_once()
            finally:
                server.shutdown()
                thread.join()
                server.server_close()

    def test_outbound_failure_is_silent_and_no_redirects(self):
        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.URLError("SYNTHETIC_SECRET")
        with patch.object(relay.urllib.request, "build_opener", return_value=opener) as build:
            self.assertFalse(relay.send("https://discord.com/api/webhooks/123/SYNTHETIC_SECRET", "message"))
        self.assertIsInstance(build.call_args.args[0], relay.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)["allowed_mentions"], {"parse": []})


if __name__ == "__main__":
    unittest.main()
