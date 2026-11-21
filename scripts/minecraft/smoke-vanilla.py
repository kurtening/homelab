#!/usr/bin/env python3
"""Start the pinned mod stack in an isolated, disposable Docker world."""
import os
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

IMAGE = 'itzg/minecraft-server@sha256:efa878ddb49cf5251b2e5f2ad71b08fd2f7236c1f7907433f6697258b31d2ce4'
ROOT = Path(__file__).resolve().parents[2]
PINS = 'fabric-api:Zns5SSRA,lithium:Lal8mJGR,ferrite-core:d5ddUdiB,leaves-us-in-peace:apF73NDo,fabric-language-kotlin:SKW1BTL3,ledger:pxv5cN0d,luckperms:DzQPkkXY,spark:e3hsPc1o'


def run(args, **kwargs):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)


def main():
    with tempfile.TemporaryDirectory(prefix='minecraft-vanilla-smoke-') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        data, mods, docker_config = (root / name for name in ('data', 'mods', 'docker'))
        for path in (data, mods, docker_config):
            path.mkdir()
        env = os.environ.copy()
        env['DOCKER_CONFIG'] = str(docker_config)
        values = {'EULA': 'TRUE', 'TYPE': 'FABRIC', 'VERSION': '26.3',
                  'FABRIC_LOADER_VERSION': '0.20.1', 'FABRIC_LAUNCHER_VERSION': '1.1.2',
                  'MODRINTH_PROJECTS': PINS, 'MODRINTH_DOWNLOAD_DEPENDENCIES': 'none',
                  'MODS': '', 'LEVEL': 'forever-world',
                  'SEED': '-4995054936707021313',
                  'INIT_MEMORY': '512M', 'MAX_MEMORY': '1G', 'ONLINE_MODE': 'FALSE',
                  'ENABLE_RCON': 'TRUE', 'RCON_PASSWORD': 'synthetic-disposable',
                  'PAUSE_WHEN_EMPTY_SECONDS': '600'}
        name = 'codex-vanilla-smoke-' + root.name.rsplit('-', 1)[-1]
        args = ['docker', 'run', '-d', '--rm', '--name', name, '--memory', '2500m',
                '--cpus', '1.5', '--pids-limit', '512', '-v', str(data) + ':/data',
                '-v', str(mods) + ':/test:ro']
        for key, value in values.items():
            args.extend(['-e', key + '=' + value])
        try:
            started = run(args + [IMAGE], env=env, timeout=30)
            if started.returncode:
                raise RuntimeError('Disposable server did not start')
            deadline = time.monotonic() + 420
            while time.monotonic() < deadline:
                state = run(['docker', 'inspect', '--format', '{{.State.Running}}', name], env=env)
                if state.returncode or state.stdout.strip() != 'true':
                    raise RuntimeError('Disposable server exited')
                if run(['docker', 'exec', name, 'mc-health'], env=env, timeout=15).returncode == 0:
                    break
                time.sleep(5)
            else:
                raise RuntimeError('Disposable server startup timed out')
            if run(['docker', 'exec', name, 'rcon-cli', 'list'], env=env, timeout=20).returncode:
                raise RuntimeError('Disposable RCON connectivity failed')
            for mod in json.loads((ROOT / 'scripts/minecraft/server-mod-lock.json').read_text()):
                path = data / 'mods' / mod['filename']
                if not path.is_file() or hashlib.sha512(path.read_bytes()).hexdigest() != mod['sha512']:
                    raise RuntimeError('Server mod checksum mismatch: ' + mod['version_id'])
            properties = (data / 'server.properties').read_text().splitlines()
            if 'level-seed=' + values['SEED'] not in properties or 'level-name=' + values['LEVEL'] not in properties:
                raise RuntimeError('Disposable seed or level configuration mismatch')
            print('PASS: disposable pinned server is healthy, seed and level match, and RCON responds')
            print('PENDING: real-player, permissions, restart and recovery tests')
        finally:
            run(['docker', 'rm', '-f', name], env=env, timeout=40)


if __name__ == '__main__':
    main()
