# Video Synchronization and Annotation

The complete tool decision, the exact Mauny/ACT4Behav human-labeling workflow, and the boundary
between Goat Sensor Lab and Herdlink are documented in
[Annotation tooling and responsibility boundary](annotation-tooling.md).

## Camera layout

Use at least one overhead camera covering posture and movement and one feeder-side camera showing muzzle/jaw/feed interaction. Keep clocks, camera IDs, pen layout, frame rate, resolution, and dropped-frame behavior in session metadata. Avoid relying on painted identifiers as the sole identity method after washing or prolonged housing; use a visible durable study marker plus RFID/session records.

## Synchronization

The authoritative sensor clock is monotonic time. At session start and end, create a visible and inertially sharp synchronization event near the mounted sensor, such as three distinct taps or a controlled device movement while the animal is not wearing it. For long sessions, repeat every 30–60 minutes.

1. Record the synchronization event in `events.csv`.
2. Locate the matching peaks in raw acceleration/gyroscope and video frames.
3. Fit a clock offset, and drift correction when multiple anchors exist.
4. Store the mapping and residual error as derived metadata.
5. Target residual synchronization error below 100 ms for jaw/head behavior work; report achieved error rather than assuming it.

BLE notification arrival time is not the XIAO sample time. Use board sequence numbers and time anchors, then map board uptime to phone monotonic time.

## Annotation workflow

- Train annotators using the [ethogram](ethogram.md) and a shared example set.
- Annotate each label head independently; never force one flat class.
- Mark occlusion/uncertainty as `UNKNOWN` and technical failure as invalid.
- Store every rater track in append-only
  [`annotations-v1.csv`](../../schema/annotations-v1.schema.json), including media position,
  versioned clock mapping, ethogram/tool versions, confidence, visibility, and revisions.
- Keep source video and annotation projects immutable and bind them by digest in the experiment
  manifest. Bind the versioned sensor-to-media clock-mapping artifact by URI and SHA-256 as well.
  BORIS is the default open-source reference for Goat Sensor Lab event logging and media coding
  ([project](https://github.com/olivierfriard/BORIS),
  [methods paper](https://doi.org/10.1111/2041-210X.12584)); record the exact version used.
- Register a minimum double-annotation fraction (at least 20% for the pilot) and keep raters blinded
  to model output and to one another until tracks freeze. The analysis gate recomputes
  duration-weighted coverage from active accepted revisions; it does not trust a declared percent.
- Compute per-head agreement, including Cohen's kappa or an appropriate time-series agreement measure; target at least 0.80 before freezing labels.
- Adjudicate disagreements without deleting or rewriting original annotations.
- Generate a separate
  [`annotation-consensus-v1`](../../schema/annotation-consensus-v1.schema.json) artifact citing the
  source annotation IDs, input digest, resolution rule, ethogram, and code/manual method version.

The label state captured live by the Android recorder is an operator aid and synchronization/field
QA trace. It is not double annotation and must not be treated as frozen research ground truth.

## Leakage controls

Do not annotate by looking at model predictions for the primary ground truth. Do not tune boundaries on final-test animals. Preprocessing windows must stop at label transitions and invalid intervals or explicitly use a documented transition policy.

## Privacy and retention

Position cameras to minimize staff/public capture, post signage and obtain required consent, restrict raw video access, and define retention/deletion dates. Microphone recording on the wearable remains disabled unless separately approved and justified.
