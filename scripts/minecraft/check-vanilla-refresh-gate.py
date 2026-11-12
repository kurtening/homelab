#!/usr/bin/env python3
"""Prevent accidental rollout of an incompletely verified Minecraft refresh."""

from pathlib import Path
import sys

config = Path(__file__).resolve().parents[2] / 'kubernetes/apps/minecraft/configmap.yaml'
if 'VANILLA_REFRESH_STATUS: "READY"' not in config.read_text():
    print('PENDING: Minecraft refresh needs recovery and rollout review')
    sys.exit(1)
print('PASS: Minecraft refresh review gate')
