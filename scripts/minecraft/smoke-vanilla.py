#!/usr/bin/env python3
"""Start the pinned mod stack in an isolated, disposable Docker world."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time

IMAGE = 'itzg/minecraft-server@sha256:efa878ddb49cf5251b2e5f2ad71b08fd2f7236c1f7907433f6697258b31d2ce4'
JAR_SHA256 = 'ea737a731d1d4ba983b40266dbabb7d20aad0ebb226408155cbdb487322db851'
ROOT = Path(__file__).resolve().parents[2]
PINS = 'fabric-api:lOQ4tyDD,lithium:fQBdPR1m,ferrite-core:d5ddUdiB,leaves-us-in-peace:OZtHERvr,fabric-language-kotlin:Pd0xrHCw,open-parties-and-claims:oT1wWKmM,forge-config-api-port:jUe0ucoE,ledger:NopA8uYe,luckperms:Nq5UZXxA,spark:e3hsPc1o'


def run(args, **kwargs):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)


def main():
    with tempfile.TemporaryDirectory(prefix='minecraft-vanilla-smoke-') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        data, mods, docker_config = (root / name for name in ('data', 'mods', 'docker'))
        for path in (data, mods, docker_config):
            path.mkdir()
        (data / 'config').mkdir()
        (data / 'config/openpartiesandclaims-server.toml').write_bytes(
            (ROOT / 'kubernetes/apps/minecraft/claims/openpartiesandclaims-server.toml').read_bytes())
        download = run(['gh', 'release', 'download', 'v0.5.0', '--repo',
                        'WesterhofRoy/fabric-discord-notifier', '--pattern',
                        'fabric-discord-notifier-0.5.0.jar', '--dir', str(mods)], timeout=90)
        jar = mods / 'fabric-discord-notifier-0.5.0.jar'
        if download.returncode or hashlib.sha256(jar.read_bytes()).hexdigest() != JAR_SHA256:
            raise RuntimeError('Cannot retrieve pinned notifier or hash mismatch')
        env = os.environ.copy()
        env['DOCKER_CONFIG'] = str(docker_config)
        values = {'EULA': 'TRUE', 'TYPE': 'FABRIC', 'VERSION': '26.1.2',
                  'FABRIC_LOADER_VERSION': '0.19.3', 'FABRIC_LAUNCHER_VERSION': '1.1.2',
                  'MODRINTH_PROJECTS': PINS, 'MODRINTH_DOWNLOAD_DEPENDENCIES': 'none',
                  'MODS': '/test/fabric-discord-notifier-0.5.0.jar', 'LEVEL': 'world-season-2',
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
            properties = (data / 'server.properties').read_text().splitlines()
            if 'level-seed=' + values['SEED'] not in properties or 'level-name=' + values['LEVEL'] not in properties:
                raise RuntimeError('Disposable seed or level configuration mismatch')
            print('PASS: disposable pinned server is healthy, seed and level match, and RCON responds')
            print('PENDING: real-player, claims, permissions, restart and recovery tests')
        finally:
            run(['docker', 'rm', '-f', name], env=env, timeout=40)


if __name__ == '__main__':
    main()
