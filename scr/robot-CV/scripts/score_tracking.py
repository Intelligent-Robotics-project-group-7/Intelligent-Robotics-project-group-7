"""Score tracked boxes against independent visible-person masks."""
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

from detection_metrics import match_frame
from person_tracking import ByteTracker, TargetLock, observations_from_frame


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'downloads/phase4'


def tracking_pairs(truth, tracks):
    predictions = [{'box': track['bbox'], 'score': track['score']} for track in tracks]
    pairs = match_frame(truth, predictions, .50)['matches']
    return {tracks[pair['prediction']]['track_id']: truth[pair['ground_truth']]['label'] for pair in pairs}


def score(rows, expected_label):
    last_ids = {}
    identity_matches = Counter()
    truth_count = track_count = switches = 0
    states, outcome, reasons = Counter(), Counter(), Counter()
    wrong_outputs = []
    gaps = []
    first_selected = gap_start = None
    last_safe = None
    recoveries = []
    for row in rows:
        frame, truth, stamp = row.get('frame'), row['truth'], row['stamp_ns']
        truth_count += len(truth)
        if frame is None:
            continue
        tracks = [track for track in frame['tracks'] if track['confirmed']]
        track_count += len(tracks)
        pairs = tracking_pairs(truth, tracks)
        for track_id, label in pairs.items():
            if label in last_ids and last_ids[label] != track_id:
                switches += 1
            last_ids[label] = track_id
            identity_matches[label, track_id] += 1
        if frame['selected_id'] is None:
            continue
        if first_selected is None:
            first_selected = stamp
        states[frame['state']] += 1
        reasons[frame['reason']] += 1
        target = frame['target']
        if target is None:
            if gap_start is None:
                gap_start = stamp
            outcome['withheld'] += 1
            continue
        label = pairs.get(target['track_id'])
        if label is None:
            outcome['unverified_output'] += 1
            wrong_outputs.append({'stamp_ns': stamp, 'track_id': target['track_id'], 'matched_label': None})
        elif label != expected_label:
            outcome['wrong_person'] += 1
            wrong_outputs.append({'stamp_ns': stamp, 'track_id': target['track_id'], 'matched_label': label})
        else:
            outcome['correct_person'] += 1
            if gap_start is not None:
                gaps.append(round((stamp - gap_start) / 1e9, 3))
                if last_safe is not None:
                    recoveries.append(round((stamp - last_safe) / 1e9, 3))
                gap_start = None
            last_safe = stamp
    labels = sorted({key[0] for key in identity_matches})
    tracks = sorted({key[1] for key in identity_matches})
    counts = np.array([[identity_matches[label, track] for track in tracks] for label in labels])
    idtp = 0
    if counts.size:
        a, b = linear_sum_assignment(counts, maximize=True)
        idtp = int(np.sum(counts[a, b]))
    return {'frames': len(rows), 'truth_instances': truth_count, 'confirmed_track_boxes': track_count,
            'identity_switches': switches, 'idf1_at_iou_50': 2 * idtp / (truth_count + track_count)
            if truth_count + track_count else None, 'first_selection_ns': first_selected,
            'states': dict(states), 'reasons': dict(reasons), 'target_outcomes': dict(outcome),
            'wrong_or_unverified_outputs': wrong_outputs,
            'completed_withhold_periods_s': gaps, 'recovery_from_last_correct_s': recoveries,
            'still_withheld_at_end': gap_start is not None}


def select_by_side(visible, side):
    tracks = [track for track in visible.values() if track.hits >= 2]
    if len(tracks) < (2 if side == 'right' else 1):
        return None
    if len(tracks) > 1:
        tracks.sort(key=lambda track: track.observation.box[0] + track.observation.box[2])
    return tracks[-1 if side == 'right' else 0]


def replay(source, use_depth, side, selection_ns=2_200_000_000, drop=None, require_two=False):
    tracker, lock = ByteTracker(use_depth), TargetLock(use_depth)
    result = []
    for row in source:
        stamp = row['stamp_ns']
        if row['boxes'] is None:
            result.append(dict(row, frame=None))
            continue
        depth = row['depth'] if row['frame'] and row['frame']['depth_paired'] else None
        observations = observations_from_frame(row['boxes'], depth)
        # Controlled loss of one detector's observation after the initial selection.
        if drop and drop[0] <= stamp < drop[1]:
            observations = [obs for obs in observations if obs.index != drop[2].get(stamp)]
        visible = tracker.update(observations, stamp)
        lock.update(stamp, visible, tracker.tracks, observations)
        if lock.state == 'IDLE' and selection_ns <= stamp <= 4_000_000_000:
            confirmed = sum(track.hits >= 2 for track in visible.values())
            chosen = select_by_side(visible, side) if not require_two or confirmed >= 2 else None
            if chosen:
                lock.select(lock.session, chosen.id, visible, stamp, observations)
        tracks = [{'track_id': track.id, 'bbox': list(track.observation.box),
                   'score': track.observation.score, 'confirmed': track.hits >= 2} for track in visible.values()]
        result.append(dict(row, frame={'tracks': tracks, **lock.report(visible)}))
    return result


def load(case):
    return json.loads((CAPTURE / case / 'frames.json').read_text())


def main():
    cases = ('two_crossing', 'partial_occlusion', 'torso_occlusion', 'exit_return')
    runs = [load(case) for case in cases]
    comparison = {}
    for case, run in zip(cases, runs, strict=True):
        source = run['rows']
        comparison[case] = {'live': score(source, run['selected_label']),
                            '2d_replay': score(replay(source, False, 'left', require_two=case == 'two_crossing'),
                                               run['selected_label']),
                            'depth_replay': score(replay(source, True, 'left', require_two=case == 'two_crossing'),
                                                  run['selected_label']),
                            'graph': run['graph']}
    crossing = runs[0]['rows']
    variants, early_dropouts = [], []
    # Detector dropout is scripted in evaluation only. Truth labels identify which box to remove.
    for side, label in (('left', runs[0]['selected_label']), ('right', runs[0]['other_label'])):
        indices = {}
        for row in crossing:
            boxes = row['boxes'] or []
            matches = match_frame(row['truth'], [{'box': box['bbox'], 'score': box['score']} for box in boxes], .50)
            for pair in matches['matches']:
                if row['truth'][pair['ground_truth']]['label'] == label:
                    indices[row['stamp_ns']] = pair['prediction']
        for start, duration in ((6.0, 0.0), (6.0, .5), (6.0, 1.0), (6.4, 1.0), (6.0, 3.0)):
            drop = (round(start * 1e9), round((start + duration) * 1e9), indices)
            scored = score(replay(crossing, True, side, drop=drop, require_two=True), label)
            variants.append({'side': side, 'selected_label': label, 'drop_start_s': start,
                             'drop_duration_s': duration, **scored})
        for use_depth in (False, True):
            scored = score(replay(crossing, use_depth, side, drop=(4_000_000_000, 4_400_000_000, indices),
                                  require_two=True), label)
            early_dropouts.append({'side': side, 'use_depth': use_depth, 'drop_start_s': 4.0,
                                   'drop_duration_s': .4, **scored})
    report = {'recorded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'cases': comparison, 'controlled_crossing_replays': variants,
              'pre_crossing_dropout_replays': early_dropouts}
    (CAPTURE / 'tracking_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    for case, values in comparison.items():
        print(case, values['live']['target_outcomes'], values['live']['states'])
    if any(row['first_selection_ns'] is None for row in variants):
        raise RuntimeError('Some crossing variants failed to make an initial selection')
    measured_runs = [values['live'] for values in comparison.values()] + variants + early_dropouts
    if any(row['wrong_or_unverified_outputs'] for row in measured_runs):
        raise RuntimeError('Wrong or unverified target output in the live or controlled replay runs')


if __name__ == '__main__':
    main()
