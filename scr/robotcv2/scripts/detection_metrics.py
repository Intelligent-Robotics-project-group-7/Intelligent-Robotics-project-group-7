"""Confidence-ordered one-to-one matching for a fixed IoU operating point."""


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0., x2-x1) * max(0., y2-y1)
    area_a = max(0., a[2]-a[0]) * max(0., a[3]-a[1])
    area_b = max(0., b[2]-b[0]) * max(0., b[3]-b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.


def match_frame(ground_truth, predictions, threshold=0.5):
    unmatched = set(range(len(ground_truth)))
    matches, false_positives = [], []
    for index in sorted(range(len(predictions)), key=lambda i: predictions[i]['score'], reverse=True):
        best = max(unmatched, key=lambda j: iou(predictions[index]['box'], ground_truth[j]['box']), default=None)
        overlap = iou(predictions[index]['box'], ground_truth[best]['box']) if best is not None else 0.
        if best is not None and overlap >= threshold:
            unmatched.remove(best)
            matches.append({'prediction': index, 'ground_truth': best, 'iou': overlap})
        else:
            false_positives.append(index)
    return {'tp': len(matches), 'fp': len(false_positives), 'fn': len(unmatched),
            'matches': matches, 'false_positive_indices': false_positives,
            'missed_ground_truth_indices': sorted(unmatched)}


def summarize(rows):
    tp = sum(r['matching']['tp'] for r in rows)
    fp = sum(r['matching']['fp'] for r in rows)
    fn = sum(r['matching']['fn'] for r in rows)
    return {'frames': len(rows), 'ground_truth_instances': tp+fn,
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'negative_frames': sum(not r['ground_truth'] for r in rows),
            'negative_frames_with_false_positives': sum(not r['ground_truth'] and r['matching']['fp'] > 0 for r in rows)}
