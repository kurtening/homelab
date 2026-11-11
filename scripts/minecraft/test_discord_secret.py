import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('discord_secret', Path(__file__).with_name('configure-discord-secret.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiscordSecretTest(unittest.TestCase):
    def test_private_capture_and_refuse_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            identity = root / 'age-key'
            subprocess.run(['age-keygen', '-o', str(identity)], check=True, capture_output=True)
            recipient = subprocess.check_output(['age-keygen', '-y', str(identity)], text=True).strip()
            source = root / 'placeholder.yaml'
            source.write_text('apiVersion: v1\nkind: Secret\nmetadata:\n  name: minecraft-discord-webhook\n  annotations:\n    homelab.kurtening.dev/credential-status: PENDING\nstringData:\n  webhook: PENDING\n')
            destination = root / 'webhook.sops.yaml'
            destination.write_bytes(subprocess.check_output(['sops', 'encrypt', '--age', recipient, '--encrypted-regex', '^(data|stringData)$', str(source)], cwd=root))
            fake = 'https://discord.com/api/webhooks/123/SYNTHETIC_SECRET'
            with patch.dict(os.environ, {'SOPS_AGE_KEY_FILE': str(identity)}), patch.object(module, 'DESTINATION', destination), patch.object(module, 'RECIPIENT', recipient), patch.object(module.getpass, 'getpass', return_value=fake), contextlib.redirect_stdout(io.StringIO()) as output:
                module.main()
                value = json.loads(module.run(['sops', 'decrypt', '--output-type', 'json', str(destination)]))
                self.assertEqual(value['stringData']['webhook'], fake)
                self.assertNotIn(fake, output.getvalue())
                self.assertNotIn(fake, destination.read_text())
                with self.assertRaises(ValueError):
                    module.main()


if __name__ == '__main__':
    unittest.main()
