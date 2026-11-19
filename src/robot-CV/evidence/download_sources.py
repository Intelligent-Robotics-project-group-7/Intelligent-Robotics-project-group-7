import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path('/home/john/projects/turtlebot4_person_following')
inventory = json.loads((ROOT / 'evidence/repository_inventory.json').read_text())
by_name = {x['full_name']: x for x in inventory['repositories']}
items = [
    ('turtlebot/turtlebot4_simulator', by_name['turtlebot/turtlebot4_simulator']['commit_sha']),
    ('mgonzs13/yolo_ros', by_name['mgonzs13/yolo_ros']['commit_sha']),
]
headers = {'User-Agent': 'TurtleBot4-Research/1.0'}
url = 'https://api.github.com/repos/ros-navigation/navigation2/commits/jazzy'
with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as r:
    commit = json.load(r)
items.append(('ros-navigation/navigation2', commit['sha']))
records = []
for repo, sha in items:
    url = f'https://codeload.github.com/{repo}/tar.gz/{sha}'
    target = ROOT / 'downloads' / (repo.replace('/', '__') + '-' + sha[:12] + '.tar.gz')
    if not target.exists():
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as r, target.open('wb') as w:
            while chunk := r.read(1024 * 1024):
                w.write(chunk)
    record = {'repository': repo, 'commit': sha, 'source_url': url,
              'file': str(target.relative_to(ROOT)), 'bytes': target.stat().st_size,
              'sha256': hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()}
    records.append(record)
    print(json.dumps(record), flush=True)
(ROOT / 'evidence/source_downloads.lock.json').write_text(json.dumps(records, indent=2))

# Read version-sensitive files from authoritative branches, without executing them.
paths = [
 ('luxonis/depthai-ros', 'humble', 'depthai_ros_driver/package.xml'),
 ('luxonis/depthai-ros', 'jazzy', 'depthai_ros_driver/package.xml'),
 ('turtlebot/turtlebot4_robot', 'jazzy', 'turtlebot4_bringup/config/oakd_pro.yaml'),
 ('turtlebot/turtlebot4_robot', 'jazzy', 'turtlebot4_bringup/launch/oakd.launch.py'),
 ('ros-navigation/navigation2', 'jazzy', 'nav2_following/opennav_following/package.xml'),
 ('ros-navigation/navigation2', 'jazzy', 'nav2_msgs/action/FollowObject.action'),
]
for repo, ref, path in paths:
    url = f'https://raw.githubusercontent.com/{repo}/{ref}/{path}'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=35) as r:
            data = r.read()
        dest = ROOT / 'evidence/sources' / (repo.replace('/', '__') + '__' + ref + '__' + path.replace('/', '__'))
        dest.write_bytes(data)
        print(json.dumps({'source': url, 'downloaded': str(dest)}), flush=True)
    except Exception as exc:
        print(json.dumps({'source': url, 'NOT_VERIFIED': str(exc)}), flush=True)
