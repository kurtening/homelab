#!/usr/bin/env python3
"""Protected local prerequisite check; never display decrypted values."""
import json
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
identity = os.environ.get('SOPS_AGE_KEY_FILE')
if not identity or not Path(identity).is_file():
    raise SystemExit('PENDING: set SOPS_AGE_KEY_FILE to the protected existing identity')
result = subprocess.run(['sops', 'decrypt', '--output-type', 'json', str(root / 'kubernetes/secrets/monitoring/monitoring-credentials.sops.yaml')], capture_output=True, text=True)
if result.returncode:
    raise SystemExit('FAIL: silent credential decryption failed')
try:
    value = json.loads(result.stdout)
    fields = value['stringData']
    checks = [value['metadata']['name'] == 'monitoring-credentials',
              value['metadata']['namespace'] == 'monitoring',
              'homelab.kurtening.dev/credential-status' not in value['metadata'].get('annotations', {}),
              bool(re.fullmatch(r'https://discord\.com/api/webhooks/[0-9]{17,20}/[A-Za-z0-9._-]+', fields['DISCORD_WEBHOOK_URL'])),
              len(fields['GRAFANA_ADMIN_PASSWORD']) >= 32,
              bool(re.fullmatch(r'https://grafana\.[a-z0-9.-]+\.ts\.net/', fields['GRAFANA_ROOT_URL']))]
    if not all(checks):
        raise ValueError('Prerequisite incomplete')
except (ValueError, KeyError, TypeError):
    raise SystemExit('PENDING: complete protected credential entry and remove its status annotation; no values displayed')
print('PASS: decrypted credential structure/format verified silently; delivery and vault custody require operator checks')
