#!/usr/bin/env python3
"""Prevent activation with a placeholder Discord webhook."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
secret = root / 'kubernetes/secrets/minecraft-discord/webhook.sops.yaml'
if secret.exists() and 'homelab.kurtening.dev/credential-status: PENDING' in secret.read_text():
    print('PENDING: Minecraft Discord webhook must be provisioned privately before merge')
    sys.exit(1)
print('PASS: Minecraft Discord credential placeholder gate')
