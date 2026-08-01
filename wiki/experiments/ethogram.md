# Ethogram

The ethogram uses simultaneous label heads because ingestive behavior and posture can coexist. Annotators label only directly observable states; model interpretation comes later.

## Ingestive behavior

| Label | Operational definition | Exclusions |
|---|---|---|
| `FEEDING` | Muzzle in or immediately over feeder/feed, with active acquisition or chewing of newly consumed feed | Rumination away from feed; investigating an empty feeder without ingestion |
| `RUMINATION` | Cud regurgitation/re-chewing cycle with repeated jaw movements, typically separated from feed acquisition | Ordinary mastication during feeding; licking or grooming |
| `NEITHER` | Clearly visible and neither feeding nor ruminating | Use `UNKNOWN` when visibility is insufficient |
| `UNKNOWN` | Ingestive state cannot be determined | Do not guess from posture alone |

## Posture and activity

| Label | Operational definition | Boundary rule |
|---|---|---|
| `LYING` | Trunk supported by floor/bedding | May coexist with rumination |
| `STANDING` | Weight borne on limbs without sustained displacement | Small head movement does not make it active movement |
| `ACTIVE_MOVEMENT` | Sustained walking, running, climbing, or clear whole-body displacement | Record transitions at the observed boundary |
| `UNKNOWN` | Posture/activity cannot be determined | Use during occlusion or ambiguous transitions |

## Welfare observation

| Label | Operational definition | Authority |
|---|---|---|
| `NORMAL` | No study-defined abnormality observed during the interval | Observation only, not proof of health |
| `SUSPECTED_ABNORMAL_INACTIVITY` | Unusual inactivity or reduced feeding relative to the study definition/baseline | Triggers review; not a diagnosis |
| `UNKNOWN` | Welfare state not assessed or not observable | Default when no qualified assessment exists |

Clinical confirmation is not an observable behavior label. Store it only in the separate
[`clinical-outcomes-v1.csv`](../../schema/clinical-outcomes-v1.schema.json) contract, assigned by
the registered reference standard and linked to a pre-specified prediction window. The sensor,
live observer, and consensus-materialization process cannot create a clinical diagnosis.

## Data validity

Set `invalid_data=true` for loose/rotated mount, handling, charging, sensor reset, camera occlusion, time-sync failure, or an annotator unable to establish ground truth. Keep the most plausible behavior label if useful, but exclude invalid intervals from primary model training.

## Additional event annotations

Record as timestamped events rather than forced behavior classes: drinking, grooming, scratching, fighting/social contact, urination/defecation, coughing/vocalization, human handling, feed delivery, medication, weighing, mount adjustment, and synchronization gesture.

Rumination's biological definition and the need for explicit behavior definitions are consistent with the [systematic review of sheep rumination sensors](https://pmc.ncbi.nlm.nih.gov/articles/PMC10740880/) and the [indoor-goat ear-accelerometer study](https://doi.org/10.24072/pcjournal.545).
