import pathlib
import json
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

class MinecraftUpgradeTest(unittest.TestCase):
    def test_version_and_disabled_mods(self):
        config = (ROOT / 'kubernetes/apps/minecraft/configmap.yaml').read_text()
        server = (ROOT / 'kubernetes/apps/minecraft/server.yaml').read_text()
        self.assertIn('VERSION: "26.3"', config)
        self.assertIn('LEVEL: forever-world', config)
        self.assertIn('MODS: ""', config)
        self.assertNotIn('open-parties-and-claims:', config)
        self.assertNotIn('discord-relay', server)
        self.assertNotIn('claims-config', server)
        self.assertIn('MODRINTH_DOWNLOAD_DEPENDENCIES: none', config)

    def test_smoke_mod_pins_match_gitops(self):
        config = (ROOT / 'kubernetes/apps/minecraft/configmap.yaml').read_text()
        block = config.split('  MODRINTH_PROJECTS: |-\n', 1)[1].split('\n  MODRINTH_DOWNLOAD_DEPENDENCIES:', 1)[0]
        smoke = runpy.run_path(str(ROOT / 'scripts/minecraft/smoke-vanilla.py'))
        self.assertEqual(set(smoke['PINS'].split(',')), {x.strip() for x in block.splitlines() if x.strip()})
        lock = json.loads((ROOT / 'scripts/minecraft/server-mod-lock.json').read_text())
        self.assertEqual({x['version_id'] for x in lock}, {x.split(':', 1)[1] for x in smoke['PINS'].split(',')})
        self.assertTrue(all(len(x['sha512']) == 128 for x in lock))

if __name__ == '__main__':
    unittest.main()
