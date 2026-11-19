"""Fetch immutable perception inputs; store large files outside Git and record hashes."""
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.error
import zipfile
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'downloads/phase2'
DEST.mkdir(parents=True, exist_ok=True)
HF_REV = 'e046fc5125ee6b579f1801f0b6df68a60b949c42'
SPECS = [
    ('models/yolo26n.onnx', f'https://huggingface.co/unileon-robotics/YOLO26-ONNX/resolve/{HF_REV}/yolo26n.onnx', 'AGPL-3.0'),
    ('model_card.md', f'https://huggingface.co/unileon-robotics/YOLO26-ONNX/raw/{HF_REV}/README.md', 'AGPL-3.0'),
    ('source/yolo_ros.tar.gz', 'https://codeload.github.com/mgonzs13/yolo_ros/tar.gz/94d2dd500cb26027ee9c019f4d3a02029ac615cc', 'MIT'),
    ('scrubs.zip', 'https://fuel.gazebosim.org/1.0/OpenRobotics/models/Scrubs/2/Scrubs.zip', 'CC-BY-4.0'),
    ('scrubs_metadata.json', 'https://fuel.gazebosim.org/1.0/OpenRobotics/models/Scrubs', 'CC-BY-4.0'),
]
lock_path = ROOT / 'config/phase2_assets.lock.json'
previous = json.loads(lock_path.read_text()) if lock_path.exists() else {'files': []}
expected = {x['path']: x['sha256'] for x in previous['files']}
records = []
for rel, url, license_id in SPECS:
    target = DEST / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_name(target.name + '.part')
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'TurtleBot4-Perception-Research/1.0'})
                with urllib.request.urlopen(req, timeout=90) as response, temporary.open('wb') as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                temporary.replace(target)
                break
            except (OSError, urllib.error.URLError):
                temporary.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
    with target.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    path = target.relative_to(ROOT).as_posix()
    immutable = rel != 'scrubs_metadata.json'
    if immutable and path in expected and expected[path] != digest:
        raise RuntimeError('Input digest mismatch: ' + path)
    record = {'path': path, 'url': url, 'bytes': target.stat().st_size, 'sha256': digest,
              'license': license_id, 'immutable_artifact': immutable}
    records.append(record)
    print(json.dumps(record), flush=True)

scrubs_dir = DEST / 'Scrubs'
scrubs_dir.mkdir(exist_ok=True)
with zipfile.ZipFile(DEST / 'scrubs.zip') as archive:
    if any(not (scrubs_dir / item.filename).resolve().is_relative_to(scrubs_dir.resolve()) for item in archive.infolist()):
        raise RuntimeError('Unsafe Scrubs archive path')
    archive.extractall(scrubs_dir)
source_dir = ROOT / 'research_ws/src/yolo_ros'
source_dir.mkdir(parents=True, exist_ok=True)
with tarfile.open(DEST / 'source/yolo_ros.tar.gz', 'r:gz') as archive:
    members = []
    for item in archive.getmembers():
        parts = Path(item.name).parts[1:]
        if not parts:
            continue
        item.name = str(Path(*parts))
        target = source_dir / item.name
        if item.isfile() and target.exists():
            if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(archive.extractfile(item).read()).digest():
                raise RuntimeError('Existing upstream source differs; preserving edits: ' + str(target))
        members.append(item)
    archive.extractall(source_dir, members=members, filter='data')
# Preserve the committed lock; changing live metadata must not rewrite pinned inputs.
(DEST / 'assets.actual.json').write_text(json.dumps({'model_repository_revision': HF_REV,
                                'person_asset': 'OpenRobotics/Scrubs', 'person_asset_version': 2,
                                'files': records}, indent=2) + '\n')
print('Person asset files: ' + ', '.join(str(p.relative_to(scrubs_dir)) for p in scrubs_dir.rglob('*') if p.is_file())[:2200])
