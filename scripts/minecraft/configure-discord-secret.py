#!/usr/bin/env python3
"""Replace the encrypted placeholder with a privately entered Discord webhook."""

import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / 'kubernetes/secrets/minecraft-discord/webhook.sops.yaml'
RECIPIENT = 'age1jjc8lptxy8te9xp9gpfwxxrnkqex6xuhu5crwu6jktuze0gyyfkqrc63eg'
WEBHOOK = re.compile(r'https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+\Z')


def run(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def main():
    identity = os.environ.get('SOPS_AGE_KEY_FILE')
    if not identity or not os.path.isfile(identity):
        raise ValueError('Protected identity is not configured')
    original = json.loads(run(['sops', 'decrypt', '--output-type', 'json', str(DESTINATION)]))
    if original.get('stringData') != {'webhook': 'PENDING'} or original.get('metadata', {}).get('annotations', {}).get('homelab.kurtening.dev/credential-status') != 'PENDING':
        raise ValueError('Refusing to replace a non-placeholder credential')
    webhook = getpass.getpass('Paste the Discord webhook URL: ').strip()
    if not WEBHOOK.fullmatch(webhook) or getpass.getpass('Paste it again to confirm: ').strip() != webhook:
        raise ValueError('Webhook format or confirmation is invalid')
    source = ('apiVersion: v1\nkind: Secret\nmetadata:\n  name: minecraft-discord-webhook\n'
              '  namespace: minecraft\n  annotations:\n'
              '    argocd.argoproj.io/sync-options: Prune=false,Delete=false\n'
              'type: Opaque\nstringData:\n  webhook: ' + json.dumps(webhook) + '\n')
    with tempfile.TemporaryDirectory(prefix='minecraft-discord-') as temporary:
        os.chmod(temporary, 0o700)
        source_file = Path(temporary) / 'secret.yaml'
        source_file.write_text(source)
        os.chmod(source_file, 0o600)
        ciphertext = run(['sops', 'encrypt', '--age', RECIPIENT, '--encrypted-regex', '^(data|stringData)$', str(source_file)], cwd=temporary)
        encrypted = Path(temporary) / 'encrypted.yaml'
        encrypted.write_bytes(ciphertext)
        decoded = json.loads(run(['sops', 'decrypt', '--output-type', 'json', str(encrypted)], cwd=temporary))
        if decoded.get('stringData') != {'webhook': webhook}:
            raise ValueError('Encrypted credential comparison failed')
        DESTINATION.write_bytes(ciphertext)
    print('PASS: webhook encrypted and verified without displaying it')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError, UnicodeError):
        raise SystemExit('Webhook setup failed; check the identity, URL, and placeholder privately') from None
