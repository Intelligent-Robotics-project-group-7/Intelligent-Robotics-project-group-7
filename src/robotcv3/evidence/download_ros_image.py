"""Download and verify an official Docker Hub ROS image without requiring Docker."""
import gzip
import hashlib
import io
import json
import pathlib
import struct
import tarfile
import time
import urllib.request

ROOT = pathlib.Path('/home/john/projects/turtlebot4_person_following')
OUT = ROOT / 'downloads'
OUT.mkdir(parents=True, exist_ok=True)
NAME = 'library/ros'
TAG = 'jazzy-ros-base-noble'
API = 'https://registry-1.docker.io/v2/' + NAME
token_url = ('https://auth.docker.io/token?service=registry.docker.io'
             '&scope=repository:library/ros:pull')
with urllib.request.urlopen(token_url, timeout=40) as response:
    TOKEN = json.load(response)['token']

def request(path):
    return urllib.request.Request(API + path, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Accept': ', '.join([
            'application/vnd.oci.image.index.v1+json',
            'application/vnd.docker.distribution.manifest.list.v2+json',
            'application/vnd.oci.image.manifest.v1+json',
            'application/vnd.docker.distribution.manifest.v2+json']),
    })

def manifest(ref):
    with urllib.request.urlopen(request('/manifests/' + ref), timeout=45) as response:
        body = response.read()
    digest = 'sha256:' + hashlib.sha256(body).hexdigest()
    return json.loads(body), digest

def blob(digest):
    target = OUT / digest.replace(':', '_')
    if target.exists() and hashlib.file_digest(target.open('rb'), 'sha256').hexdigest() == digest[7:]:
        return target
    partial = target.with_suffix('.partial')
    check = hashlib.sha256()
    with urllib.request.urlopen(request('/blobs/' + digest), timeout=90) as response, partial.open('wb') as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
            check.update(chunk)
    if check.hexdigest() != digest[7:]:
        raise RuntimeError('Digest mismatch: ' + digest)
    partial.replace(target)
    return target

index, index_digest = manifest(TAG)
if 'manifests' in index:
    match = next(item for item in index['manifests']
                 if item.get('platform', {}).get('os') == 'linux'
                 and item['platform'].get('architecture') == 'amd64')
    image, digest = manifest(match['digest'])
    if digest != match['digest']:
        raise RuntimeError('Manifest digest mismatch')
else:
    image, digest = index, index_digest
size = sum(layer['size'] for layer in image['layers'])
if size > 2 * 1024 ** 3:
    raise RuntimeError('Image exceeds the reviewed 2 GiB download limit')
print(json.dumps({'image': 'ros:' + TAG, 'compressed_bytes': size,
                  'manifest_digest': digest}), flush=True)
config = blob(image['config']['digest']).read_bytes()
config_name = image['config']['digest'][7:] + '.json'
layers = []
for number, layer in enumerate(image['layers'], 1):
    print(f"Downloading verified layer {number}/{len(image['layers'])}: {layer['size']} bytes", flush=True)
    path = blob(layer['digest'])
    layers.append((layer, path))

archive_path = OUT / 'ros-jazzy-ros-base-noble.tar'
temporary = archive_path.with_suffix('.tar.partial')
def add_bytes(archive, name, body):
    header = tarfile.TarInfo(name)
    header.size = len(body)
    archive.addfile(header, io.BytesIO(body))

layer_names = []
with tarfile.open(temporary, 'w') as archive:
    add_bytes(archive, config_name, config)
    for layer, path in layers:
        name = layer['digest'][7:] + '/layer.tar'
        layer_names.append(name)
        header = tarfile.TarInfo(name)
        if layer['mediaType'].endswith('+gzip') or layer['mediaType'].endswith('.gzip'):
            with path.open('rb') as raw:
                raw.seek(-4, 2)
                header.size = struct.unpack('<I', raw.read(4))[0]
            with gzip.open(path, 'rb') as unpacked:
                archive.addfile(header, unpacked)
        elif layer['mediaType'].endswith('.tar'):
            header.size = path.stat().st_size
            with path.open('rb') as raw:
                archive.addfile(header, raw)
        else:
            raise RuntimeError('Unsupported layer media type: ' + layer['mediaType'])
    load_manifest = [{'Config': config_name, 'RepoTags': ['ros:' + TAG], 'Layers': layer_names}]
    add_bytes(archive, 'manifest.json', json.dumps(load_manifest).encode())
temporary.replace(archive_path)
lock = {'image': 'ros:' + TAG, 'platform': 'linux/amd64',
        'index_digest': index_digest, 'manifest_digest': digest,
        'config_digest': image['config']['digest'], 'compressed_bytes': size,
        'archive_bytes': archive_path.stat().st_size,
        'archive_sha256': hashlib.file_digest(archive_path.open('rb'), 'sha256').hexdigest(),
        'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'layers': image['layers']}
(ROOT / 'evidence' / 'ros_image.lock.json').write_text(json.dumps(lock, indent=2))
dockerfile = ROOT / 'Dockerfile'
if dockerfile.exists():
    lines = dockerfile.read_text().splitlines()
    lines[0] = 'FROM ros:' + TAG + '@' + digest
    dockerfile.write_text('\n'.join(lines) + '\n')
print(json.dumps({'download_complete': str(archive_path), **lock}), flush=True)
