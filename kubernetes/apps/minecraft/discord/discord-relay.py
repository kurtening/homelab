#!/usr/bin/env python3
"""Loopback-only bridge from Minecraft player events to a Discord webhook."""

import http.server
import json
import os
import re
import socketserver
import threading
import urllib.error
import urllib.parse
import urllib.request

EVENT = re.compile(
    r"(?:🟢  [A-Za-z0-9_]{1,16} joined! \(\d+ online\)\nPlayers online: [A-Za-z0-9_, ]+|"
    r"🔴  [A-Za-z0-9_]{1,16} left\.\. \(\d+ online\))\Z"
)
WEBHOOK = re.compile(r"/api/webhooks/[0-9]+/[A-Za-z0-9_-]+\Z")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_url(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        return (parsed.scheme == "https" and parsed.netloc == "discord.com"
                and WEBHOOK.fullmatch(parsed.path) is not None
                and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def send(url, content):
    payload = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
            return 200 <= response.status < 300
    except (OSError, ValueError, urllib.error.URLError):
        return False


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            if self.path != "/events" or self.headers.get("Transfer-Encoding"):
                raise ValueError()
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 2048:
                raise ValueError()
            self.connection.settimeout(2)
            data = json.loads(self.rfile.read(length))
            content = data.get("content") if isinstance(data, dict) else None
            if not isinstance(content, str) or not EVENT.fullmatch(content):
                raise ValueError()
        except (ValueError, OSError, UnicodeError):
            self.send_response(400)
            self.end_headers()
            return
        ok = send(self.server.webhook, content)
        if not ok:
            print("Discord delivery failed", flush=True)
        self.send_response(204 if ok else 502)
        self.end_headers()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args):
        super().__init__(*args)
        self.slots = threading.BoundedSemaphore(8)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    with open(os.environ.get("WEBHOOK_FILE", "/run/secrets/discord/webhook"), encoding="utf-8") as f:
        url = f.read(2048).strip()
    if not valid_url(url):
        raise SystemExit("Invalid Discord webhook configuration")
    server = Server(("127.0.0.1", 8765), Handler)
    server.webhook = url
    server.serve_forever()


if __name__ == "__main__":
    main()
