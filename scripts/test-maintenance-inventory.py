#!/usr/bin/env python3
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('maintenance_inventory', str(ROOT / 'scripts/maintenance-inventory'))
spec = importlib.util.spec_from_loader(loader.name, loader)
inventory = importlib.util.module_from_spec(spec)
loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_committed_inventory_is_current(self):
        self.assertEqual(inventory.render(ROOT), (ROOT / 'docs/versions.md').read_text())

    def test_monitoring_aliases_are_resolved_to_eight_digests(self):
        rows = [row for row in inventory.collect(ROOT) if row[3] == 'kubernetes/apps/monitoring/kustomization.yaml']
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row[2] == 'digest' for row in rows))
        self.assertFalse(any(row[1] == 'prometheus' for row in inventory.collect(ROOT)))

    def test_mutable_pins_are_not_claimed_immutable(self):
        rows = inventory.collect(ROOT)
        self.assertTrue(any(row[1] == 'traefik/whoami:v1.11.0' and row[2] == 'tag only' for row in rows))
        self.assertTrue(any(row[0] == 'GitHub Action' and row[2] == 'tag only' for row in rows))

    def test_secret_files_are_never_opened(self):
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            self.assertNotIn('secrets', path.relative_to(ROOT).parts)
            self.assertFalse(path.name.endswith('.sops.yaml'))
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            self.assertTrue(inventory.collect(ROOT))

    def test_inventory_includes_chart_bundle_tools_mods_and_provider(self):
        names = [row[0] for row in inventory.collect(ROOT)]
        for prefix in ['Helm chart:', 'Argo CD upstream bundle', 'Development tool:', 'Minecraft mod:', 'OpenTofu provider:']:
            self.assertTrue(any(name.startswith(prefix) for name in names), prefix)


if __name__ == '__main__':
    unittest.main()
