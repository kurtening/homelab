#!/usr/bin/env python3
"""Do not accept placeholder Minecraft credentials for production."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
secret = root / 'kubernetes/secrets/minecraft-admin/credentials.sops.yaml'
admin = root / 'kubernetes/apps/minecraft/admin.yaml'
pending = False
if secret.exists() and 'homelab.kurtening.dev/credential-status: PENDING' in secret.read_text():
    print('PENDING: Minecraft admin credentials must be provisioned privately before merge')
    pending = True
if admin.exists() and 'homelab.kurtening.dev/security-status: PENDING' in admin.read_text():
    print('PENDING: Minecraft console security review and remediation must be completed before merge')
    pending = True
if pending:
    sys.exit(1)
print('PASS: Minecraft admin credential placeholder gate')
