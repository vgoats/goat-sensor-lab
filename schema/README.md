# Canonical Research Schemas

[`samples-v1.schema.json`](samples-v1.schema.json) is the canonical, machine-readable contract
for the 25-column `samples.csv` export. Android and Python implementations must conform to it;
this file defines column order, CSV type, nullability, units, enums, and value constraints.

The JSON is intentionally independent of either runtime. Runtime validators may enforce the
contract, but they must not silently redefine it. Before the first public release, version 1 was
finalized with `source_uptime_ms` as its 11th column so the XIAO clock anchor remains auditable.
After publication, any incompatible CSV change requires a new schema version and migration plan.

Validate the contract from the repository root:

```bash
python3 tools/verify_samples_schema.py
```

The verifier uses only the Python standard library and exits non-zero for malformed, incomplete,
duplicated, misordered, or internally inconsistent schema definitions.

## Annotation and metadata contracts

- [`annotations-v1.schema.json`](annotations-v1.schema.json) defines the append-only independent
  rater table. It preserves media-clock provenance, ethogram version, uncertainty, revisions, and
  adjudication without overwriting a rater's original observation.
- [`annotation-consensus-v1.schema.json`](annotation-consensus-v1.schema.json) defines a separate,
  frozen, reproducible consensus materialization. Its `input_annotations_sha256` binds the exact
  independent-annotation snapshot. Consensus is derived research ground truth; the live labels
  copied into `samples.csv` are not.
- [`clinical-outcomes-v1.schema.json`](clinical-outcomes-v1.schema.json) defines a separate,
  append-only clinical reference table with assessor role, reference standard, blinding, clinical
  timing, record pseudonym, and a link to a pre-specified prediction window. Clinical outcomes are
  never live observer labels and are never assigned by the IMU model.
- [`experiment-manifest-v1.schema.json`](experiment-manifest-v1.schema.json) defines versioned
  experiment/session metadata. Every reproducibility field is present; null values must be
  classified and explained through its `missingness` records. The protocol fixes the minimum
  double-annotation fraction, the annotation block records both forms of blinding, and every
  media-backed camera entry binds its media and clock mapping with immutable SHA-256 digests.
- [`evidence-ledger-v1.schema.json`](evidence-ledger-v1.schema.json) validates the machine-readable
  literature evidence map and keeps direct indoor evidence distinct from transfer or methods-only
  sources.
- [`reference-manifest-v1.schema.json`](reference-manifest-v1.schema.json) is the reusable local
  checkout manifest contract; current pins and honest license/checkout status live in
  [`references/manifest.json`](../references/manifest.json).

These governance artifacts are designed for research curation and are not yet emitted
automatically by the Android recorder. Until automation exists, create them during post-export
curation and bind them to immutable input artifacts with SHA-256 digests.
