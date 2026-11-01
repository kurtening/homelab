#!/usr/bin/env python3
"""Synthetic recovery regression tests: no Docker, host state, or credentials."""
import importlib.machinery
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader('recovery', str(ROOT / 'host/krof-desktop/backup/jellyfin/jellyfin-restore-drill'))
spec = importlib.util.spec_from_loader(loader.name, loader)
r = importlib.util.module_from_spec(spec)
loader.exec_module(r)
status_loader = importlib.machinery.SourceFileLoader('backup_status', str(ROOT / 'host/krof-desktop/backup/jellyfin/jellyfin-backup-status'))
status_spec = importlib.util.spec_from_loader(status_loader.name, status_loader)
status = importlib.util.module_from_spec(status_spec)
status_loader.exec_module(status)
IMAGE = 'jellyfin/jellyfin:10.11.11@sha256:' + 'a' * 64
USER = str(uuid.UUID(int=1))
ITEM = str(uuid.UUID(int=2))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'jellyfin-backup-20261101.zip'
        self.config = self.root / 'config'
        (self.config / 'data').mkdir(parents=True)
        (self.config / 'root/default/library').mkdir(parents=True)
        (self.config / 'root/default/library/options.xml').write_text('<LibraryOptions><Path>/media/Movies</Path></LibraryOptions>')
        self.rows = {
            'Users': [{'Id': USER, 'Username': 'fixture-user'}],
            'BaseItems': [{'Id': ITEM, 'Path': '/media/Movies/fixture', 'Type': 'Movie'}],
            'UserData': [{'ItemId': ITEM, 'UserId': USER, 'CustomDataKey': 'fixture', 'Played': True,
                          'PlaybackPositionTicks': 10, 'PlayCount': 1, 'IsFavorite': False,
                          'LastPlayedDate': '2026-11-01T00:00:00Z'}],
        }
        with sqlite3.connect(self.config / 'data/jellyfin.db') as db:
            db.execute('CREATE TABLE Users (Id TEXT, Username TEXT)')
            db.execute('INSERT INTO Users VALUES (?, ?)', (USER.upper(), 'fixture-user'))
            db.execute('CREATE TABLE BaseItems (Id TEXT, Path TEXT, Type TEXT)')
            db.execute('INSERT INTO BaseItems VALUES (?, ?, ?)', (ITEM.upper(), '/media/Movies/fixture', 'Movie'))
            db.execute('CREATE TABLE UserData (ItemId TEXT, UserId TEXT, CustomDataKey TEXT, Played INTEGER, PlaybackPositionTicks INTEGER, PlayCount INTEGER, IsFavorite INTEGER, LastPlayedDate TEXT)')
            db.execute('INSERT INTO UserData VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (ITEM.upper(), USER.upper(), 'fixture', 1, 10, 1, 0, '2026-11-01 00:00:00'))
        self.make_archive()

    def make_archive(self, version='10.11.11.0', missing=None, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('manifest.json', json.dumps({'ServerVersion': version, 'Options': {'Database': True}}))
            z.writestr('Root/default/library/options.xml', '<LibraryOptions><Path>/media/Movies</Path></LibraryOptions>')
            for table, rows in self.rows.items():
                if table != missing:
                    z.writestr('Database/' + table + '.json', json.dumps(rows))
            if extra:
                z.writestr(extra, 'unsafe')

    def check_content(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return r.verify_content(self.archive, self.config, self.root / 'report.json')

    def test_matching_content_and_private_summary(self):
        report = self.check_content()
        self.assertTrue(all(x['matched'] for x in report.values()))
        text = (self.root / 'report.json').read_text()
        self.assertNotIn('fixture-user', text)
        self.assertNotIn('/media/', text)

    def test_content_mismatch(self):
        with sqlite3.connect(self.config / 'data/jellyfin.db') as db:
            db.execute('UPDATE UserData SET Played=0, PlaybackPositionTicks=0')
        with self.assertRaises(r.RecoveryError):
            self.check_content()

    def test_missing_user_identity(self):
        with sqlite3.connect(self.config / 'data/jellyfin.db') as db:
            db.execute('DELETE FROM Users')
        with self.assertRaises(r.RecoveryError):
            self.check_content()

    def test_library_path_mismatch(self):
        (self.config / 'root/default/library/options.xml').write_text('<different/>')
        with self.assertRaises(r.RecoveryError):
            self.check_content()

    def test_missing_content_export(self):
        self.make_archive(missing='UserData')
        with self.assertRaises(r.RecoveryError):
            self.check_content()

    def test_relative_and_absolute_layouts(self):
        for layout in ['config/data/backups', 'mnt/data-drive-2tb/jellyfin/config/data/backups']:
            target = self.root / layout
            target.mkdir(parents=True)
            self.archive.replace(target / self.archive.name)
            self.assertEqual(r.choose_archive(self.root, IMAGE).parent, target)
            (target / self.archive.name).replace(self.archive)

    def test_missing_archive(self):
        self.archive.unlink()
        with self.assertRaises(r.RecoveryError):
            r.choose_archive(self.root, IMAGE)

    def test_corrupt_and_version_mismatched_archives(self):
        self.archive.write_bytes(b'partial zip')
        with self.assertRaises(r.RecoveryError):
            r.inspect_archive(self.archive, IMAGE)
        self.make_archive(version='10.12.0')
        with self.assertRaises(r.RecoveryError):
            r.inspect_archive(self.archive, IMAGE)

    def test_unsafe_archive_path(self):
        self.make_archive(extra='../outside')
        with self.assertRaises(r.RecoveryError):
            r.inspect_archive(self.archive, IMAGE)

    def test_archive_symlink_escape(self):
        link = self.root / 'jellyfin-backup-link.zip'
        link.symlink_to('/etc/passwd')
        with self.assertRaises(r.RecoveryError):
            r.choose_archive(self.root, IMAGE)

    def test_pin_and_manifest_validation(self):
        path = self.root / 'server.yaml'
        path.write_text('image: ' + IMAGE + '\n')
        self.assertEqual(r.image_from_manifest(path), IMAGE)
        path.write_text('image: jellyfin/jellyfin:latest\n')
        with self.assertRaises(r.RecoveryError):
            r.image_from_manifest(path)

    def test_schema_order_and_failure_shutdown(self):
        events = []
        start = lambda role, importing: events.append(('start', role, importing))
        wait = lambda role: events.append(('wait', role))
        stop = lambda role, cleanup=False: events.append(('stop', role, cleanup))
        r.restore_sequence(start, wait, stop, lambda: events.append(('verify',)))
        self.assertLess(events.index(('stop', 'bootstrap', False)), events.index(('start', 'restored', True)))
        self.assertLess(events.index(('stop', 'restored', False)), events.index(('verify',)))
        events.clear()
        def fail(role):
            raise r.RecoveryError('fixture failure')
        with self.assertRaises(r.RecoveryError):
            r.restore_sequence(start, fail, stop, lambda: None)
        self.assertIn(('stop', 'bootstrap', True), events)
        self.assertIn(('stop', 'restored', True), events)

    def test_invalid_resume_path(self):
        with self.assertRaises(r.RecoveryError):
            r.validate_resume(self.root, '3892c33a', IMAGE)

    def test_health_alone_is_not_restore_completion(self):
        self.assertFalse(r.startup_complete('HTTP 200 Startup complete', True))
        self.assertFalse(r.startup_complete('Restored Jellyfin system from fixture', True))
        self.assertTrue(r.startup_complete('Restored Jellyfin system from fixture\nStartup complete', True))
        self.assertTrue(r.startup_complete('Startup complete', False))
        with self.assertRaises(r.RecoveryError):
            r.startup_complete('HTTP 200 OutOfMemoryException', True)

    def test_manual_job_owner_does_not_prove_scheduled_execution(self):
        owner = {'kind': 'CronJob', 'name': 'jellyfin-backup', 'controller': True}
        manual = {'metadata': {'ownerReferences': [owner], 'annotations': {'cronjob.kubernetes.io/instantiate': 'manual'}},
                  'status': {'succeeded': 1, 'completionTime': '2026-11-01T00:00:00Z'}}
        self.assertEqual(status.scheduled_successes([manual]), [])
        scheduled = {'metadata': {'ownerReferences': [owner], 'annotations': {'batch.kubernetes.io/cronjob-scheduled-timestamp': '2026-11-01T04:00:00Z'}},
                     'status': {'succeeded': 1, 'completionTime': '2026-11-01T04:01:00Z'}}
        self.assertEqual(status.scheduled_successes([manual, scheduled]), [scheduled])
        scheduled['status']['succeeded'] = 0
        self.assertEqual(status.scheduled_successes([scheduled]), [])

    def test_snapshot_archive_correlation(self):
        from datetime import datetime, timezone
        entry = {'type': 'file', 'path': '/config/data/backups/' + self.archive.name,
                 'size': self.archive.stat().st_size,
                 'mtime': datetime.fromtimestamp(self.archive.stat().st_mtime, timezone.utc).isoformat()}
        self.assertTrue(status.archive_matches(entry, self.archive))
        entry['size'] += 1
        self.assertFalse(status.archive_matches(entry, self.archive))

    def test_raw_systemd_timestamps_avoid_duration_formatting(self):
        with patch.object(status, 'command', return_value='t 726402767143\n') as call:
            value = status.monotonic_usec('jellyfin-restic-backup.timer', 'Timer', 'LastTriggerUSecMonotonic')
            self.assertEqual(value, 726402767143)
            self.assertIn('busctl', call.call_args[0][0])
            self.assertIn('/org/freedesktop/systemd1/unit/jellyfin_2drestic_2dbackup_2etimer', call.call_args[0][0])
        with patch.object(status, 'command', return_value='1w 1d 9h 46min 42.767143s'):
            with self.assertRaises(RuntimeError):
                status.monotonic_usec('jellyfin-restic-backup.timer', 'Timer', 'LastTriggerUSecMonotonic')


if __name__ == '__main__':
    unittest.main()
