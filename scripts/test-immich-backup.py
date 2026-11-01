#!/usr/bin/env python3
"""Exercise the real dump function with synthetic commands, never a cluster."""
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'host/krof-desktop/backup/immich/immich-restic-backup').read_text()


def function(name):
    return re.search(r'^' + name + r'\(\) \{\n.*?^\}\n', SOURCE, re.M | re.S)[0]


class DumpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dump = self.root / 'immich-postgres.sql.gz'
        self.dump.write_bytes(b'existing checkpoint')
        self.stub = self.root / 'k3s'
        self.stub.write_text('''#!/usr/bin/env python3
import gzip, json, os, subprocess, sys
from pathlib import Path
Path(os.environ['ARGV_LOG']).write_text(json.dumps(sys.argv[1:]))
mode = os.environ['MODE']
if mode == 'stream-failure':
    sys.stdout.buffer.write(gzip.compress(b'partial SQL'))
    sys.exit(77)
if mode == 'corrupt':
    sys.stdout.buffer.write(b'not gzip')
    sys.exit(0)
if mode == 'empty':
    sys.exit(0)
remote = sys.argv.index('--') + 1
sys.exit(subprocess.run(sys.argv[remote:]).returncode)
''')
        self.stub.chmod(0o700)
        pg_dump = self.root / 'pg_dump'
        pg_dump.write_text('#!/usr/bin/env bash\nprintf "synthetic SQL\\n"\nif [[ "$MODE" == dump-failure ]]; then exit 23; fi\n')
        pg_dump.chmod(0o700)

    def run_dump(self, mode):
        env = dict(os.environ, MODE=mode, ARGV_LOG=str(self.root / 'argv.json'),
                   PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                   K3S_BIN=str(self.stub), DATABASE_DUMPS_PATH=str(self.root),
                   DATABASE_DUMP_PATH=str(self.dump), POSTGRES_NAMESPACE='immich',
                   POSTGRES_POD='immich-postgres-0', POSTGRES_CONTAINER='postgres',
                   POSTGRES_DATABASE='fixture database', POSTGRES_USER='fixture user')
        script = 'set -Eeuo pipefail\numask 077\nDUMP_TEMP_PATH=""\n'
        script += ''.join(function(name) for name in ['log', 'die', 'cleanup', 'create_database_dump'])
        script += '\ntrap cleanup EXIT\ncreate_database_dump\n'
        return subprocess.run(['bash', '-c', script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_compression_is_remote_and_arguments_are_preserved(self):
        result = self.run_dump('success')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(gzip.decompress(self.dump.read_bytes()), b'synthetic SQL\n')
        args = json.loads((self.root / 'argv.json').read_text())
        remote = args[args.index('--') + 1:]
        self.assertEqual(remote[:4], ['bash', '-o', 'pipefail', '-c'])
        self.assertIn('| gzip -9', remote[4])
        self.assertEqual(remote[-2:], ['fixture database', 'fixture user'])
        self.assertEqual(self.dump.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob('.immich-postgres.sql.gz.tmp.*')), [])

    def test_dump_failure_is_not_masked_by_successful_gzip(self):
        self.assert_failure_preserves_checkpoint('dump-failure')

    def test_stream_failure_is_not_promoted_even_with_valid_gzip(self):
        self.assert_failure_preserves_checkpoint('stream-failure')

    def test_corrupt_stream_preserves_checkpoint(self):
        self.assert_failure_preserves_checkpoint('corrupt')

    def test_empty_stream_preserves_checkpoint(self):
        self.assert_failure_preserves_checkpoint('empty')

    def test_compressor_failure_preserves_checkpoint(self):
        compressor = self.root / 'gzip'
        compressor.write_text('#!/usr/bin/env bash\nexit 9\n')
        compressor.chmod(0o700)
        self.assert_failure_preserves_checkpoint('success')

    def assert_failure_preserves_checkpoint(self, mode):
        self.assertNotEqual(self.run_dump(mode).returncode, 0)
        self.assertEqual(self.dump.read_bytes(), b'existing checkpoint')
        self.assertEqual(list(self.root.glob('.immich-postgres.sql.gz.tmp.*')), [])


if __name__ == '__main__':
    unittest.main()
