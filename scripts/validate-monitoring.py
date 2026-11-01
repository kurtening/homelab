#!/usr/bin/env python3
"""Validate public configs using the exact digest-pinned images, without network in validators."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'kubernetes/apps/monitoring'
images={x['name']:x['newName']+':'+x['newTag']+'@'+x['digest'] for x in yaml.safe_load((BASE/'kustomization.yaml').read_text())['images']}
with tempfile.TemporaryDirectory(prefix='monitoring-validation-') as directory:
    temp=Path(directory);(temp/'docker').mkdir()
    # No changes to the operator's Docker config/credential helper. Public images only.
    env=dict(os.environ,DOCKER_CONFIG=str(temp/'docker'))
    fixture=temp/'credentials';fixture.mkdir(mode=0o755)
    (fixture/'DISCORD_WEBHOOK_URL').write_text('https://discord.com/api/webhooks/000000000000000000/disposable-validation-fixture')
    (fixture/'DISCORD_WEBHOOK_URL').chmod(0o644)
    pulled=set()
    def run(name, entrypoint, arguments, mounts=(), extra=(), capture=False):
        image=images[name]
        if image not in pulled:
            subprocess.run(['docker','pull',image],env=env,check=True,stdout=subprocess.DEVNULL)
            pulled.add(image)
        command=['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:mode=1777,size=128m','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m']
        for source,target in mounts:command+=['--mount',f'type=bind,src={source},dst={target},readonly']
        command+=list(extra)+['--entrypoint',entrypoint,image]+arguments
        result=subprocess.run(command,env=env,check=True,text=True,stdout=subprocess.PIPE if capture else None)
        return result.stdout
    run('prometheus','/bin/promtool',['check','config','--syntax-only','/etc/prometheus/prometheus.yml'],[(BASE/'config','/etc/prometheus')])
    run('prometheus','/bin/promtool',['test','rules','/tests/monitoring-rules.yml'],[(BASE/'config','/etc/prometheus'),(ROOT/'scripts/fixtures','/tests')])
    run('alertmanager','/bin/amtool',['check-config','/etc/alertmanager/config/alertmanager.yml'],[(BASE/'config','/etc/alertmanager/config'),(fixture,'/etc/alertmanager/credentials')])
    (fixture/'fixture.tmpl').write_text('{{ define "fixture" }}fixture{{ end }}')
    (fixture/'fixture.tmpl').chmod(0o644)
    receiver=yaml.safe_load((BASE/'config/alertmanager.yml').read_text())['receivers'][0]['discord_configs'][0]
    for status in ['firing','resolved']:
        data={'receiver':'discord','status':status,'groupLabels':{'alertname':'HomelabMonitoringTest','severity':'warning','application':'immich'},
              'commonLabels':{'instance':'private.invalid'},'commonAnnotations':{'description':'do-not-send'},
              'externalURL':'https://private.invalid','alerts':[]}
        (fixture/'data.json').write_text(json.dumps(data));(fixture/'data.json').chmod(0o644)
        output=run('alertmanager','/bin/amtool',['template','render','--template.glob=/fixtures/*.tmpl','--template.data=/fixtures/data.json',
                   '--template.text='+receiver['title']+'\n'+receiver['message']],[(fixture,'/fixtures')],capture=True)
        if any(value in output for value in ['private.invalid','do-not-send','@everyone','@here']) or status not in output or 'HomelabMonitoringTest' not in output:
            raise SystemExit('FAIL: notification template privacy/status fixture')
    run('loki','/usr/bin/loki',['-config.file=/config/loki.yml','-verify-config=true'],[(BASE/'config','/config')],['--tmpfs','/loki:uid=10001,gid=10001,mode=0700,size=64m'])
    run('alloy','/bin/alloy',['validate','/config/config.alloy'],[(BASE/'config','/config')])
print('PASS: pinned monitoring configuration and PromQL tests; no production credentials supplied')
