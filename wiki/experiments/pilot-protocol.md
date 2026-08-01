# Pilot Protocol

This is a protocol template, not approval to begin animal work. Freeze a completed copy, analysis
plan, ethogram, and experiment-manifest template before enrollment. Register the protocol in a
timestamped institutional or public repository when permitted, and record all deviations. The
design follows the reporting fields in [ARRIVE 2.0](https://arriveguidelines.org/arrive-guidelines)
and the planning topics in [PREPARE](https://norecopa.no/prepare); site ethics and veterinary
requirements remain authoritative.

## Research questions

1. Can ear- or neck-mounted XIAO IMU data distinguish feeding, rumination, lying, standing, and active movement in indoor goats and sheep?
2. How much accuracy is lost on animals excluded from training?
3. Does mount, shed, day, breed/size, or device materially change performance?
4. Can deviations from an individual's established behavior baseline produce useful review alerts without being presented as diagnoses?

## Staged sample plan

| Stage | Suggested scope | Purpose |
|---|---|---|
| Engineering | 6–8 animals per species, short supervised sessions | Mount safety, orientation, BLE loss, timing, label usability |
| Model pilot | At least 24 animals per species, at least 6 annotated hours per animal across 3 non-consecutive days | Animal-independent behavior models and variance estimates |
| Stronger internal validation | 30–40+ animals per species across pens, age/size groups, and days | Stable class and subgroup estimates |
| External validation | New shed/farm, unseen animals and operators | Generalization and claim boundary |

These are planning targets, not a statistical power calculation. Final sample size must follow expected prevalence, effect size, clustering, and the primary endpoint.

## Registration lock

Before enrollment, complete and freeze these fields in the protocol and
[`experiment-manifest-v1`](../../schema/experiment-manifest-v1.schema.json):

| Field | Required decision |
|---|---|
| Experimental unit | Individual animal; identify repeated sessions and pen/farm clustering |
| Primary endpoint | Default behavior pilot: animal-held-out macro-F1 across the prespecified non-`UNKNOWN`, valid classes of the ingestive and posture/activity heads, with a 95% animal-bootstrap CI; replace only before registration |
| Secondary endpoints | Per-head/class precision, recall and F1; balanced accuracy; agreement; packet loss; invalid time; mount adverse events |
| Target population | Species, breed/size, sex, age/life stage, health, housing, ration, farm/site and eligible placement |
| Sample-size method | Simulation or analytical method using expected class prevalence, animal/session clustering, minimally useful endpoint and precision; archive code, assumptions and seed |
| Allocation | Device, placement/order, session time and operator allocation method, including blocking factors and random seed |
| Analysis plan | Immutable train/validation/test animal IDs, feature/window definitions, exclusions, estimand, missing-data rules, uncertainty and multiplicity decisions |
| Governance | Ethics approvals, owner/site permissions, protocol version, registration URI/date, data retention and adverse-event contacts |

If a field is unknown or not applicable, record that state and its reason rather than omitting it.
The suggested stage sizes above must never be reported as powered merely because they were met.

## Eligibility and exclusions

- Register animal inclusion criteria for species, age/life stage, body mass/mount fit, housing,
  health examination, and ability to habituate safely.
- Register animal exclusions before outcomes are inspected: veterinary/welfare removal, inability to
  fit safely, withdrawal of permission, or pre-existing condition outside the target population.
- Register session exclusions: failed immutable export, unusable clock mapping, missing required
  video, sensor/mount failure above the declared threshold, or insufficient visible annotation.
- Register interval exclusions: handling, mount adjustment, sensor reset, occlusion, failed sync,
  ambiguous identity, or other ethogram-defined invalidity.
- Report every enrolled animal and session in an attrition flow with reason. Technical failure is
  not permission to delete inconvenient animals or labels after seeing model errors.

## Habituation, allocation, blinding, and counterbalance

- Pre-specify a welfare-approved fit check and habituation period for each mount. Record duration,
  acceptance criteria, skin/ear/neck findings, and behavior relative to the animal's ordinary
  husbandry. Exclude acclimatisation data from the primary endpoint unless registered otherwise.
- Randomize devices across eligible animals and block by important factors such as species, pen,
  sex/life stage, breed/size, and day where feasible. Record the generator, seed, and allocation.
- In paired ear-versus-neck work, counterbalance mount order, device, time of day, feed cycle, and
  operator; define washout/habituation between conditions. Do not pool placements by convenience.
- Raters are blinded to model predictions, test membership, and the other independent rater's
  labels until tracks freeze. Model developers remain blinded to final-test consensus until the
  pipeline and thresholds are locked. Record every blinding breach.

## Capture configuration

- XIAO nRF52840 Sense at 25/26 Hz, raw accelerometer and gyroscope.
- Start with approximately ±4 g and ±500 degrees/second if supported and confirm clipping empirically.
- Record exact mount, orientation, enclosure, firmware, device, animal, pen, and session.
- Use overhead and feeder-side 1080p video at 25/30 fps where possible.
- Capture normal husbandry; do not induce illness merely to create labels.
- Collect phone data only for engineering comparison, not for final animal-model training.
- Record all required-or-explicitly-unknown fields in the experiment manifest, including animal
  sex/age/breed/body mass/life stage, ration, treatment/health context, enclosure mass/orientation,
  calibration status, firmware/app revisions, site and camera clocks.

## Session procedure

1. Confirm eligibility, animal identity, allocation, habituation acceptance, device identity and
   protocol version without consulting future outcome labels.
2. Inspect the animal and attachment; record pre-existing clinical concerns in the approved system.
3. Start cameras and recorder, then perform the synchronization gesture.
4. Observe a session likely to contain feeding, post-feeding rumination, standing, lying, and movement.
5. Record feed delivery, handling, occlusion, mount changes, and other events.
6. Repeat synchronization during long recordings and before stop.
7. Inspect skin/ear/neck and device after removal; record adverse events.
8. Export immediately, hash/archive the raw package, and complete the experiment manifest before
   the next session.

## Stopping and humane endpoints

Stop and remove the device immediately for injury, persistent distress, entanglement risk, impaired
feeding/drinking/movement, skin/ear/neck damage, unsafe temperature, attachment failure, or a
veterinary/husbandry instruction. Pre-register quantitative technical stops for repeated resets,
unacceptable packet loss, failed clock anchors, or unusable video. Care takes precedence over data;
stopped animals receive the site's normal assessment and treatment. Record the stop, reason,
treatment, recovery, and whether replacement enrollment was permitted by the frozen protocol.

## Analysis design

- Decide train/validation/test animals before overlapping window creation.
- Use leave-one-animal-out or grouped cross-validation during development; reserve a final unseen-animal test set.
- Keep all windows from an animal/session in one partition.
- Compare simple interpretable baselines first: orientation, vector magnitude, spectral/temporal features, and tree ensembles.
- Evaluate sequence models only after the baseline and leakage checks are stable.
- Report macro-F1 and balanced accuracy, plus per-class precision, recall, F1, confusion matrices, and confidence intervals bootstrapped by animal.
- Report packet loss, invalid time, label coverage, mount failures, and achieved sample rate alongside model scores.
- Use append-only independent rater tracks and a frozen consensus materialization; the app's live
  label columns are not the primary reference labels.
- Keep species, source, placement, farm/site, protocol, firmware, enclosure, and calibration domains
  explicit. Pool them only under a registered domain-generalization analysis.
- For any clinical endpoint, use the separate
  [`clinical-outcomes-v1`](../../schema/clinical-outcomes-v1.schema.json) reference table and freeze
  prediction windows before unblinding outcomes.

The 2025 indoor-goat study reported lower AUC when testing goats absent from training (rumination 0.644, head-in-feeder 0.733, lying 0.741, standing 0.749), demonstrating why animal-independent evaluation is mandatory: [paper](https://doi.org/10.24072/pcjournal.545).

## Advancement criteria

Do not advance a behavior to product trials until performance is acceptable on unseen animals, errors are reviewed by subgroup and context, model uncertainty is exposed, and a rollback/monitoring plan exists. Do not advance health, pregnancy, estrus, lambing, or kidding claims from behavior correlation alone.
