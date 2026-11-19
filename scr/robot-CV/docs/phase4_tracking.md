# Phase 4 Person Tracking and Target Lock

Validation date 2026-11-18. The tracker assigns session-local IDs to YOLO person detections. An explicit operator selection pins one ID and gates the target output independently of the tracker. The benchmark uses Gazebo and a stationary TurtleBot 4.

## Tracker and selection

The project implements a compact ByteTrack-style baseline using constant-velocity Kalman prediction and two passes of one-to-one IoU association. High-confidence boxes at 0.25 and above can start tracks. Boxes scoring 0.10 to below 0.25 can extend recently observed tracks after the high-confidence pass. Two observations confirm a track. The Phase 4 launch enables the lower threshold to supply both passes. [ByteTrack paper](https://arxiv.org/abs/2110.06864)

Depth-assisted association uses the Phase 3 torso-region estimates. The tracker waits up to 150 ms of wall time for depth with the same image timestamp and optical frame. A depth estimate needs a valid status and support from at least 45% of the region. When both a track and candidate have usable depth, the gate checks camera-relative X and Z. At a 0.2 s interval the limits are 0.45 m laterally and 0.38 m in forward depth. Bounds increase with elapsed time to allow movement. Continuous tracking can use 2D boxes when depth is unavailable.

The output starts in `IDLE`. A request with the current session ID and a confirmed track ID can enter `LOCKED`. A missing box, overlapping candidates, or a depth conflict moves the selected target to `OCCLUDED` and clears the target output. Within 0.8 s of the last accepted observation, depth-assisted mode can recover the same track after separation when fresh depth agrees with the pre-gap position. After that interval, `LOST` latches until an operator makes another selection. A 1.25 s wall-clock input watchdog also withdraws stale targets. Track prediction can survive up to 1.2 s internally.

The system uses box motion and optional RGB-D position. Appearance embeddings, moving-camera tracking and physical-camera validation remain outside the evidence from these tests.

## Evaluation method

The evaluator sends a single successful initial selection through the ROS selection topic, choosing the leftmost eligible track from observed boxes. In the crossing scene it waits for two confirmed tracks. The semantic label subscriber is confined to the evaluator. After capture, the labels determine the intended person and score tracked boxes at IoU ≥ 0.50. A target output with no matched semantic box is counted as unverified.

The report counts ID changes relative to a person's previous matched ID, even across a gap. It also reports IDF1 from the per-frame IoU assignments and the global one-to-one assignment between track IDs and semantic labels. These values are for the simulator's visible-pixel boxes. Recovery latency is measured from the last verified target output before a gap to the next verified output.

The offline comparison reuses the captured inputs for both modes. The ten controlled crossing replays reuse one captured crossing sequence and vary the selected side and lengths of simulated detector dropout. Simulator labels identify which detection to remove in those stress trials and are only used by the evaluator. The variants do not supply identity labels to the tracker. Partial runs and raw frame captures are written to `downloads/phase4/`.

## Gazebo results

YOLO26s ran on CPU in the existing Jazzy/Harmonic simulation container. The camera produced five frames per simulated second. All four scenarios yielded 60 scored timestamps. Counts of correct and withheld target frames start after selection. The evaluator confirmed that it was the only semantic-label subscriber and observed no velocity topics in all four runs.

| Live scenario | Correct target frames | Withheld frames | Wrong or unverified outputs | Tracker ID changes | IDF1 at IoU 0.50 | Result |
|---|---:|---:|---:|---:|---:|---|
| Two people crossing | 22 | 36 | 0 | 1 | 75.7% | Withheld on overlap, then latched lost |
| Partial occlusion | 12 | 46 | 0 | 1 | 51.9% | One 0.6 s recovery, then latched lost during the longer gap |
| Torso occlusion | 58 | 0 | 0 | 0 | 100.0% | The detector and lock kept the original person |
| Exit and return | 12 | 46 | 0 | 1 | 56.8% | Latched lost, with explicit selection required on return |
| **Overall** | **104** | **128** | **0** | **3** | | Eight frames preceded selection |

During the live crossing, the lock first withheld output at 6.8 simulated seconds and reached `LOST` at 7.6 s. The selected person's internal tracker ID changed from 1 to 3 at 8.2 s. The lock stayed lost when the person reappeared. The four low-confidence track outputs in the live partial-occlusion scene exercised the detector's lower-confidence path.

| Same-frame replay | 2D correct / withheld | Depth-assisted correct / withheld | 2D / depth tracker ID changes |
|---|---:|---:|---:|
| Two people crossing | 23 / 36 | 23 / 36 | 1 / 1 |
| Partial occlusion | 11 / 48 | 13 / 46 | 1 / 1 |
| Torso occlusion | 59 / 0 | 59 / 0 | 0 / 0 |
| Exit and return | 13 / 46 | 13 / 46 | 1 / 1 |

Depth-assisted mode recovered the original lock after 0.6 s in the partial-occlusion replay. The separate pre-crossing dropout test removed 0.4 s of detections. Depth-assisted mode recovered after 0.6 s for both starting targets. The 2D-only lock stayed withheld under its conservative recovery policy. Both modes had the same tracking ID-change count in the four ordinary replays.

The ten controlled crossing replays produced zero wrong or unverified target outputs. Both 0.5 s dropout variants briefly recovered at an interval of 0.8 s from the last correct output. All ten ultimately withheld the target during the crossing or following loss. These are variations of one scene captured with one synthetic mesh duplicated for the two people. They measure the lock's behaviour under those inputs and leave sustained identity through prolonged overlap unresolved.

## Reproduction

```bash
bash scripts/setup_person_models.sh yolo26s
TB4_MODEL=yolo26s bash scripts/run_tracking_suite.sh
bash scripts/run_env.sh python3 scripts/score_tracking.py
bash scripts/run_env.sh python3 -m pytest -q tests
```

The four capture files and their simulation logs live under `downloads/phase4/CASE/`. The scorer writes `downloads/phase4/tracking_report.json`. Thirteen tests passed, including the four new tests for tracking and target-lock transitions. A separate ROS probe verified successful explicit selection followed by an input timeout that latched `LOST` and cleared the published target. The default Phase 2 single-front regression still matched 60 of 60 annotations with zero false positives and full detection-message coverage.

The archived validation includes the live results, controlled replays, and all 240 scored frames. [Results](../evidence/phase4/tracking_report.json) · [Frame records](../evidence/phase4/frame_records.jsonl.gz) · [Capture log](../evidence/phase4/suite.log)

See the recorded checks for the tracking logic, ROS input timeout, and default detection workflow. [Unit tests](../evidence/phase4/unit_tests.log) · [ROS probe](../evidence/phase4/ros_probe.log) · [Phase 2 regression](../evidence/phase4/phase2_regression.log)
