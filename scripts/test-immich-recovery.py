#!/usr/bin/env python3
"""Synthetic Immich dump, media, isolation, and cleanup checks."""
import gzip
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('immich_recovery', str(ROOT / 'host/krof-desktop/backup/immich/immich-restore-drill'))
spec = importlib.util.spec_from_loader(loader.name, loader)
r = importlib.util.module_from_spec(spec)
loader.exec_module(r)


def dump_text():
    lines = ["SELECT pg_catalog.set_config('search_path', '', false);\n"]
    for table, columns in r.PROJECTIONS.items():
        lines += ['COPY public."' + table + '" (' + ', '.join('"' + c + '"' for c in columns) + ') FROM stdin;\n',
                  '\t'.join('fixture' for _ in columns) + '\n', '\\.\n']
    return ''.join(lines).encode()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dump = self.root / 'database-dumps/immich-postgres.sql.gz'
        self.dump.parent.mkdir()
        self.library = self.root / 'library'
        self.library.mkdir()
        self.dump.write_bytes(gzip.compress(dump_text()))

    def baseline(self):
        return r.dump_baseline(self.dump, self.root / 'database.sql')

    def test_valid_copy_rows_and_restore_search_path(self):
        baseline = self.baseline()
        self.assertEqual(set(baseline), set(r.PROJECTIONS))
        self.assertTrue(all(sum(x['rows'].values()) == 1 for x in baseline.values()))
        self.assertIn("'public, pg_catalog', true", (self.root / 'database.sql').read_text())

    def test_relative_and_absolute_snapshot_layout(self):
        self.assertEqual(r.find_backup(self.root), (self.dump, self.library))
        nested = self.root / 'mnt/data-drive-2tb/homelab/immich'
        nested.mkdir(parents=True)
        self.dump.parent.rename(nested / 'database-dumps')
        self.library.rename(nested / 'library')
        self.assertEqual(r.find_backup(self.root), (nested / 'database-dumps/immich-postgres.sql.gz', nested / 'library'))

    def test_missing_dump_and_media(self):
        self.library.rmdir()
        with self.assertRaises(r.DrillError):
            r.find_backup(self.root)
        self.dump.unlink()
        with self.assertRaises(r.DrillError):
            r.find_backup(self.root)

    def test_corrupt_gzip_and_truncated_copy(self):
        self.dump.write_bytes(b'corrupt')
        with self.assertRaises((OSError, EOFError)):
            self.baseline()
        self.dump.write_bytes(gzip.compress(dump_text()[:-3]))
        with self.assertRaises(r.DrillError):
            self.baseline()

    def test_malformed_copy_and_unsupported_identifiers(self):
        self.dump.write_bytes(gzip.compress(dump_text().replace(b'fixture\t', b'fixture\tfixture\t', 1)))
        with self.assertRaises(r.DrillError):
            self.baseline()
        with self.assertRaises(r.DrillError):
            r.identifier('unsafe; SQL')

    def test_original_checksum_and_safe_paths(self):
        original = self.library / 'upload/fixture.jpg'
        original.parent.mkdir()
        original.write_bytes(b'fixture original')
        asset = {'path': '/data/upload/fixture.jpg', 'checksum': hashlib.sha1(original.read_bytes()).hexdigest(), 'algorithm': 'sha1', 'isExternal': False}
        r.verify_original(self.library, asset)
        asset['checksum'] = '0' * 40
        with self.assertRaises(r.DrillError):
            r.verify_original(self.library, asset)
        for path in ['/etc/passwd', '/data/../../etc/passwd', '/data/missing']:
            with self.assertRaises(r.DrillError):
                r.original_path(self.library, path)
        original.unlink()
        original.symlink_to('/etc/passwd')
        with self.assertRaises(r.DrillError):
            r.original_path(self.library, '/data/upload/fixture.jpg')

    def test_external_originals_are_not_silently_ignored(self):
        with self.assertRaises(r.DrillError):
            r.verify_original(self.library, {'isExternal': True})

    def test_content_mismatch_fails(self):
        with self.assertRaises(r.DrillError):
            r.assert_equal({'expected': 1}, {'expected': 0}, 'fixture')

    def test_sql_failure_is_not_masked(self):
        with patch.object(r.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(r.DrillError):
                r.run(['fixture'], io.BytesIO())

    def test_pinned_image_inventory(self):
        p = self.root / 'images.json'
        data = {'version': '3.1.0', 'extensions': {'vchord': '0.4.3'}}
        for role, repo in [('server', 'ghcr.io/immich-app/immich-server'), ('machine_learning', 'ghcr.io/immich-app/immich-machine-learning'), ('postgres', 'ghcr.io/immich-app/postgres'), ('valkey', 'docker.io/valkey/valkey')]:
            data[role] = repo + '@sha256:' + 'a' * 64
        p.write_text(json.dumps(data))
        self.assertEqual(r.images(p), data)
        data['server'] = 'ghcr.io/immich-app/immich-server:latest'
        p.write_text(json.dumps(data))
        with self.assertRaises(r.DrillError):
            r.images(p)

    def test_internal_network_and_no_published_ports(self):
        stack = r.Stack(self.root, {}, self.dump, {}, self.library, io.BytesIO())
        with patch.object(r, 'run') as run:
            stack.start('fixture', ['--memory', '1g'], 'fixture-image')
        args = run.call_args[0][0]
        self.assertIn(stack.network, args)
        self.assertNotIn('--publish', args)
        self.assertNotIn('--privileged', args)
        self.assertIn('--restart', args)

    def test_failure_cleanup_stops_all_owned_running_services(self):
        stack = r.Stack(self.root, {}, self.dump, {}, self.library, io.BytesIO())
        stack.started = ['postgres', 'server']
        def response(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=b'true\n')
        with patch.object(r.subprocess, 'run', side_effect=response) as run:
            stack.cleanup()
        stops = [c.args[0] for c in run.call_args_list if c.args[0][1] == 'stop']
        self.assertEqual([args[-1] for args in stops], [stack.name('server'), stack.name('postgres')])
        self.assertTrue(all('rm' not in c.args[0] for c in run.call_args_list))

    def test_restore_is_strict_and_network_internal_before_startup(self):
        inventory = {'version': '3.1.0', 'postgres': 'db-image', 'valkey': 'cache-image',
                     'server': 'server-image', 'machine_learning': 'ml-image', 'extensions': {'vchord': '0.4.3'}}
        stack = r.Stack(self.root, inventory, self.dump, {}, self.library, io.BytesIO())
        order = []
        def query(sql):
            return b'vchord\t0.4.3\n' if sql.startswith('COPY') else b'[]'
        with patch.object(r, 'run') as run, patch.object(stack, 'ready', side_effect=lambda role, command: order.append('ready-'+role)), \
             patch.object(stack, 'compare', side_effect=lambda projected=False: order.append('metadata' if projected else 'dump')), \
             patch.object(stack, 'query', side_effect=query):
            with contextlib.redirect_stdout(io.StringIO()):
                stack.execute()
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][:4], ['docker', 'network', 'create', '--internal'])
        restore = next(c for c in commands if '--single-transaction' in c)
        self.assertIn('ON_ERROR_STOP=on', restore)
        self.assertLess(order.index('dump'), order.index('ready-server'))
        self.assertLess(order.index('ready-server'), order.index('metadata'))


if __name__ == '__main__':
    unittest.main()
