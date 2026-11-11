import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


class AdminManifests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = list(yaml.safe_load_all((ROOT / 'kubernetes/apps/minecraft/admin.yaml').read_text()))
        cls.by_name = {(d['kind'], d['metadata']['name']): d for d in cls.docs}

    def test_console_is_cluster_internal_and_persistent(self):
        self.assertEqual(self.by_name['Service', 'minecraft-admin']['spec']['type'], 'ClusterIP')
        self.assertEqual(self.by_name['Service', 'minecraft-rcon']['spec']['type'], 'ClusterIP')
        pvc = self.by_name['PersistentVolumeClaim', 'minecraft-admin-data']
        self.assertIn('Delete=false', pvc['metadata']['annotations']['argocd.argoproj.io/sync-options'])
        pod = self.by_name['Deployment', 'minecraft-admin']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(pod['containers'][0]['securityContext']['runAsNonRoot'], True)

    def test_rcon_ingress_is_restricted(self):
        policy = self.by_name['NetworkPolicy', 'minecraft-server-ingress']
        rules = policy['spec']['ingress']
        rcon_rules = [r for r in rules if any(p['port'] == 25575 for p in r.get('ports', []))]
        self.assertEqual(len(rcon_rules), 1)
        self.assertEqual(rcon_rules[0]['from'][0]['podSelector']['matchLabels']['app.kubernetes.io/name'], 'minecraft-admin')
        self.assertTrue(all('ports' in rule for rule in rules))

    def test_console_only_allows_tailscale_proxy(self):
        policy = self.by_name['NetworkPolicy', 'minecraft-admin-ingress']
        rule = policy['spec']['ingress'][0]
        self.assertEqual(rule['from'][0]['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name'], 'tailscale')
        self.assertEqual(rule['from'][0]['podSelector']['matchLabels']['homelab.kurtening.dev/minecraft-admin-proxy'], 'true')


if __name__ == '__main__':
    unittest.main()
