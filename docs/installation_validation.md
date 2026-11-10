# Clean Installation Validation

Date: 2026-11-10. Result: **PASS for the documented x86_64 Ubuntu container workflow, covering Phases 1–2 only.** Phase 3 was not started.

## What changed

The host bootstrap now selects the account invoking sudo, or accepts an explicit existing account through `--user`. It no longer assumes a username or home directory. The Docker wrappers derive the checkout path from the scripts, match the caller's numeric UID/GID, use a writable temporary home, and detect whether a terminal is available. A fixed internal `/workspace` mount is independent of the host clone location.

`install.sh` builds the environment and perception overlay. `verify_install.sh` runs the sensor/detection checks and verifies freshly generated image hashes and replay results. Asset downloads run with container Python, use temporary files and retries, verify immutable inputs, and preserve the committed input lock. The English README includes clone authentication, host setup, first login, installation, verification, resources, and troubleshooting.

## Clean test setup and boundaries

- A freshly pulled Ubuntu 24.04 client container on the existing Ubuntu 26.04.1 VMware host.
- A new account named `replica`, UID/GID 2001. The account exists only in the disposable client; no new host account was created.
- A fresh Git clone in a directory named `robot CV`, testing a path containing a space.
- No original project downloads, generated image dataset, or ROS build/install/log directories.
- `bash scripts/install.sh --no-cache --pull`, using a separate image tag. Application layers were rebuilt, apt dependencies downloaded/installed, model/assets fetched and checked, and all five ROS packages compiled.
- The existing host Docker daemon and immutable ROS base-image layers were reused. `--pull` refreshed the pinned manifest. The disposable client accessed that daemon through its socket; its supplemental socket group was supplied by the test fixture.

This was **not a newly provisioned VM or newly started Docker daemon**. Package installation and bootstrap account handling were exercised in the fresh client, but its lack of systemd means the systemd daemon-start branch was not exercised there. The README requires a working local Docker daemon and describes session renewal and daemon startup.

## Source access

Anonymous HTTPS cloning in the clean client failed because GitHub required authentication. The clean test therefore cloned candidate commit `0d4fe9299708bbc5a70a140089c9689ca058c428` from a Git bundle without transferring the operator's credentials. This is a fresh Git checkout of the candidate source, not a copy of the original installed workspace.

Readers must use their own GitHub account with repository access, through configured HTTPS credentials or SSH. Credentials are not included in the project. The validation summary records hashes of every tested script, launch/configuration file, and Dockerfile; the final documentation update preserves those tested files.

## Executed checks

| Check | Result |
|---|---|
| Bootstrap with implicit sudo account and explicit `--user replica` | PASS |
| Repeated bootstrap; missing, nonexistent, and unprivileged-account invocations | Expected success/failure behaviour |
| Shell syntax and Python compilation in the fresh clone | PASS |
| Fresh application image build, model/asset checksums, five ROS package builds | PASS |
| Scoring tests | 4 passed |
| Stationary RGB-D, lidar, clock, intrinsics, and camera TF checks | 9 passed |
| All six detection scenes | 60 paired frames each; 360 total |
| Prediction-message coverage | 100% in every scene |
| Newly generated image hashes | All 360 verified |
| ROS replay without Gazebo | 120 images; 0 timeouts |
| Non-default UID/GID, writable home, and output ownership | PASS: UID/GID 2001 |
| Invocation from outside the checkout, with no TTY | PASS |
| Tracked scripts, launch files, and input locks unchanged by installation | PASS |

The new run reproduced TP=252, FP=0, FN=70 across 322 visible annotations, giving recall 78.26%. This confirms installation and execution of the fixed synthetic baseline, not reliable following or real-world generalisation. Message coverage is distinct from detection recall. Crossing and occlusion limitations remain as described in the [Phase 2 report](phase2_detection.md).

Validated image ID: `sha256:8f1c73a331276d26a47c0cd7c738ea59edbd439bb6fc0f903c486d27d54d4d7c`.

## Evidence and reproduction

- [Validation summary, results, image ID, and tested source hashes](../evidence/installation/validation_summary.json)
- [Complete clean build, compilation, sensor, scene, and analysis log](../evidence/installation/clean_run.log)
- [Fresh-client bootstrap log](../evidence/installation/bootstrap.log)
- [Bootstrap account/error/idempotence checks](../evidence/installation/bootstrap_checks.log)
- [Path, ownership, terminal, and configuration-preservation checks](../evidence/installation/portability.log)
- [Anonymous clone failure](../evidence/installation/anonymous_clone.log)

Follow the [README](../README.md) using your own authorised clone. Run `bash scripts/install.sh`, then `bash scripts/verify_install.sh`. To rebuild application layers without cache and refresh the base manifest, pass `--no-cache --pull` to the installer. Later apt repository changes or upstream dependency-tag changes can affect rebuilds; the project does not claim byte-identical images on arbitrary future dates.

No depth-based person localisation, identity tracking, Nav2, following, or robot motion was enabled by this validation. Physical OAK-D and VPU performance remain **NOT VERIFIED**.
