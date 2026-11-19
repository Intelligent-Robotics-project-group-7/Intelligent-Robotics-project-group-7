"""Two-pass ByteTrack association and explicit target selection for a static camera."""
from dataclasses import dataclass
import math
from uuid import uuid4

import numpy as np
from scipy.optimize import linear_sum_assignment

from detection_metrics import iou


LOW_SCORE = 0.10
HIGH_SCORE = 0.25
TRACK_BUFFER_S = 1.2
TARGET_GRACE_S = 0.8
MIN_DEPTH_SUPPORT = 0.45
AMBIGUOUS_IOU = 0.22


@dataclass(frozen=True)
class Observation:
    box: tuple
    score: float
    index: int
    optical_xyz: tuple | None = None


def measurement(box):
    x1, y1, x2, y2 = box
    return np.array([(x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1], dtype=float)


class Track:
    def __init__(self, track_id, observation, stamp_ns):
        self.id = track_id
        self.mean = np.r_[measurement(observation.box), np.zeros(4)]
        self.covariance = np.diag([16., 16., 25., 25., 225., 225., 225., 225.])
        self.stamp_ns = self.last_seen_ns = stamp_ns
        self.observation = observation
        self.optical_xyz = observation.optical_xyz
        self.depth_stamp_ns = stamp_ns
        self.hits = 1

    def predict(self, stamp_ns):
        dt = (stamp_ns - self.stamp_ns) / 1e9
        motion = np.eye(8)
        motion[:4, 4:] = np.eye(4) * dt
        self.mean = motion @ self.mean
        self.covariance = motion @ self.covariance @ motion.T + np.diag(
            [4., 4., 4., 4., 36., 36., 36., 36.]) * dt
        self.stamp_ns = stamp_ns

    @property
    def predicted_box(self):
        x, y, w, h = self.mean[:4]
        w, h = max(w, 1.), max(h, 1.)
        return x-w/2, y-h/2, x+w/2, y+h/2

    def update(self, observation, stamp_ns):
        innovation = self.covariance[:4, :4] + np.eye(4) * 4
        gain = np.linalg.solve(innovation, self.covariance[:4, :]).T
        self.mean += gain @ (measurement(observation.box) - self.mean[:4])
        self.covariance -= gain @ self.covariance[:4, :]
        self.observation = observation
        self.last_seen_ns = stamp_ns
        self.hits += 1
        if observation.optical_xyz is not None:
            self.optical_xyz = observation.optical_xyz
            self.depth_stamp_ns = stamp_ns


def compatible_depth(reference, observed, elapsed):
    # Camera-relative X and Z. Vertical changes from torso sampling are common.
    x_limit = 0.25 + 1.0 * elapsed
    z_limit = 0.32 + 0.30 * elapsed
    return abs(reference[0] - observed[0]) <= x_limit and abs(reference[2] - observed[2]) <= z_limit


class ByteTracker:
    """ByteTrack-style high-score association followed by low-score recovery."""

    def __init__(self, use_depth=True):
        self.use_depth = use_depth
        self.tracks = {}
        self.next_id = 1

    def associate(self, tracks, observations, stamp_ns, min_iou):
        if not tracks or not observations:
            return [], tracks, observations
        invalid = 1e6
        costs = np.full((len(tracks), len(observations)), invalid)
        for i, track in enumerate(tracks):
            for j, obs in enumerate(observations):
                overlap = iou(track.predicted_box, obs.box)
                if overlap < min_iou:
                    continue
                age = (stamp_ns - track.depth_stamp_ns) / 1e9
                depth_available = (self.use_depth and track.optical_xyz is not None
                                   and obs.optical_xyz is not None and age <= TRACK_BUFFER_S)
                if depth_available and not compatible_depth(track.optical_xyz, obs.optical_xyz, age):
                    continue
                costs[i, j] = 1 - overlap
        rows, columns = linear_sum_assignment(costs)
        pairs = [(i, j) for i, j in zip(rows, columns) if costs[i, j] < invalid]
        used_i, used_j = {i for i, _ in pairs}, {j for _, j in pairs}
        return ([(tracks[i], observations[j]) for i, j in pairs],
                [track for i, track in enumerate(tracks) if i not in used_i],
                [obs for j, obs in enumerate(observations) if j not in used_j])

    def update(self, observations, stamp_ns):
        active = [track for track in self.tracks.values()
                  if (stamp_ns - track.last_seen_ns) / 1e9 <= TRACK_BUFFER_S]
        self.tracks = {track.id: track for track in active}
        for track in active:
            track.predict(stamp_ns)
        high = [obs for obs in observations if obs.score >= HIGH_SCORE]
        low = [obs for obs in observations if LOW_SCORE <= obs.score < HIGH_SCORE]
        matches, unmatched, new = self.associate(active, high, stamp_ns, .20)
        recent = [track for track in unmatched if track.hits >= 2
                  and (stamp_ns - track.last_seen_ns) / 1e9 <= .45]
        recovery, _, _ = self.associate(recent, low, stamp_ns, .35)
        observed = {}
        for track, obs in matches + recovery:
            track.update(obs, stamp_ns)
            observed[track.id] = track
        for obs in new:
            track = Track(self.next_id, obs, stamp_ns)
            self.next_id += 1
            self.tracks[track.id] = track
            observed[track.id] = track
        return observed


class TargetLock:
    """Keep the operator's track ID and stop exposing a target on uncertainty."""

    def __init__(self, use_depth=True):
        self.use_depth = use_depth
        self.session = uuid4().hex
        self.track_id = None
        self.state = 'IDLE'
        self.reason = 'awaiting_selection'
        self.last_good_ns = None
        self.anchor = None

    def select(self, session, track_id, visible, stamp_ns, observations):
        if session != self.session or type(track_id) is not int:
            return False
        if track_id not in visible or visible[track_id].hits < 2:
            return False
        track = visible[track_id]
        if track.observation.score < HIGH_SCORE or any(
                obs.index != track.observation.index and iou(obs.box, track.observation.box) >= AMBIGUOUS_IOU
                for obs in observations):
            return False
        self.track_id = track_id
        self.last_good_ns = stamp_ns
        self.anchor = track.observation.optical_xyz
        self.state, self.reason = 'LOCKED', 'operator_selected'
        return True

    def clear(self):
        self.track_id = None
        self.state, self.reason = 'IDLE', 'operator_cleared'
        self.last_good_ns = self.anchor = None

    def expire(self):
        if self.state in ('LOCKED', 'OCCLUDED'):
            self.state, self.reason = 'LOST', 'input_timeout'

    def update(self, stamp_ns, visible, tracks, observations):
        if self.state in ('IDLE', 'LOST'):
            return
        age = (stamp_ns - self.last_good_ns) / 1e9
        if age > TARGET_GRACE_S:
            self.state, self.reason = 'LOST', 'target_timeout'
            return
        track = visible.get(self.track_id)
        reason = 'missing_detection'
        if track is not None:
            obs = track.observation
            overlap = any(other.index != obs.index and iou(obs.box, other.box) >= AMBIGUOUS_IOU
                          for other in observations)
            overlap |= any(other.id != track.id and other.id not in visible and other.hits >= 2
                           and (stamp_ns - other.last_seen_ns) / 1e9 <= TARGET_GRACE_S
                           and iou(obs.box, other.predicted_box) >= AMBIGUOUS_IOU for other in tracks.values())
            comparable = self.use_depth and self.anchor is not None and obs.optical_xyz is not None
            depth_ok = comparable and compatible_depth(self.anchor, obs.optical_xyz, age)
            if overlap:
                reason = 'overlapping_candidates'
            elif comparable and not depth_ok:
                reason = 'inconsistent_depth'
            elif self.state == 'OCCLUDED' and not depth_ok:
                reason = 'recovery_needs_consistent_depth'
            else:
                self.reason = 'recovered' if self.state == 'OCCLUDED' else 'observed'
                self.state = 'LOCKED'
                self.last_good_ns = stamp_ns
                # Recovery requires recent, consecutive depth evidence.
                self.anchor = obs.optical_xyz
                return
        self.state, self.reason = 'OCCLUDED', reason

    def report(self, visible):
        target = visible.get(self.track_id) if self.state == 'LOCKED' else None
        obs = target.observation if target else None
        return {'session_id': self.session, 'selected_id': self.track_id,
                'state': self.state, 'reason': self.reason,
                'target': {'track_id': target.id, 'bbox': list(obs.box), 'detection_index': obs.index,
                           'optical_xyz_m': obs.optical_xyz} if target else None}


def observations_from_frame(boxes, depth):
    points = {}
    if depth and depth.get('status') == 'paired':
        for estimate in depth['estimates']:
            if estimate['status'] != 'valid' or estimate.get('support_fraction', 0) < MIN_DEPTH_SUPPORT:
                continue
            point = estimate['xyz_m']
            if len(point) == 3 and all(math.isfinite(value) for value in point) and point[2] > 0:
                points[estimate['detection_index']] = tuple(point)
    return [Observation(tuple(item['bbox']), item['score'], index, points.get(index))
            for index, item in enumerate(boxes)]
