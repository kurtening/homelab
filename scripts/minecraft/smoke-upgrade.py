#!/usr/bin/env python3
"""Rehearse a 26.1.2 to 26.3 upgrade on disposable data; no ports or credentials."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
NEW = runpy.run_path(str(ROOT / 'scripts/minecraft/smoke-vanilla.py'))
OLD = 'fabric-api:lOQ4tyDD,lithium:fQBdPR1m,ferrite-core:d5ddUdiB,leaves-us-in-peace:OZtHERvr,fabric-language-kotlin:Pd0xrHCw,open-parties-and-claims:oT1wWKmM,forge-config-api-port:jUe0ucoE,ledger:NopA8uYe,luckperms:Nq5UZXxA,spark:e3hsPc1o'
IMAGE = NEW['IMAGE']

def run(args, **kwargs):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)

def main():
    with tempfile.TemporaryDirectory(prefix='minecraft-upgrade-') as temp:
        root = Path(temp)
        root.chmod(0o755)
        data, mods = root / 'data', root / 'source'
        data.mkdir(mode=0o777); data.chmod(0o777)
        mods.mkdir(mode=0o755)
        url = 'https://github.com/WesterhofRoy/fabric-discord-notifier/releases/download/v0.5.0/fabric-discord-notifier-0.5.0.jar'
        request = urllib.request.Request(url, headers={'User-Agent': 'homelab-upgrade-test/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            jar = response.read()
        if hashlib.sha256(jar).hexdigest() != 'ea737a731d1d4ba983b40266dbabb7d20aad0ebb226408155cbdb487322db851':
            raise RuntimeError('old notifier checksum mismatch')
        (mods / 'fabric-discord-notifier-0.5.0.jar').write_bytes(jar)
        name = 'minecraft-upgrade-' + root.name.rsplit('-', 1)[-1]
        common = {'EULA': 'TRUE', 'TYPE': 'FABRIC', 'FABRIC_LAUNCHER_VERSION': '1.1.2',
                  'MODRINTH_DOWNLOAD_DEPENDENCIES': 'none', 'LEVEL': 'forever-world',
                  'INIT_MEMORY': '512M', 'MAX_MEMORY': '1G', 'ONLINE_MODE': 'FALSE',
                  'ENABLE_RCON': 'TRUE', 'RCON_PASSWORD': 'synthetic-disposable',
                  'VIEW_DISTANCE': '4', 'SIMULATION_DISTANCE': '4'}
        def stage(version, loader, pins, mod):
            values = dict(common, VERSION=version, FABRIC_LOADER_VERSION=loader, MODRINTH_PROJECTS=pins, MODS=mod)
            args = ['docker', 'run', '-d', '--rm', '--name', name, '--memory', '2500m',
                    '--cpus', '1.5', '--pids-limit', '512', '-v', str(data)+':/data', '-v', str(mods)+':/test:ro']
            for k, v in values.items(): args.extend(['-e', k+'='+v])
            result = run(args + [IMAGE], timeout=30)
            if result.returncode: raise RuntimeError('container start failed: '+result.stdout)
            try:
                deadline = time.monotonic()+600
                while time.monotonic() < deadline:
                    state = run(['docker', 'inspect', '--format', '{{.State.Running}}', name])
                    if state.returncode or state.stdout.strip() != 'true': raise RuntimeError('server exited')
                    if run(['docker','exec',name,'mc-health'],timeout=15).returncode == 0: break
                    time.sleep(5)
                else: raise RuntimeError('server readiness timed out')
                if run(['docker','exec',name,'rcon-cli','save-all','flush'],timeout=45).returncode:
                    raise RuntimeError('save flush failed')
                if version == '26.1.2':
                    names = [p.name.lower() for p in (data/'mods').glob('*.jar')]
                    if not any('open-parties-and-claims' in p for p in names) or not any('discord-notifier' in p for p in names):
                        raise RuntimeError('old JARs were not installed')
                else:
                    names = [p.name.lower() for p in (data/'mods').glob('*.jar')]
                    if any('open-parties-and-claims' in p or 'discord-notifier' in p for p in names):
                        raise RuntimeError('old managed JAR remained after upgrade')
                    if not (data/'forever-world/level.dat').is_file(): raise RuntimeError('world missing')
                    for item in json.loads((ROOT / 'scripts/minecraft/server-mod-lock.json').read_text()):
                        path = data / 'mods' / item['filename']
                        if not path.is_file() or hashlib.sha512(path.read_bytes()).hexdigest() != item['sha512']:
                            raise RuntimeError('mod checksum mismatch: ' + item['version_id'])
                print('PASS:', version, 'ready and saved', flush=True)
            except Exception:
                print(run(['docker','logs','--tail','80',name]).stdout, flush=True)
                raise
            finally:
                stopped = run(['docker','stop','--time','60',name], timeout=75)
                if stopped.returncode:
                    raise RuntimeError('could not stop disposable server: ' + stopped.stdout)
                deadline = time.monotonic() + 30
                while run(['docker', 'inspect', name]).returncode == 0:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('container removal timed out')
                    time.sleep(1)
        stage('26.1.2','0.19.3',OLD,'/test/fabric-discord-notifier-0.5.0.jar')
        stage('26.3','0.20.1',NEW['PINS'],'')
        print('PASS: old managed claims and notifier JARs removed from upgraded disposable data')
        print('PENDING: real restored world, client gameplay, claims impact and production acceptance')

if __name__ == '__main__':
    main()
