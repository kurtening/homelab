#!/usr/bin/env python3
"""Run the backup with synthetic commands; never access a cluster or repository."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'host/krof-desktop/backup/minecraft/minecraft-restic-backup').read_text()

STUB = '''#!/usr/bin/env python3
import os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['EVENTS'], 'a') as log:
    log.write(name + ' ' + ' '.join(args) + '\\n')
mode = os.environ['MODE']
if name == 'mountpoint':
    sys.exit(1 if mode == 'missing-mount' else 0)
if name == 'findmnt':
    print('ext4' if args[-1] == 'FSTYPE' else ('data-device' if 'data-drive' in ' '.join(args) else 'backup-device'))
if name == 'blkid':
    print('wrong' if mode == 'wrong-mount' else ('cb3505ce-970c-49c2-ad50-4bc07ddbe508' if args[-1] == 'data-device' else '3180031e-abd5-4d6a-8aac-abe3e41dc950'))
if name == 'k3s':
    if 'get' in args:
        print('fixture-pod' + ('\\nsecond-pod' if mode == 'multiple-pods' else ''))
    if 'wait' in args and mode == 'not-ready': sys.exit(1)
    if 'rcon-cli' in args:
        command = args[args.index('rcon-cli') + 1]
        if mode == command + '-failure': sys.exit(1)
if name == 'restic':
    if args[0] == 'backup' and mode == 'signal':
        import signal
        os.kill(int(os.environ['BACKUP_SHELL_PID']), signal.SIGTERM)
        sys.exit(1)
    if mode == args[0] + '-failure': sys.exit(1)
'''


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for name in ['mountpoint', 'findmnt', 'blkid', 'k3s', 'restic']:
            stub = self.directory / name
            stub.write_text(STUB)
            stub.chmod(0o700)
        for name in ['data', 'repository']:
            (self.directory / name).mkdir()
        (self.directory / 'password').write_text('synthetic fixture, not a credential')
        source = SOURCE.replace('set -Eeuo pipefail', 'set -Eeuo pipefail\nexport BACKUP_SHELL_PID=$$')
        source = source.replace('/usr/local/bin/k3s', str(self.directory / 'k3s'))
        source = source.replace('DATA_ROOT="${DATA_MOUNT}/homelab/minecraft"', f'DATA_ROOT="{self.directory}/data"')
        source = source.replace('RESTIC_REPOSITORY="${BACKUP_MOUNT}/homelab/minecraft/repository"', f'RESTIC_REPOSITORY="{self.directory}/repository"')
        source = source.replace('/etc/restic/minecraft-password', str(self.directory / 'password'))
        source = source.replace('mkdir -p /run/minecraft-backup', ': # synthetic runtime directory')
        source = source.replace('/run/minecraft-backup/backup.lock', str(self.directory / 'lock'))
        self.script = self.directory / 'backup'
        self.script.write_text(source)

    def run_backup(self, mode='success'):
        result = subprocess.run(['bash', str(self.script)], capture_output=True,
                                env=dict(os.environ, MODE=mode, EVENTS=str(self.directory / 'events'),
                                         PATH=str(self.directory) + os.pathsep + os.environ['PATH']), timeout=15)
        self.events = (self.directory / 'events').read_text().splitlines() if (self.directory / 'events').exists() else []
        self.rcon = [line.split('rcon-cli ', 1)[1] for line in self.events if 'rcon-cli ' in line]
        return result

    def test_success_order_and_bounded_quiet_copy(self):
        self.assertEqual(self.run_backup().returncode, 0)
        self.assertEqual(self.rcon, ['save-off', 'save-all flush', 'save-on'])
        events = '\n'.join(self.events)
        self.assertLess(events.index('save-all flush'), events.index('restic backup'))
        self.assertLess(events.index('restic backup'), events.index('save-on'))
        self.assertLess(events.index('save-on'), events.index('restic forget'))
        self.assertIn('--quiet', events)
        self.assertIn('--request-timeout=60s', events)
        self.assertIn('2h restic backup', SOURCE)

    def test_ambiguous_save_off_failure_attempts_resume(self):
        self.assertNotEqual(self.run_backup('save-off-failure').returncode, 0)
        self.assertEqual(self.rcon, ['save-off', 'save-on'])
        self.assertFalse(any(line.startswith('restic backup') for line in self.events))

    def test_flush_failure_attempts_resume(self):
        self.assertNotEqual(self.run_backup('save-all-failure').returncode, 0)
        self.assertEqual(self.rcon[-1], 'save-on')

    def test_copy_failure_resumes_and_never_prunes(self):
        self.assertNotEqual(self.run_backup('backup-failure').returncode, 0)
        self.assertEqual(self.rcon[-1], 'save-on')
        self.assertFalse(any(line.startswith('restic forget') for line in self.events))

    def test_term_during_copy_exits_through_resume_trap(self):
        self.assertNotEqual(self.run_backup('signal').returncode, 0)
        self.assertEqual(self.rcon[-1], 'save-on')

    def test_save_on_failure_is_failure_and_retries_in_trap(self):
        self.assertNotEqual(self.run_backup('save-on-failure').returncode, 0)
        self.assertEqual(self.rcon.count('save-on'), 2)

    def test_mount_and_repository_failures_never_suspend_saves(self):
        for mode in ['missing-mount', 'wrong-mount', 'snapshots-failure', 'multiple-pods', 'not-ready']:
            with self.subTest(mode=mode):
                (self.directory / 'events').write_text('')
                self.assertNotEqual(self.run_backup(mode).returncode, 0)
                self.assertEqual(self.rcon, [])

    def test_retention_or_check_failure_is_not_success(self):
        for mode in ['forget-failure', 'check-failure']:
            with self.subTest(mode=mode):
                self.assertNotEqual(self.run_backup(mode).returncode, 0)
                self.assertEqual(self.rcon[-1], 'save-on')

    def test_concurrent_invocation_fails_before_saves(self):
        import fcntl
        with (self.directory / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self.run_backup().returncode, 0)
            self.assertEqual(self.rcon, [])

    def test_installer_does_not_initialize_enable_or_start(self):
        installer = (ROOT / 'host/krof-desktop/backup/minecraft/install-minecraft-backup').read_text()
        self.assertNotIn('restic init', installer)
        self.assertNotIn('systemctl enable', installer)
        self.assertNotIn('systemctl start', installer)
        self.assertIn('! -L ${destination}', installer)
        self.assertIn('check-minecraft-backup', installer)

    def test_explicit_manila_schedule(self):
        self.assertIn('05:30:00 Asia/Manila',
                      (ROOT / 'host/krof-desktop/backup/minecraft/minecraft-restic-backup.timer').read_text())

    def test_lock_is_writable_under_service_sandbox_and_retained(self):
        service = (ROOT / 'host/krof-desktop/backup/minecraft/minecraft-restic-backup.service').read_text()
        self.assertIn('RuntimeDirectory=minecraft-backup', service)
        self.assertIn('RuntimeDirectoryPreserve=yes', service)
        self.assertIn('ProtectSystem=strict', service)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'check-minecraft-backup').write_text('print("PASS: synthetic preflight")\n')
        source = (ROOT / 'host/krof-desktop/backup/minecraft/verify-minecraft-recovery').read_text()
        self.helper = self.root / 'verify-minecraft-recovery'
        self.helper.write_text(source.replace('/mnt/backup', str(self.root)))
        restic = self.root / 'restic'
        restic.write_text('''#!/usr/bin/env python3
import gzip, json, os, sys
from pathlib import Path
args = sys.argv[1:]
mode = os.environ['MODE']
if 'cat' in args:
    print(json.dumps({'hostname': 'krof-desktop', 'tags': ['minecraft'], 'paths':
        ['/wrong' if mode == 'wrong-source' else '/mnt/data-drive-2tb/homelab/minecraft']}))
elif 'stats' in args: print(json.dumps({'total_size': 1}))
elif 'restore' in args:
    if mode == 'restore-failure': sys.exit(1)
    destination = Path(args[args.index('--target') + 1])
    if mode == 'absolute': destination /= 'mnt/data-drive-2tb/homelab/minecraft'
    destination /= 'world'
    destination.mkdir(parents=True)
    if mode != 'missing':
        (destination / 'level.dat').write_bytes(b'corrupt' if mode == 'corrupt' else gzip.compress(b'synthetic NBT fixture'))
''')
        restic.chmod(0o700)

    def run_recovery(self, mode, snapshot='12345678'):
        return subprocess.run(['python3', str(self.helper), snapshot], capture_output=True,
                              env=dict(os.environ, MODE=mode, PATH=str(self.root) + os.pathsep + os.environ['PATH']),
                              timeout=15)

    def test_relative_and_absolute_layout(self):
        for layout in ['relative', 'absolute']:
            with self.subTest(layout=layout):
                result = self.run_recovery(layout)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b'production unchanged', result.stdout)

    def test_corrupt_missing_and_failed_restores_fail(self):
        for mode in ['corrupt', 'missing', 'restore-failure']:
            with self.subTest(mode=mode):
                self.assertNotEqual(self.run_recovery(mode).returncode, 0)

    def test_wrong_snapshot_contract_rejected_before_restore(self):
        self.assertNotEqual(self.run_recovery('wrong-source').returncode, 0)
        self.assertEqual(list(self.root.glob('minecraft-restore-check.*')), [])

    def test_latest_is_rejected(self):
        self.assertNotEqual(self.run_recovery('relative', snapshot='latest').returncode, 0)

    def test_evidence_parent_is_private_and_retained(self):
        self.assertNotEqual(self.run_recovery('restore-failure').returncode, 0)
        directories = list(self.root.glob('minecraft-restore-check.*'))
        self.assertEqual(len(directories), 1)
        self.assertEqual(directories[0].stat().st_mode & 0o777, 0o700)
        self.assertTrue((directories[0] / 'restore.log').is_file())


if __name__ == '__main__':
    unittest.main()
