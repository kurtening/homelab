#!/usr/bin/env python3
"""Offline topology, privacy, resource and staging invariants."""
import json
from pathlib import Path
import re
import subprocess
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'kubernetes/apps/monitoring'
DOCS=list(yaml.safe_load_all(subprocess.check_output(['kustomize','build',str(BASE)],text=True)))

class Tests(unittest.TestCase):
    def test_all_images_immutable_and_caps_exact(self):
        memory=cpu=0
        for d in DOCS:
            if d['kind'] not in ('Deployment','DaemonSet'):continue
            pod=d['spec']['template']['spec']
            self.assertTrue(pod['securityContext']['runAsNonRoot'])
            for c in pod['containers']:
                self.assertRegex(c['image'],r'@sha256:[0-9a-f]{64}$')
                self.assertTrue(c['securityContext']['readOnlyRootFilesystem'])
                self.assertFalse(c['securityContext']['allowPrivilegeEscalation'])
                self.assertEqual(c['securityContext']['capabilities']['drop'],['ALL'])
                limit=c['resources']['limits'];memory+=int(limit['memory'][:-2]);cpu+=int(limit['cpu'][:-1])
                self.assertNotIn('hostPort',str(c))
        self.assertEqual(memory,1888)
        proxy=next(d for d in DOCS if d['kind']=='ProxyClass')['spec']['statefulSet']['pod']['tailscaleContainer']['resources']['limits']
        self.assertEqual(memory+int(proxy['memory'][:-2])+32,2048)
        self.assertLessEqual(cpu+int(proxy['cpu'][:-1])+100,2000)

    def test_staged_applications_disconnected(self):
        rendered=subprocess.check_output(['kustomize','build',str(ROOT/'kubernetes/clusters/krof-desktop')],text=True)
        names=[d['metadata']['name'] for d in yaml.safe_load_all(rendered) if d]
        self.assertNotIn('monitoring',names);self.assertNotIn('monitoring-secrets',names)

    def test_only_private_grafana_ingress(self):
        ing=[d for d in DOCS if d['kind']=='Ingress']
        self.assertEqual(len(ing),1);self.assertEqual(ing[0]['spec']['tls'][0]['hosts'],['grafana'])
        for d in DOCS:
            if d['kind']=='Service':self.assertEqual(d['spec'].get('type','ClusterIP'),'ClusterIP')

    def test_log_roles_remain_namespace_scoped(self):
        roles=[d for d in DOCS if d['kind']=='Role']
        self.assertEqual({d['metadata']['namespace'] for d in roles},{'argocd','kube-system','tailscale','monitoring'})
        for d in DOCS:
            if d['kind']=='ClusterRole':
                resources=[r for rule in d['rules'] for r in rule.get('resources',[])]
                self.assertFalse({'secrets','pods/log','pods/exec','nodes/proxy'} & set(resources))

    def test_log_config_excludes_family_apps_and_limits_journals(self):
        text=(BASE/'config/config.alloy').read_text()
        self.assertIn('names = ["argocd", "kube-system", "tailscale", "monitoring"]',text)
        self.assertNotIn('"immich"',text);self.assertNotIn('"jellyfin"',text);self.assertNotIn('"minecraft"',text)
        matches=re.findall(r'  matches = "([^"]+)"',text)
        self.assertEqual(len(matches),2)
        self.assertTrue(all(s=='_SYSTEMD_UNIT=immich-restic-backup.service _SYSTEMD_UNIT=jellyfin-restic-backup.service _SYSTEMD_UNIT=minecraft-restic-backup.service' for s in matches))
        expression=json.loads(re.search(r'    expression = (".*")',text)[1])
        for line in ['https://discord.com/api/webhooks/123/fixture','Authorization: fixture','Bearer fixture','password=fixture','/data/library/upload/fixture.jpg']:
            self.assertRegex(line,expression)
        self.assertIsNone(re.search(expression,'Backup completed successfully'))

    def test_pvc_retention_and_no_production_storage(self):
        pvcs=[d for d in DOCS if d['kind']=='PersistentVolumeClaim']
        self.assertEqual(len(pvcs),5)
        for d in pvcs:
            self.assertEqual(d['spec']['storageClassName'],'local-path')
            self.assertEqual(d['metadata']['annotations']['argocd.argoproj.io/sync-options'],'Prune=false,Delete=false')
        for d in DOCS:
            if d['kind'] in ('Deployment','DaemonSet'):
                for v in d['spec']['template']['spec'].get('volumes',[]):
                    if 'hostPath' in v:self.assertNotIn('/mnt/',v['hostPath']['path'])

    def test_secret_projection_and_notification_privacy(self):
        alert=next(d for d in DOCS if d['kind']=='Deployment' and d['metadata']['name']=='alertmanager')
        secret=next(v['secret'] for v in alert['spec']['template']['spec']['volumes'] if 'secret' in v)
        self.assertEqual(secret['items'],[{'key':'DISCORD_WEBHOOK_URL','path':'DISCORD_WEBHOOK_URL'}])
        config=yaml.safe_load((BASE/'config/alertmanager.yml').read_text())
        discord=config['receivers'][0]['discord_configs'][0]
        self.assertIn('webhook_url_file',discord);self.assertNotIn('webhook_url',discord)
        message=discord['message']+discord['title']
        for forbidden in ('GeneratorURL','ExternalURL','Annotations','instance','pod','@everyone','@here'):
            self.assertNotIn(forbidden,message)

    def test_dashboards_and_retention(self):
        self.assertEqual(len(list((BASE/'dashboards').glob('*.json'))),5)
        for path in (BASE/'dashboards').glob('*.json'):
            d=json.loads(path.read_text());self.assertTrue(d['panels']);self.assertTrue(d['uid'])
        loki=yaml.safe_load((BASE/'config/loki.yml').read_text())
        self.assertTrue(loki['compactor']['retention_enabled'])
        self.assertEqual(loki['limits_config']['retention_period'],'24h')
        prom=yaml.safe_load((BASE/'config/prometheus.yml').read_text())
        self.assertEqual(prom['global']['scrape_interval'],'60s')
        self.assertNotIn('insecure_skip_verify',(BASE/'config/prometheus.yml').read_text())

    def test_secret_ciphertext_and_recipient_preserved(self):
        secret=yaml.safe_load((ROOT/'kubernetes/secrets/monitoring/monitoring-credentials.sops.yaml').read_text())
        expected=yaml.safe_load((ROOT/'.sops.yaml').read_text())['creation_rules'][0]['age']
        self.assertEqual([a['recipient'] for a in secret['sops']['age']],expected)
        self.assertEqual(set(secret['stringData']),{'DISCORD_WEBHOOK_URL','GRAFANA_ADMIN_PASSWORD','GRAFANA_ROOT_URL'})
        self.assertTrue(all(v.startswith('ENC[') for v in secret['stringData'].values()))
        self.assertNotIn('homelab.kurtening.dev/credential-status',secret['metadata'].get('annotations',{}))

if __name__=='__main__':unittest.main()
