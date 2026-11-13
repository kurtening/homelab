#!/usr/bin/env python3
"""Build a pinned client mrpack without bundling mod binaries."""
import hashlib
import io
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
LOCK = json.loads((ROOT / 'lock.json').read_text())
HEADERS = {'User-Agent': 'homelab-minecraft-pack/1.0 (https://github.com/kurtening/homelab)'}


def fetch(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('api.modrinth.com', 'cdn.modrinth.com'):
        raise ValueError('unapproved download host')
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=45) as response:
        return response.read()


def verified(data, size, hashes):
    if len(data) != size:
        raise ValueError('download size mismatch')
    for algorithm in ('sha1', 'sha512'):
        if algorithm in hashes and hashlib.new(algorithm, data).hexdigest() != hashes[algorithm]:
            raise ValueError('download hash mismatch')
    if 'sha512' not in hashes:
        raise ValueError('missing SHA-512')


def remove_exclusions(files, exclusions):
    files = list(files)
    for exclusion in exclusions:
        expected = '/data/%s/versions/%s/' % (exclusion['project_id'], exclusion['version_id'])
        matches = [item for item in files if any(
            urllib.parse.urlsplit(url).path.startswith(expected) for url in item['downloads'])]
        if len(matches) != 1:
            raise ValueError('expected exactly one excluded base mod')
        files.remove(matches[0])
    return files


def main():
    base = json.loads(fetch('https://api.modrinth.com/v2/version/' + LOCK['base']['version_id']))
    primary = next(f for f in base['files'] if f['primary'])
    archive = fetch(primary['url'])
    verified(archive, primary['size'], {'sha512': LOCK['base']['sha512']})
    source = zipfile.ZipFile(io.BytesIO(archive))
    index = json.loads(source.read('modrinth.index.json'))
    if index['dependencies'] != {'fabric-loader': '0.19.5', 'minecraft': '26.1.2'}:
        raise ValueError('unexpected base game or loader')
    index['files'] = remove_exclusions(index['files'], LOCK['exclusions'])
    paths = {item['path'].lower() for item in index['files']}
    existing_urls = [url for item in index['files'] for url in item['downloads']]
    for mod in LOCK['additions']:
        path = 'mods/' + mod['filename']
        if path.lower() in paths or any('/data/' + mod['project_id'] + '/' in url for url in existing_urls):
            raise ValueError('duplicate mod: ' + path)
        paths.add(path.lower())
        index['files'].append({'path': path, 'hashes': mod['hashes'], 'downloads': [mod['url']],
                               'fileSize': mod['size'], 'env': {'client': 'required', 'server': 'unsupported'}})
    for item in index['files']:
        if not item['downloads']:
            raise ValueError('missing file download')
        verified(fetch(item['downloads'][0]), item['fileSize'], item['hashes'])
    index.update(name='krof-smp', versionId=LOCK['version'], summary='Private vanilla survival client pack')
    entries = {'modrinth.index.json': (json.dumps(index, indent=2, sort_keys=True) + '\n').encode()}
    for info in source.infolist():
        if info.is_dir() or info.filename == 'modrinth.index.json':
            continue
        p = pathlib.PurePosixPath(info.filename)
        if p.is_absolute() or '..' in p.parts or p.parts[0] not in ('overrides', 'client-overrides'):
            raise ValueError('unsafe or unknown base archive entry')
        entries[info.filename] = source.read(info)
    entries['overrides/krof-smp-credits.txt'] = (ROOT / 'CREDITS.txt').read_bytes()
    entries['overrides/krof-smp-fabulously-optimized-license.txt'] = (ROOT / 'FABULOUSLY-OPTIMIZED-LICENSE.txt').read_bytes()
    output = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'dist/krof-smp-1.0.0.mrpack'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as result:
        for name, data in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            result.writestr(entry, data)
    print('PASS: verified downloads and built', output)


if __name__ == '__main__':
    main()
