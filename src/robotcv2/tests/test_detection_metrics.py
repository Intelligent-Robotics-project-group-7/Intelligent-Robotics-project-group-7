import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from detection_metrics import iou, match_frame, summarize


def box(coords, score=1.):
    return {'box': coords, 'score': score}


def test_duplicate_predictions_cannot_claim_two_true_positives():
    result = match_frame([box([0, 0, 10, 10])], [box([0, 0, 10, 10], .9), box([0, 0, 10, 10], .8)])
    assert (result['tp'], result['fp'], result['fn']) == (1, 1, 0)


def test_empty_predictions_count_visible_person_as_missed():
    result = match_frame([box([0, 0, 10, 10]), box([20, 20, 30, 30])], [])
    assert (result['tp'], result['fp'], result['fn']) == (0, 0, 2)


def test_false_positive_on_negative_frame_is_not_discarded():
    result = match_frame([], [box([0, 0, 10, 10])])
    summary = summarize([{'ground_truth': [], 'matching': result}])
    assert summary['fp'] == summary['negative_frames_with_false_positives'] == 1
    assert summary['recall'] is None


def test_iou_and_threshold_boundary():
    assert iou([0, 0, 10, 10], [5, 0, 15, 10]) == 1/3
    assert iou([0, 0, 0, 10], [0, 0, 0, 10]) == 0
    result = match_frame([box([0, 0, 10, 10])], [box([0, 0, 5, 10])], threshold=.5)
    assert result['tp'] == 1
