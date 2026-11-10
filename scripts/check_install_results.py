"""Check newly captured installation results, including locally generated PNGs."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    sensor = json.loads((ROOT / 'evidence/sensor_smoke.json').read_text())
    if not sensor['pass'] or not all(sensor['checks'].values()):
        raise RuntimeError('Sensor smoke checks failed')
    settings = json.loads((ROOT / 'config/person_scenarios.json').read_text())
    cases = []
    verified_images = 0
    for case in settings['cases']:
        directory = ROOT / 'evidence/phase2' / case['id']
        result = json.loads((directory / 'summary.json').read_text())
        if not result['simulation_completed'] or result['prediction_coverage'] != 1:
            raise RuntimeError('Incomplete prediction coverage: ' + case['id'])
        if result['frames'] < settings['sensor_hz'] * settings['case_duration_sim_s'] * .9:
            raise RuntimeError('Too few paired frames: ' + case['id'])
        if result['motion_commands_sent'] or result['tracking_enabled']:
            raise RuntimeError('Validation must stay within detection-only scope')
        if case['id'] == 'single_front' and result['tp'] == 0:
            raise RuntimeError('Detector did not match the visible single person')
        for frame in json.loads((directory / 'frames.json').read_text()):
            with (ROOT / frame['image']).open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != frame['image_sha256']:
                raise RuntimeError('Captured image hash mismatch: ' + frame['image'])
            verified_images += 1
        cases.append({'case': case['id'], 'frames': result['frames'],
                      'prediction_coverage': result['prediction_coverage']})
    replay = json.loads((ROOT / 'evidence/phase2/offline_roundtrip.json').read_text())
    if replay['samples_requested'] != 120 or replay['timeouts'] != 0:
        raise RuntimeError('Offline ROS replay did not complete 120 images without timeouts')
    report = {'pass': True, 'runtime_uid': os.getuid(), 'runtime_gid': os.getgid(),
              'sensor_checks': len(sensor['checks']), 'cases': cases,
              'captured_image_hashes_verified': verified_images,
              'replay_samples': replay['samples_requested'], 'replay_timeouts': replay['timeouts'],
              'phase3_started': False}
    (ROOT / 'evidence/install_check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    check()
