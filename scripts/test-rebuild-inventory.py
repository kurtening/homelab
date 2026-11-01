#!/usr/bin/env python3
"""Synthetic redaction checks for the protected read-only inventory helper."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('rebuild_inventory', str(ROOT / 'scripts/homelab-rebuild-inventory'))
spec = importlib.util.spec_from_loader(loader.name, loader)
inventory = importlib.util.module_from_spec(spec)
loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_private_settings_are_presence_only(self):
        result = inventory.safe_settings({'node-ip': 'private-address-marker',
            'token': 'private-token-marker', 'datastore-endpoint': 'private-endpoint-marker',
            'tls-san': ['private-name-marker']})
        self.assertEqual(result, {'private_network_settings_present': True})

    def test_unrecognized_interface_backend_and_component_are_not_emitted(self):
        result = inventory.safe_settings({'flannel-iface': 'private-interface-marker',
            'flannel-backend': 'private-backend-marker', 'disable': ['private-component-marker', 'servicelb']})
        self.assertNotIn('private-', str(result))
        self.assertIn('servicelb', result['disable'])

    def test_known_flags_remain_useful(self):
        result = inventory.safe_settings({'flannel-iface': 'tailscale0', 'flannel-backend': 'vxlan',
                                         'secrets-encryption': True, 'disable': 'traefik,servicelb'})
        self.assertEqual(result['flannel-iface'], 'tailscale0')
        self.assertEqual(result['disable'], ['servicelb', 'traefik'])
        self.assertTrue(result['secrets-encryption'])

    def test_no_token_content_read_or_raw_configuration_dump(self):
        source = (ROOT / 'scripts/homelab-rebuild-inventory').read_text()
        self.assertIn("(data_dir / 'server/token').is_file()", source)
        self.assertNotIn("server/token').read", source)
        self.assertNotIn('print(configuration', source)
        self.assertNotIn('print(environment', source)
        self.assertNotIn('systemctl start', source)


if __name__ == '__main__':
    unittest.main()
