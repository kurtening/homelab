#!/usr/bin/env python3
"""Capture the current RCON credential and encrypt console bootstrap credentials."""

import json
import getpass
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "kubernetes/secrets/minecraft-admin/credentials.sops.yaml"
RECIPIENT = "age1jjc8lptxy8te9xp9gpfwxxrnkqex6xuhu5crwu6jktuze0gyyfkqrc63eg"


def run(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def live_password():
    result = run(["kubectl", "-n", "minecraft", "exec", "deployment/minecraft", "--", "cat", "/data/.rcon-cli.env"])
    lines = result.decode().splitlines()
    passwords = [line.partition("=")[2] for line in lines if line.startswith("password=")]
    if len(passwords) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{12,128}", passwords[0]):
        raise ValueError("Current RCON credential cannot be safely imported")
    return passwords[0]


def main():
    identity = os.environ.get("SOPS_AGE_KEY_FILE")
    if not identity or not os.path.isfile(identity):
        raise ValueError("Set SOPS_AGE_KEY_FILE to the protected age identity")
    if not DESTINATION.exists():
        raise ValueError("Expected encrypted placeholder is missing")
    old = json.loads(run(["sops", "decrypt", "--output-type", "json", str(DESTINATION)]))
    mode = sys.argv[1:]
    if mode == ["--verify"]:
        if run(["kubectl", "config", "current-context"]).decode().strip() != "homelab-desktop":
            raise ValueError("Active kube context is not homelab-desktop")
        secret = old.get("stringData", {})
        if secret.get("rcon-password") in (None, "PENDING") or secret.get("rcon-password") != live_password():
            raise ValueError("Encrypted RCON credential does not match current server")
        print("PASS: encrypted RCON credential matches current server")
        return
    if mode not in ([], ["--refresh-rcon"]):
        raise ValueError("Unsupported arguments")
    expected = {"rcon-password": "PENDING", "admin-password": "PENDING", "websocket-url": "PENDING"}
    if mode == [] and (old.get("stringData") != expected or old.get("metadata", {}).get("annotations", {}).get("homelab.kurtening.dev/credential-status") != "PENDING"):
        raise ValueError("Existing encrypted credential is not the expected placeholder")
    if run(["kubectl", "config", "current-context"]).decode().strip() != "homelab-desktop":
        raise ValueError("Active kube context is not homelab-desktop")
    password = live_password()
    if mode == ["--refresh-rcon"]:
        previous = old.get("stringData", {})
        admin_password = previous.get("admin-password", "")
        websocket_url = previous.get("websocket-url", "")
        if not 20 <= len(admin_password) <= 128 or not re.fullmatch(r"wss://minecraft-admin\.[a-z0-9-]+\.ts\.net/socket", websocket_url):
            raise ValueError("Existing console credentials are invalid")
    else:
        admin_password = getpass.getpass('Enter the independently generated console password: ')
        if len(admin_password) < 20 or len(admin_password) > 128 or getpass.getpass('Confirm console password: ') != admin_password:
            raise ValueError('Console password is invalid or confirmation did not match')
        tailnet = json.loads(run(["tailscale", "status", "--json"]))["CurrentTailnet"]["MagicDNSSuffix"].rstrip(".")
        if not re.fullmatch(r"[a-z0-9-]+\.ts\.net", tailnet):
            raise ValueError("Cannot determine tailnet DNS suffix")
        websocket_url = f"wss://minecraft-admin.{tailnet}/socket"
    source = ("apiVersion: v1\nkind: Secret\nmetadata:\n  name: minecraft-admin-credentials\n"
              "  namespace: minecraft\n  annotations:\n"
              "    argocd.argoproj.io/sync-options: Prune=false,Delete=false\n"
              "type: Opaque\nstringData:\n"
              f"  rcon-password: {json.dumps(password)}\n  admin-password: {json.dumps(admin_password)}\n  websocket-url: {json.dumps(websocket_url)}\n")
    with tempfile.TemporaryDirectory(prefix="minecraft-admin-") as temporary:
        os.chmod(temporary, 0o700)
        source_file = Path(temporary) / "secret.yaml"
        source_file.write_text(source)
        os.chmod(source_file, 0o600)
        ciphertext = run(["sops", "encrypt", "--age", RECIPIENT, "--encrypted-regex", "^(data|stringData)$", str(source_file)], cwd=temporary)
        encrypted = Path(temporary) / "encrypted.yaml"
        encrypted.write_bytes(ciphertext)
        parsed = json.loads(run(["sops", "decrypt", "--output-type", "json", str(encrypted)], cwd=temporary))
        if parsed["stringData"] != {"rcon-password": password, "admin-password": admin_password, "websocket-url": websocket_url} or live_password() != password:
            raise ValueError("Credential verification failed or Minecraft restarted during capture")
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        with DESTINATION.open("wb") as out:
            out.write(ciphertext)
    print("PASS: encrypted credentials created and checked without displaying values")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError, UnicodeError):
        raise SystemExit("Credential capture failed; check context, protected identity, and SOPS access privately") from None
