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
spec = importlib.util.spec_from_file_location('admin_secret', Path(__file__).with_name('create-admin-secret.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdminSecretTest(unittest.TestCase):
    def test_capture_verify_and_refresh_keep_admin_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root / 'age-key'
            subprocess.run(['age-keygen', '-o', str(identity)], check=True, capture_output=True)
            recipient = subprocess.check_output(['age-keygen', '-y', str(identity)], text=True).strip()
            source = root / 'placeholder.yaml'
            source.write_text('apiVersion: v1\nkind: Secret\nmetadata:\n  name: minecraft-admin-credentials\n  annotations:\n    homelab.kurtening.dev/credential-status: PENDING\nstringData:\n  rcon-password: PENDING\n  admin-password: PENDING\n  websocket-url: PENDING\n')
            target = root / 'credentials.sops.yaml'
            target.write_bytes(subprocess.check_output(['sops', 'encrypt', '--age', recipient, '--encrypted-regex', '^(data|stringData)$', str(source)], cwd=root))
            real_run = module.run
            current = ['abcdef0123456789abcdef01']

            def fake_run(args, **kwargs):
                if args[:3] == ['kubectl', 'config', 'current-context']:
                    return b'homelab-desktop\n'
                if args[:3] == ['tailscale', 'status', '--json']:
                    return json.dumps({'CurrentTailnet': {'MagicDNSSuffix': 'example.ts.net'}}).encode()
                if args[0] == 'kubectl':
                    return ('password=' + current[0] + '\n').encode()
                return real_run(args, **kwargs)

            with patch.dict(os.environ, {'SOPS_AGE_KEY_FILE': str(identity)}), patch.object(module, 'DESTINATION', target), patch.object(module, 'RECIPIENT', recipient), patch.object(module, 'run', side_effect=fake_run), patch.object(module.getpass, 'getpass', return_value='synthetic-admin-password-123'), patch.object(sys, 'argv', ['helper']), contextlib.redirect_stdout(io.StringIO()) as output:
                module.main()
                first = json.loads(real_run(['sops', 'decrypt', '--output-type', 'json', str(target)]))['stringData']
                self.assertEqual(first['rcon-password'], current[0])
                self.assertNotIn(current[0], output.getvalue())
                with patch.object(sys, 'argv', ['helper', '--verify']):
                    module.main()
                current[0] = '0123456789abcdef01234567'
                with patch.object(sys, 'argv', ['helper', '--verify']):
                    with self.assertRaises(ValueError):
                        module.main()
                with patch.object(sys, 'argv', ['helper', '--refresh-rcon']):
                    module.main()
                second = json.loads(real_run(['sops', 'decrypt', '--output-type', 'json', str(target)]))['stringData']
                self.assertEqual(second['rcon-password'], current[0])
                self.assertEqual(second['admin-password'], first['admin-password'])
                with self.assertRaises(ValueError):
                    module.main()


if __name__ == '__main__':
    unittest.main()
