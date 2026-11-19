import concurrent.futures
import datetime
import json
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path('/home/john/projects/turtlebot4_person_following')
OUT = ROOT / 'evidence' / 'sources'
OUT.mkdir(parents=True, exist_ok=True)
REPOS = [
    'turtlebot/turtlebot4_simulator', 'turtlebot/turtlebot4_examples',
    'luxonis/depthai-ros', 'mgonzs13/yolo_ros',
    'spencer-project/spencer_people_tracking', 'ros-navigation/navigation2',
    'ifzhang/ByteTrack', 'NirAharon/BoT-SORT', 'nwojke/deep_sort',
]

def get(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'TurtleBot4-Research/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read()
    return body if binary else json.loads(body)

def collect(repo):
    info = get('https://api.github.com/repos/' + repo)
    branch = info['default_branch']
    commit = get('https://api.github.com/repos/' + repo + '/commits/' + branch)
    sha = commit['sha']
    result = {key: info.get(key) for key in (
        'full_name', 'html_url', 'default_branch', 'archived', 'disabled',
        'pushed_at', 'updated_at', 'license', 'description')}
    result.update(commit_sha=sha, commit_date=commit['commit']['committer']['date'],
                  commit_subject=commit['commit']['message'].splitlines()[0])
    prefix = repo.replace('/', '__')
    for filename in ('README.md', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'):
        url = f'https://raw.githubusercontent.com/{repo}/{sha}/{filename}'
        try:
            body = get(url, binary=True)
            (OUT / f'{prefix}__{filename}').write_bytes(body)
            result.setdefault('downloaded_files', []).append({'name': filename, 'url': url})
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    (OUT / f'{prefix}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
    return result

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    jobs = {pool.submit(collect, repo): repo for repo in REPOS}
    for job in concurrent.futures.as_completed(jobs):
        try:
            results.append(job.result())
        except Exception as exc:
            results.append({'full_name': jobs[job], 'error': str(exc)})
            print(json.dumps(results[-1]), flush=True)
(OUT.parent / 'repository_inventory.json').write_text(
    json.dumps({'collected_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'repositories': results}, indent=2), encoding='utf-8')
