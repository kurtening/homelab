#!/usr/bin/env python3
"""Synthetic status/contract tests. No cluster, SSH, credentials or sudo."""
import contextlib
import copy
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader('homelab_status', str(ROOT / 'scripts/homelab-status'))
spec = importlib.util.spec_from_loader(loader.name, loader)
status = importlib.util.module_from_spec(spec)
loader.exec_module(status)
CONTRACT = json.loads((ROOT / 'scripts/homelab-contract.json').read_text())


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.now = time.time()
        self.checks = []
        self.add = lambda key, state, message: self.checks.append({'check': key, 'status': state, 'message': message})
        self.host = {'schema_version': 1, 'target': True, 'observed_at': self.now,
                     'mounts': {'data': True, 'backup': True}, 'collector': self.now,
                     'files': {key: hashlib.sha256((ROOT / 'host/krof-desktop' / key).read_bytes()).hexdigest()
                               for key in status.installed_files()},
                     'units': {}}
        for app in (*status.APPS, 'collector'):
            self.host['units'][app] = {'.serviceLoadState': 'loaded', '.timerLoadState': 'loaded',
                '.timerActiveState': 'active', '.timerUnitFileState': 'enabled',
                '.serviceActiveState': 'inactive', '.serviceResult': 'success',
                '.serviceExecMainStatus': '0', 'finished': self.now - 60}

    def host_check(self):
        status.check_host(self.host, ROOT, self.add, self.now)
        return status.exit_status(self.checks)

    def test_healthy_host(self):
        self.assertEqual(self.host_check(), 0)

    def test_missing_unit_is_failure(self):
        self.host['units']['minecraft']['.serviceLoadState'] = 'not-found'
        self.assertEqual(self.host_check(), 1)

    def test_drift_and_missing_files_are_failures(self):
        self.host['files'][next(iter(self.host['files']))] = 'missing'
        self.assertEqual(self.host_check(), 1)

    def test_protected_hash_is_pending_not_mismatch(self):
        self.host['files'][next(iter(self.host['files']))] = 'protected'
        self.assertEqual(self.host_check(), 2)

    def test_wrong_mount_is_failure(self):
        self.host['mounts']['data'] = False
        self.assertEqual(self.host_check(), 1)

    def test_stale_collector_is_failure(self):
        self.host['collector'] -= 1000
        self.assertEqual(self.host_check(), 1)

    def test_missing_collector_and_never_observed_completion_are_pending(self):
        self.host['collector'] = None
        self.host['units']['minecraft']['finished'] = 0
        self.assertEqual(self.host_check(), 2)

    def test_stale_or_future_report_never_reuses_old_pass(self):
        for shift in (-1000, 1000):
            self.checks.clear()
            self.host['observed_at'] = self.now + shift
            self.assertEqual(self.host_check(), 2)
            self.assertEqual(len(self.checks), 1)

    def test_wrong_host_fails_before_other_host_checks(self):
        self.host['target'] = False
        self.assertEqual(self.host_check(), 1)
        self.assertEqual(len(self.checks), 1)

    def test_wrong_context_never_contacts_cluster(self):
        with patch.object(status, 'command', return_value='other-context'), patch.object(status, 'kube') as kube:
            status.check_cluster(CONTRACT, self.add)
            kube.assert_not_called()
        self.assertEqual(status.exit_status(self.checks), 1)

    def test_offline_main_is_pending_without_sudo_or_secret_output(self):
        def offline(args, **kwargs):
            self.assertNotIn('sudo', args)
            raise status.Unavailable
        with patch.object(status, 'command', side_effect=offline), patch.object(sys, 'argv', ['homelab-status', '--json']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(status.main(), 2)
        report = json.loads(output.getvalue())
        self.assertEqual(report['status'], 'PENDING')
        self.assertNotIn('Traceback', output.getvalue())

    def test_stderr_with_sensitive_data_is_never_forwarded(self):
        with patch.object(status.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'private-marker')):
            with self.assertRaises(status.Unavailable) as error:
                status.command(['fixture'])
        self.assertNotIn('private-marker', str(error.exception))

    def test_malformed_host_report_is_not_a_pass(self):
        with self.assertRaises(ValueError):
            status.check_host([], ROOT, self.add, self.now)

    def test_healthy_cluster_and_binding_failure(self):
        def fixture(args):
            if args[:2] == ['get', 'nodes']:
                return {'items': [{'metadata': {'name': 'krof-desktop'}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}}]}
            if args[:2] == ['get', 'applications']:
                return {'items': [{'metadata': {'name': name}, 'status': {'sync': {'status': 'Synced'}, 'health': {'status': 'Healthy'}}} for name in CONTRACT['applications']]}
            namespace = args[args.index('-n') + 1]
            return {'items': [{'kind': kind, 'metadata': {'name': name, 'generation': 1},
                'spec': {'replicas': 1, 'volumeName': binding or 'dynamic-binding'},
                'status': {'observedGeneration': 1, 'readyReplicas': 1, 'numberReady': 1, 'desiredNumberScheduled': 1, 'phase': 'Bound'}}
                for kind, name, binding in CONTRACT['resources'][namespace]]}
        with patch.object(status, 'command', return_value=status.CONTEXT), patch.object(status, 'kube', side_effect=fixture):
            status.check_cluster(CONTRACT, self.add)
        self.assertEqual(status.exit_status(self.checks), 0)
        self.assertEqual(len({c['check'] for c in self.checks}), len(self.checks))
        def wrong_binding(args):
            report = fixture(args)
            for item in report['items']:
                if item.get('kind') == 'PersistentVolumeClaim':
                    item['spec']['volumeName'] = 'wrong-volume'
            return report
        self.checks.clear()
        with patch.object(status, 'command', return_value=status.CONTEXT), patch.object(status, 'kube', side_effect=wrong_binding):
            status.check_cluster(CONTRACT, self.add)
        self.assertEqual(status.exit_status(self.checks), 1)

    def test_contract_matches_tracked_application_and_workload_manifests(self):
        paths = list((ROOT / 'kubernetes/clusters/krof-desktop').glob('*application.yaml'))
        paths += [ROOT / 'kubernetes/clusters/krof-desktop/monitoring/applications.yaml']
        applications = {doc['metadata']['name'] for path in paths for doc in yaml.safe_load_all(path.read_text()) if doc and doc['kind'] == 'Application'}
        self.assertEqual(set(CONTRACT['applications']), applications)
        for namespace, resources in CONTRACT['resources'].items():
            expected = set()
            for path in (ROOT / 'kubernetes/apps' / namespace).glob('*.yaml'):
                for doc in yaml.safe_load_all(path.read_text()):
                    if doc and doc.get('kind') in {'Deployment', 'StatefulSet', 'DaemonSet', 'PersistentVolumeClaim'}:
                        binding = doc['spec'].get('volumeName') if doc['kind'] == 'PersistentVolumeClaim' else None
                        expected.add((doc['kind'], doc['metadata']['name'], binding))
            self.assertEqual({tuple(row) for row in resources}, expected)


if __name__ == '__main__':
    unittest.main()
