"""Aggregate all preregistered cases; missing/failed cases abort reporting."""
import json
from pathlib import Path
import cv2
import numpy as np
from detection_metrics import summarize

ROOT = Path(__file__).resolve().parents[1]
settings = json.loads((ROOT / 'config/person_scenarios.json').read_text())
rows, summaries, samples = [], [], []
for case in settings['cases']:
    directory = ROOT / 'evidence/phase2' / case['id']
    summary = json.loads((directory / 'summary.json').read_text())
    if not summary['simulation_completed']:
        raise RuntimeError('Incomplete case: '+case['id'])
    if summary['frames'] < int(settings['sensor_hz']*settings['case_duration_sim_s']*.9):
        raise RuntimeError('Insufficient paired RGB/truth frames: '+case['id'])
    if case['actors'] and summary['ground_truth_instances'] == 0:
        raise RuntimeError('Configured people have no visible annotations: '+case['id'])
    summaries.append(summary)
    rows.extend(json.loads((directory / 'frames.json').read_text()))
    files = sorted(directory.glob('example_*.png'))
    for image in (files[0], files[len(files)//2]):
        sample = cv2.imread(str(image))
        samples.append(cv2.copyMakeBorder(sample,2,2,2,2,cv2.BORDER_CONSTANT,value=(20,20,20)))
report = {'overall':summarize(rows), 'cases':summaries,
          'limitations':['Synthetic OpenRobotics Scrubs mesh only; no real-world validation',
                         'Temporally correlated rendered frames; not independent people',
                         'No depth localization, identity tracking or robot following evaluated']}
hog_rows = []
for file in sorted((ROOT / 'evidence/phase2').glob('*/hog_frames.json')):
    hog_rows.extend(json.loads(file.read_text()))
if hog_rows:
    report['hog_baseline_overall'] = summarize(hog_rows)
    baseline_path = ROOT / 'evidence/phase2/hog_baseline.json'
    baseline = json.loads(baseline_path.read_text())
    baseline['overall'] = report['hog_baseline_overall']
    baseline_path.write_text(json.dumps(baseline,indent=2)+'\n')
# Conditional uncertainty on these scenes, preserving short-range frame dependence.
rng = np.random.default_rng(20261110)
case_blocks = []
for case in settings['cases']:
    source = json.loads((ROOT / 'evidence/phase2' / case['id'] / 'frames.json').read_text())
    blocks = {}
    for row in source:
        key = row['stamp_ns']//1_000_000_000
        blocks.setdefault(key, np.zeros(2))
        blocks[key] += [row['matching']['tp'], row['matching']['fn']]
    case_blocks.append(np.stack(list(blocks.values())))
replicates = []
for _ in range(2000):
    totals = sum((block[rng.integers(0,len(block),len(block))].sum(axis=0) for block in case_blocks), np.zeros(2))
    replicates.append(totals[0]/totals.sum())
report['recall_uncertainty'] = {
    'method':'stratified within-scene non-overlapping 1-second block bootstrap',
    'replicates':2000, 'seed':20261110,
    'percentile_95_interval':[float(np.percentile(replicates,2.5)),float(np.percentile(replicates,97.5))],
    'scope':'conditional on these six scenes and one mesh; does not estimate new-person or real-world generalization'}
(ROOT / 'evidence/phase2/detection_report.json').write_text(json.dumps(report,indent=2)+'\n')
contact = np.vstack([np.hstack(samples[i:i+3]) for i in range(0,len(samples),3)])
cv2.imwrite(str(ROOT / 'evidence/phase2/detection_contact_sheet.png'), contact)
print(json.dumps(report['overall'],indent=2))
