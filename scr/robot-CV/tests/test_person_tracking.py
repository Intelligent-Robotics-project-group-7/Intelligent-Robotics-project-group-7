import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from person_tracking import ByteTracker, Observation, TargetLock


def obs(index, left, depth, score=.9):
    return Observation((left, 20, left+30, 80), score, index,
                       (0., 0., depth) if depth is not None else None)


def frame(tracker, lock, t, boxes):
    stamp = round(t * 1e9)
    visible = tracker.update(boxes, stamp)
    lock.update(stamp, visible, tracker.tracks, boxes)
    return visible, stamp


def test_low_confidence_can_extend_a_track_but_cannot_create_one():
    tracker = ByteTracker()
    assert not tracker.update([obs(0, 30, 3, .15)], 0)
    assert set(tracker.update([obs(0, 30, 3)], 200_000_000)) == {1}
    assert set(tracker.update([obs(0, 30, 3)], 400_000_000)) == {1}
    assert set(tracker.update([obs(0, 32, 3, .15), obs(1, 90, 4, .15)], 600_000_000)) == {1}


def test_depth_gate_blocks_assignment_of_a_different_distance_in_the_same_box():
    with_depth, baseline = ByteTracker(True), ByteTracker(False)
    for tracker in (with_depth, baseline):
        tracker.update([obs(0, 30, 3)], 0)
    assert set(with_depth.update([obs(0, 30, 4)], 200_000_000)) == {2}
    assert set(baseline.update([obs(0, 30, 4)], 200_000_000)) == {1}


def test_lock_recovers_only_the_original_id_with_consistent_depth():
    tracker, lock = ByteTracker(), TargetLock()
    frame(tracker, lock, 0, [obs(0, 20, 3)])
    boxes = [obs(0, 22, 3)]
    visible, stamp = frame(tracker, lock, .2, boxes)
    assert not lock.select('another-session', 1, visible, stamp, boxes)
    assert lock.select(lock.session, 1, visible, stamp, boxes)
    visible, _ = frame(tracker, lock, .4, [obs(0, 24, 4)])
    assert lock.state == 'OCCLUDED' and lock.report(visible)['target'] is None
    visible, _ = frame(tracker, lock, .6, [obs(0, 26, 3)])
    assert lock.state == 'LOCKED' and lock.report(visible)['target']['track_id'] == 1


def test_after_timeout_returning_target_stays_lost_until_operator_selects():
    tracker, lock = ByteTracker(), TargetLock()
    frame(tracker, lock, 0, [obs(0, 20, 3)])
    boxes = [obs(0, 20, 3)]
    visible, stamp = frame(tracker, lock, .2, boxes)
    assert lock.select(lock.session, 1, visible, stamp, boxes)
    frame(tracker, lock, .4, [obs(0, 60, 4)])
    visible, stamp = frame(tracker, lock, 1.2, boxes)
    assert lock.state == 'LOST' and lock.report(visible)['target'] is None
    assert lock.select(lock.session, 1, visible, stamp, boxes)
    lock.expire()
    assert lock.state == 'LOST'
