#!/usr/bin/env python3
"""Do not accept placeholder Minecraft credentials for production."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
secret = root / 'kubernetes/secrets/minecraft-admin/credentials.sops.yaml'
if secret.exists() and 'homelab.kurtening.dev/credential-status: PENDING' in secret.read_text():
    print('PENDING: Minecraft admin credentials must be provisioned privately before merge')
    sys.exit(1)
print('PASS: Minecraft admin credential placeholder gate')
