# Phased Implementation Plan and Acceptance Criteria

Date: 2026-11-10. Phases 1–3 have been evaluated using virtual hardware. See the [Phase 2 report](phase2_detection.md) for 2D detection and the [Phase 3 report](phase3_depth.md) for camera-relative depth and position results.

## Phases and dependencies

| Phase | Work | Condition for the next step | Current status/boundary |
|---|---|---|---|
| 1 | Research established projects, select technologies, isolate the environment, pin versions, and run stationary RGB-D smoke checks | Sourced reports; working ROS/Gazebo; measured RGB/depth/intrinsics/scan/TF records | Complete |
| 2 | Reproducible human scenes, model selection/import, detection | Independent manual/ground-truth labels; single/multiple people and occlusion; model files and hashes | Baseline complete: 6 scenes, 360 frames; occlusion/crossing reliability insufficient |
| 3 | Robust depth localisation and synchronisation, with TF planned for downstream use | Pass position-error, invalid-depth, and timestamp-mismatch tests | Camera-frame benchmark complete. The 10 cm position goal remains open |
| 4 | ByteTrack baseline, 3D gating, appearance comparison, explicit target lock | No incorrect target takeover in crossings, occlusion, and reappearance tests | Depends on Phase 3 |
| 5 | Mock Navigation, Lifecycle, fault recovery | Timeouts, cancellation, restart, and backward clock jumps reliably withdraw tasks | No base motion output |
| 6 | rosbag replay, Nav2 logic, simulated low-speed following | Pass protection-chain, path, and stopping-response tests | Enter as a separate motion-testing phase |
| 7 | If physical hardware is introduced: version/calibration audit and DepthAI A/B tests | Accessible hardware and explicit authorisation | Currently NOT VERIFIED; no hardware purchase |

## Phase 1 environment

Install Docker on the host and use a digest-pinned ROS Jazzy/Ubuntu 24.04 base image. Resolve official simulation dependencies and budget disk space before building one image. Runtime uses `--network none`, drops capabilities, maps no USB devices, and limits CPU/memory. Nav2 packages may be present as simulation dependencies, but this phase neither activates navigation nor sends motion commands.

Download only the required base image and source pinned by SHA; do not preinstall training datasets, multiple models, or GPU environments. Save image, source, and package versions in evidence. apt repositories are not historical snapshots, so retain the built image rather than claiming future byte-identical rebuilds.

## Quantitative acceptance criteria (proposed, not measured results)

Initial thresholds reflect low-speed simulation debugging and processing budgets. Adjust them using subsequent data; they are not manufacturer specifications or safety standards.

| Category | Initial proposal | Rationale/measurement |
|---|---|---|
| Sensor path | Actual RGB, depth, CameraInfo, scan, clock, and TF messages; consistent dimensions/intrinsics | Stationary smoke check; topic names alone are insufficient |
| Camera rate | Record configured rate, wall-clock reception rate, sim-time rate, and real-time factor | VM rendering may be slow; Phase 1 does not guarantee 30FPS |
| Detection quality | Report precision, recall, and false positives by scene/distance; initial simple-scene recall ≥0.90 | Independent labels; at least 100 visible annotation instances; report sample size and confidence intervals |
| Inference throughput | Initial host detection target ≥10Hz | At 0.1m/s, travel in 100ms is 1cm; this does not establish system safety |
| Perception latency | Initial wall-clock P95 ≤200ms; also report P50/P99 | Measure acquisition, queueing, inference, depth, and publication together |
| RGB-D synchronisation | P95 timestamp difference ≤33ms; discard and count mismatches | Initial 30Hz frame period; redefine the window at lower frame rates |
| Simulated depth | At least 100 frames each of known planes at 1, 2, and 3m; report bias, standard deviation, and valid fraction | Gazebo truth; distinguish optical Z from Euclidean range; physical depth error remains NOT VERIFIED |
| 3D localisation | Proposed P95 position error ≤0.10m in ideal scenes at 1–3m | Include pixel selection, TF, and synchronisation rather than checking the formula alone |
| ID maintenance | Report IDF1/HOTA/ID switches; zero incorrect automatic target takeovers over 10 crossings | Small samples do not prove generalisation; stopping under ambiguity is allowed |
| Occlusion | Separate 0.5/1/3s occlusions; withdraw the target at timeout without automatically selecting another person | Distinguish internal track lifetime from control observation validity |
| Navigation | Initial simulated stand-off distance 1.5m, with root mean square error ≤0.30m | Conditional on future scenes and person speeds; no navigation measurements yet |
| Stopping response | Withdraw the control task within an additional 0.2s after observations become stale at 0.5s | Wall-clock fault injection and downstream velocity observation; not physical braking distance |
| Faults | Target loss, TF interruption, scan loss, communication loss, and clock pause stop target-driven control | Verify separately with Mock server and simulation |
| Resources | Record CPU, RSS, container memory, network, and disk; no sustained OOM | Test under current VM limits: 5 minutes first, then 30 minutes |

## Main risks and mitigations

- Software rendering competes for CPU: begin with a simple world and low resolution; report real-time factor rather than concealing poor wall-clock speed with sim-time FPS.
- Repository/documentation drift: retain SHAs and licences. Current yolo_ros has migrated to C++, so old Python interfaces cannot be copied directly.
- DepthAI version mixing: no physical driver is installed now; verify v2/v3, ROS distribution, and compiled model format before device integration.
- Human-asset domain differences: one artificial mesh may be poorly recognised by a general detector. Test multiple models, views, and lighting conditions, and evaluate real public data separately.
- Target identity ambiguity: target locking is independent of detection IDs. Stop under ambiguity rather than selecting the nearest person.
- Map/time jumps: invalidate the target, log the reason, and rebuild TF/tracking state.
- Disk space: initial dependencies were estimated at approximately 3.27GB. Retain image/source caches and record actual usage; do not clean unrelated services or data.

## Outstanding validation

Phase 3 measured camera-relative depth and position on the virtual benchmark. Base/map-frame localisation, identity stability, Nav2 following, long-duration operation, and physical robot performance still require independent experiments.
