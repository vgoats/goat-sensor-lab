# Ethics and Claims

## Welfare first

All animal work requires a written protocol, qualified husbandry oversight, and the approvals applicable to the site. Follow the principles of [ARRIVE 2.0](https://arriveguidelines.org/arrive-guidelines), PREPARE, and relevant national/institutional animal ethics requirements.

- Use the least intrusive mount and shortest session that answers the research question.
- Review mass, balance, pressure, breakaway behavior, horn/wool interaction, heat, abrasion, chewing, entanglement, and ingress hazards before animal use.
- Inspect fit and skin/ear/neck before, during, and after sessions.
- Define immediate removal criteria: distress, injury, altered gait, persistent scratching, entanglement, device heat, loose/damaged enclosure, or abnormal behavior plausibly caused by the device.
- Never reduce required human checks because a sensor is present.
- Do not induce sickness, feed deprivation, or distress merely to improve classifier balance.

## Temperature

Rectal temperature is a common clinical reference for core temperature in goats and sheep. Ear-tag, collar, skin, ambient, and IMU temperatures are affected by environment, contact, hair/wool, blood flow, and electronics. They may support trend research only after comparison with a clinical reference; they are not interchangeable with core temperature.

## Permitted and prohibited wording

| Evidence stage | Permitted | Prohibited |
|---|---|---|
| Recorder only | “Captures raw IMU data and human labels” | Any behavior or health accuracy claim |
| Internal behavior validation | “Research estimate of feeding/rumination/posture on held-out animals in this study” | “Works for all goats/sheep” |
| Baseline deviation study | “Flags a behavior deviation for review” | “Detects sickness” or “diagnoses disease” |
| Reproduction research | “Experimental association with observed estrus/parturition labels” | “Detects pregnancy,” “guarantees breeding time,” or unattended birth assurance |
| External prospective validation | Exact population, environment, endpoint, metric, confidence interval, and limitations | Broad claims beyond the validated population and workflow |

Pregnancy requires an appropriate reproductive examination/test. Disease requires clinical assessment. Estrus, kidding, and lambing alerts must be prospectively validated and must not replace observation or assistance protocols.

## Data and privacy

- Pseudonymize animal and worker identities in research exports.
- Protect the RFID-to-research-ID mapping separately.
- Minimize camera views of people; obtain required consent and define retention.
- Disable audio by default; obtain specific approval before recording it.
- Log data access, model version, alert generation, and human disposition for auditability.

## Model safety

Every result must include the model/version, source/mount, confidence or uncertainty, data-quality state, and the validated use context. Low-quality or out-of-distribution input should yield “unknown/review,” not a confident label. Monitor false negatives and false positives by animal, species, mount, shed, subgroup, and time since deployment.
