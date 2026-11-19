"""Run a classical detector on the identical saved RGB frames as a CPU control."""
import json
from pathlib import Path
import time
import cv2
import numpy as np
from detection_metrics import match_frame, summarize

ROOT = Path(__file__).resolve().parents[1]
cv2.setNumThreads(2)
detector = cv2.HOGDescriptor()
detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
results, latencies, all_rows = {}, [], []
for path in sorted((ROOT / 'evidence/phase2').glob('*/frames.json')):
    rows = json.loads(path.read_text())
    baseline = []
    for row in rows:
        image = cv2.imread(str(ROOT / row['image']))
        if image is None:
            raise RuntimeError('Missing benchmark RGB frame: ' + row['image'])
        image = cv2.resize(image, (640, 480))
        started = time.perf_counter()
        rectangles, weights = detector.detectMultiScale(image, hitThreshold=.25, winStride=(8,8), padding=(8,8), scale=1.05)
        duration = (time.perf_counter()-started)*1000
        latencies.append(duration)
        predictions = [{'box': [float(x/2), float(y/2), float((x+w)/2), float((y+h)/2)], 'score': float(score)}
                       for (x,y,w,h),score in zip(rectangles,weights)]
        baseline.append({'stamp_ns': row['stamp_ns'], 'ground_truth': row['ground_truth'],
                         'predictions': predictions, 'inference_ms': duration,
                         'matching': match_frame(row['ground_truth'], predictions, .5)})
    (path.parent / 'hog_frames.json').write_text(json.dumps(baseline, indent=2) + '\n')
    results[path.parent.name] = summarize(baseline)
    all_rows.extend(baseline)
report = {'method': 'OpenCV default HOG people detector, 640x480 input, two CPU threads',
          'scope': 'offline detector call; excludes rendering, capture, ROS and image resize',
          'cases': results, 'overall': summarize(all_rows),
          'inference': {'p50_ms':float(np.percentile(latencies,50)), 'p95_ms':float(np.percentile(latencies,95))}}
(ROOT / 'evidence/phase2/hog_baseline.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
