import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class VanillaConfigTest(unittest.TestCase):
    def test_claim_limits_and_party_integration(self):
        config = tomllib.loads((ROOT / 'kubernetes/apps/minecraft/claims/openpartiesandclaims-server.toml').read_text())['serverConfig']
        self.assertEqual(config['permissionSystem'], 'luck_perms')
        self.assertEqual(config['primaryPartySystem'], 'default')
        self.assertNotIn('claims.protectClaimedChunks', config['playerConfigurablePlayerConfigOptions'])
        claims = config['claims']
        self.assertEqual(claims['maxPlayerClaims'], 256)
        for key in ('maxPlayerClaimForceloads', 'forceloadBonusPerPartyMember', 'forceloadBonusForPartyOwner'):
            self.assertEqual(claims[key], 0)
        self.assertEqual(claims['maxPlayerClaimForceloadsPermission'], '')

    def test_refresh_stays_gated_and_seed_unchanged_until_provisioned(self):
        config = (ROOT / 'kubernetes/apps/minecraft/configmap.yaml').read_text()
        self.assertIn('VANILLA_REFRESH_STATUS: "PENDING"', config)
        self.assertIn('LEVEL: world-season-2', config)
        self.assertIn('MODRINTH_DOWNLOAD_DEPENDENCIES: none', config)
        for pin in ('oT1wWKmM', 'jUe0ucoE', 'NopA8uYe', 'Nq5UZXxA', 'e3hsPc1o'):
            self.assertIn(pin, config)


if __name__ == '__main__':
    unittest.main()
