#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader('collector', str(Path(__file__).resolve().parents[1] / 'host/krof-desktop/monitoring/homelab-metrics'))
spec = importlib.util.spec_from_loader(loader.name, loader)
c = importlib.util.module_from_spec(spec)
loader.exec_module(c)

class Tests(unittest.TestCase):
    def observed(self, **kwargs):
        return dict(available=True, running=False, start=80, finish=90, success=True, **kwargs)

    def test_first_success_and_unknown(self):
        self.assertEqual(c.update({}, self.observed(), 100)['last_success'], 90)
        o=self.observed();o['finish']=0
        self.assertEqual(c.update({}, o, 100)['last_success'], 0)

    def test_failure_preserves_success_across_restart(self):
        o=self.observed();o.update(success=False,finish=99)
        state=c.update(json.loads('{"last_success":50}'),o,100)
        self.assertEqual(state['last_success'],50)
        self.assertEqual(state['last_failure'],99)

    def test_running_does_not_reuse_prior_result(self):
        o=self.observed();o.update(running=True,start=98)
        self.assertEqual(c.update({},o,100)['last_success'],0)

    def test_missing_unit_is_unknown(self):
        o=self.observed();o['available']=False
        self.assertEqual(c.update({},o,100)['last_success'],0)

    def test_mount_requires_exact_target_filesystem_and_uuid(self):
        good={'target':'/expected','fstype':'ext4','uuid':'fixture'}
        with patch.object(c,'command',return_value=json.dumps({'filesystems':[good]})):
            self.assertTrue(c.mount_valid('/expected','fixture'))
            self.assertFalse(c.mount_valid('/expected','wrong'))
            self.assertFalse(c.mount_valid('/parent','fixture'))
        with patch.object(c,'command',side_effect=subprocess.CalledProcessError(1,[])):
            self.assertFalse(c.mount_valid('/expected','fixture'))

    def test_atomic_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'homelab.prom';p.write_text('old')
            c.atomic_write(p,'new',0o644)
            self.assertEqual(p.read_text(),'new')
            self.assertEqual(p.stat().st_mode & 0o777,0o644)
            self.assertEqual(len(list(Path(d).iterdir())),1)

    def test_invalid_state_fails(self):
        with self.assertRaises(ValueError):c.update({'last_success':9999},self.observed(),100)

    def test_failed_atomic_replace_keeps_prior_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'homelab.prom';p.write_text('old')
            with patch.object(c.os,'replace',side_effect=OSError('fixture')):
                with self.assertRaises(OSError):c.atomic_write(p,'new',0o644)
            self.assertEqual(p.read_text(),'old')
            self.assertEqual(len(list(Path(d).iterdir())),1)

    def test_collection_reports_preexec_failure_and_unknown_history(self):
        o=self.observed();o.update(success=False,start=0,finish=0)
        with patch.object(c,'observation',return_value=o),patch.object(c,'mount_valid',return_value=False):
            state,text=c.collect({},100)
        self.assertIn('homelab_backup_service_failed{application="immich"} 1.0',text)
        self.assertEqual(state['immich']['last_success'],0)
        self.assertIn('homelab_storage_mount_valid{role="backup"} 0.0',text)

    def test_unit_directives_offline_with_synthetic_executable(self):
        if not shutil.which('systemd-analyze'):self.skipTest('systemd-analyze unavailable')
        base=Path(__file__).resolve().parents[1]/'host/krof-desktop/monitoring'
        with tempfile.TemporaryDirectory() as d:
            for name in ['homelab-metrics.service','homelab-metrics.timer']:
                (Path(d)/name).write_text((base/name).read_text().replace('ExecStart=/usr/local/sbin/homelab-metrics','ExecStart=/usr/bin/true'))
            result=subprocess.run(['systemd-analyze','verify',str(Path(d)/'homelab-metrics.service'),str(Path(d)/'homelab-metrics.timer')],capture_output=True)
            self.assertEqual(result.returncode,0)

if __name__=='__main__':unittest.main()
