# Annotation Tooling and Responsibility Boundary

## Decision

Goat Sensor Lab requires a defined video-annotation workflow for research data collection and
validation. It does not require The Observer XT, and annotation software is not part of the
finished wearable or shed runtime.

The default Goat Sensor Lab workflow is:

- use **BORIS** for independent human coding of behavior intervals from synchronized video;
- preserve the original annotation project and raw export;
- transform the accepted export into the canonical append-only
  [`annotations-v1.csv`](../../schema/annotations-v1.schema.json) contract;
- produce consensus separately under
  [`annotation-consensus-v1`](../../schema/annotation-consensus-v1.schema.json);
- record the tool name, exact version, media digest, clock mapping, ethogram version, rater, and
  review history.

The canonical annotation and consensus contracts are authoritative for the sensor experiment.
The database or project format of BORIS, CVAT, The Observer, VIA, or another interface is not the
research contract.

The repository does not yet contain a BORIS-to-`annotations-v1.csv` importer. Until that converter
and its tests exist, an experiment must register the exact conversion procedure and validate the
resulting intervals, identities, clocks, and digests before research training. Tool selection is
documented; automated import is pending implementation.

## What the indoor-goat paper actually did

The [Mauny et al. indoor-goat dataset paper](https://doi.org/10.1016/j.anopes.2025.100095)
and its [ACT4Behav companion study](https://doi.org/10.24072/pcjournal.545) used this workflow:

1. Eight indoor Alpine dairy goats wore triaxial accelerometers attached to their RFID ear tags.
2. The sensors recorded the three acceleration axes at 5 Hz for 24 consecutive hours.
3. A camera above each pen recorded the animals. Each goat had a visible number applied to its
   back so the observer could distinguish animals in the footage.
4. The researchers created a visible synchronization event by vigorously moving the sensor in
   front of the camera. The resulting shake pattern was the reference event used to align video
   and accelerometer time.
5. **One human observer** watched the daylight video and manually coded behavior for approximately
   11 hours per goat using a predefined ethogram.
6. The human used **The Observer XT version 16** to record animal, behavior, onset, and offset.
   The Observer XT was an interface for playing video and logging events; it was not an AI model.
7. The behavior intervals were aligned with the sensor timestamps. The released rows therefore
   contain `TIME`, `ACCx`, `ACCy`, `ACCz`, and simultaneous feeding, position, social, other, and
   disturbance behavior fields.
8. The companion study calculated features over accelerometer windows and trained **four separate
   CatBoost binary classifiers**: ruminating, head in feeder, lying, and standing.

The video frames were not inputs to CatBoost. Human labels derived from the video supplied the
target answers associated with accelerometer windows:

```text
human watches synchronized video
    -> human records behavior start and stop
    -> behavior interval is aligned to accelerometer timestamps
    -> CatBoost learns accelerometer patterns associated with that human label
```

The time-window split reported AUC values of 0.800, 0.819, 0.829, and 0.823 for rumination,
head-in-feeder, lying, and standing. When training used six goats and testing used two different
goats, the corresponding AUC values fell to 0.644, 0.733, 0.741, and 0.749. The result supports
video-labelled sensor research but also demonstrates that a small same-animal dataset can
overstate generalization.

This evidence does **not** demonstrate automatic camera recognition. It contains no video object
detector, pose model, visual tracker, or video behavior classifier. It also relies on one observer,
so it does not provide independent-rater agreement evidence.

## What The Observer XT is

The Observer XT is commercial behavioral-coding software from Noldus. A user loads a recording,
selects a subject and behavior, and records the start and end of the observed event. It combines a
media player, event log, configurable behavior list, synchronized data views, and analysis/export
functions.

Version 16 was used by the Mauny study. As of 2026-08-02, the public Noldus trial page supplies
The Observer XT 17 as a Windows `.exe` installer and does not provide a native macOS installer.
The current trial is time-limited and the full product is commercially licensed. These platform
and licensing properties make it a reproducibility reference, not a Goat Sensor Lab dependency.

Official references:

- [The Observer animal-research product page](https://noldus.com/observer-animal)
- [The Observer XT trial download](https://noldus.com/download/latest/the-observer-xt)
- [Noldus sample lesson showing behavior setup](https://academy.noldus.com/courses/trial-lessons/lessons/the-observer-onboarding-training-sample-lesson/topics/behaviors-in-the-observer-xt/)

## Tool roles

| Tool | Suitable role | Project decision |
|---|---|---|
| [BORIS](https://www.boris.unito.it/) | Human coding of state intervals and point events from video; export for later conversion | Default Goat Sensor Lab behavior-annotation reference; pinned locally in the reference manifest |
| [The Observer XT](https://noldus.com/observer-animal) | Commercial event coding and synchronized-media analysis; exact tool used by the Mauny study | Not required and not selected as a dependency |
| [VIA Video Annotator](https://www.robots.ox.ac.uk/~vgg/software/via/via.html) | Lightweight browser-based spatial regions and temporal segments | Acceptable fallback for a small controlled task if its export is transformed and governed identically |
| [CVAT](https://www.cvat.ai/) | Video boxes, tracks, skeletons, masks, review, and AI-assisted spatial annotation | Relevant to Herdlink camera datasets; not the Goat Sensor Lab wearable-label contract |
| [DeepLabCut labeling GUI](https://deeplabcut.github.io/DeepLabCut/docs/beginner-guides/labeling.html) | Multi-animal body-keypoint labels used to train a pose model | Relevant to Herdlink's selected pose pipeline; not a replacement for sensor behavior intervals |

The tools serve different tasks. Repository popularity is not evidence that a tool matches the
ethogram, identity, review, synchronization, or export requirements.

The official BORIS macOS build was marked experimental at version 9.13.0 and uses a separate media
window rather than embedding video in the main application. Pilot the exact export path, keep
frequent backups, and use VIA as the controlled fallback if the registered Mac workflow is not
stable enough. CVAT is browser-based, but its official documentation supports Google Chrome
rather than Safari.

## Goat Sensor Lab and Herdlink boundary

[Herdlink](https://github.com/vgoats/herdlink) owns fixed-camera detection, pose, temporary visual
tracks, RFID-backed permanent identity, camera hand-off, occlusion boundaries, and
identity-qualified shed behavior events. Goat Sensor Lab owns wearable IMU recording, sensor/video
clock alignment, independent behavior annotations, consensus, and sensor-model evaluation.

The repositories must not create competing camera-identity systems:

- Goat Sensor Lab may consume an identity-qualified video interval from Herdlink as supporting
  evidence.
- A visible study marker and session RFID record may establish identity in a controlled sensor
  experiment.
- When a group video does not establish which animal produced the behavior, the Goat Sensor Lab
  annotation must remain `UNKNOWN` or invalid. It must not assign identity by elimination.
- CVAT and DeepLabCut dataset decisions for camera tracking belong in Herdlink and must be recorded
  there before camera-model implementation.

## Human annotation procedure

A trained observer is a person who has learned the written ethogram and passed an agreement check
on shared example footage. It is not a model.

For each selected animal and video:

1. Open the immutable video in the registered annotation tool.
2. Select the pseudonymous animal ID established by the study identity procedure.
3. Play, pause, rewind, or advance frame by frame as required.
4. Record the onset and exclusive offset for each independent label head in the
   [ethogram](ethogram.md). Feeding and posture can overlap and must not be forced into one class.
5. Mark insufficient visibility as `UNKNOWN`; record technical failures as invalid data.
6. Export the rater track without editing or deleting prior published annotations.
7. Convert it to `annotations-v1.csv`, retaining the original tool project and export by digest.
8. Have a second blinded human independently annotate the registered overlap sample. The pilot
   requires at least 20% double annotation.
9. Measure agreement per label head and adjudicate disagreements without overwriting either
   original rater track.
10. Freeze a versioned consensus artifact before model training or final evaluation.

The Android live-label buttons remain field notes and a synchronization aid. They do not replace
post-session independent video annotation.

## AI-assisted annotation boundary

Initial training and final evaluation labels require human observation independent of model
predictions. Showing a model's prediction to the primary rater can copy model errors into the
supposed ground truth.

After the initial human-labelled dataset and evaluation set are frozen, AI may help prioritize
unlabelled operational footage. Humans can then review low-confidence events, disagreements,
alerts, and a registered random audit sample instead of watching every future hour. AI-generated
or AI-assisted labels must remain distinguishable from independent primary ground truth and must
never be used to score the same model as if they were human reference labels.

## Pilot with approximately ten animals

A group of approximately ten animals in one controlled shed section is suitable for an engineering
pilot of camera coverage, visible identity, synchronization, annotation throughput, and sensor
mounting. Use normal husbandry, two complementary camera views where occlusion matters, visible
study identifiers linked to RFID/session records, and synchronized wearable recordings.

That pilot does not establish production accuracy for a substantially larger or more crowded
group. Model claims still require the registered cohort, animal-held-out evaluation, multiple
days and conditions, independent raters, and later testing under the intended shed density.
