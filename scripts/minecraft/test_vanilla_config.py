import pathlib
import runpy
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

    def test_refresh_uses_new_public_seed(self):
        config = (ROOT / 'kubernetes/apps/minecraft/configmap.yaml').read_text()
        self.assertIn('VANILLA_REFRESH_STATUS: "READY"', config)
        self.assertIn('LEVEL: forever-world', config)
        self.assertIn('SEED: "-4995054936707021313"', config)
        deployment = (ROOT / 'kubernetes/apps/minecraft/server.yaml').read_text()
        self.assertNotIn('name: minecraft-bootstrap', deployment)
        self.assertIn('MODRINTH_DOWNLOAD_DEPENDENCIES: none', config)
        for pin in ('oT1wWKmM', 'jUe0ucoE', 'NopA8uYe', 'Nq5UZXxA', 'e3hsPc1o'):
            self.assertIn(pin, config)

    def test_smoke_mod_pins_match_gitops(self):
        config = (ROOT / 'kubernetes/apps/minecraft/configmap.yaml').read_text()
        block = config.split('  MODRINTH_PROJECTS: |-\n', 1)[1].split('\n  MODRINTH_DOWNLOAD_DEPENDENCIES:', 1)[0]
        expected = {line.strip() for line in block.splitlines() if line.strip()}
        smoke = runpy.run_path(str(ROOT / 'scripts/minecraft/smoke-vanilla.py'))
        self.assertEqual(set(smoke['PINS'].split(',')), expected)


if __name__ == '__main__':
    unittest.main()
