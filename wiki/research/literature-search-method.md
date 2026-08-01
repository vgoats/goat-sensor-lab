# Literature Search Method

## Scope and status

This reproducible search supports design decisions for wearable IMU collection, synchronized
behavior annotation, welfare governance, and open hardware for indoor stall-fed goats and sheep.
The current pass was run and reconciled on **2026-08-01**. It is a scoped evidence map, not a
completed PRISMA systematic review or meta-analysis. Before a regulated claim, protocol
publication, or systematic-review claim, rerun the search with a librarian/statistician and include
subscription indexes such as Scopus and Web of Science.

The machine-readable extraction is
[`references/evidence-ledger.json`](../../references/evidence-ledger.json), validated by
[`evidence-ledger-v1.schema.json`](../../schema/evidence-ledger-v1.schema.json). The
[evidence matrix](evidence-matrix.md) is its concise human-facing interpretation.

## Sources searched

- Crossref/DOI and publisher search pages for bibliographic verification;
- PubMed and PubMed Central for animal behavior, welfare, and sensor studies;
- institutional repositories when the publisher full text was unavailable;
- Recherche Data Gouv, Figshare, and Zenodo for datasets and versioned artifacts;
- GitHub and official project sites for open hardware, firmware, and annotation tools;
- official manufacturer documentation for board and sensor specifications; and
- backward/forward citation chasing from the closest indoor-goat and small-ruminant reviews.

Google Scholar or general web results may identify a candidate, but a ledger record is verified
against a DOI registry, publisher, institutional/data repository, official project, or official
guideline. Scopus and Web of Science subscription searches were not available in this pass and are
an explicit limitation.

## Recorded search strings

Run the strings with spelling variants (`behavior`/`behaviour`) and filter through the search date:

```text
(goat OR caprine) AND (accelerometer OR inertial OR IMU OR wearable) AND
  (feeding OR rumination OR posture OR activity OR behaviour) AND (indoor OR intensive OR housed)

(sheep OR ovine OR small ruminant) AND (accelerometer OR inertial OR IMU OR wearable) AND
  (feeding OR rumination OR posture OR welfare OR lambing)

(goat OR sheep) AND (video annotation OR ethogram OR inter-rater OR adjudication OR ground truth)

(goat OR sheep) AND (wearable OR precision livestock) AND
  (welfare OR disease OR stress OR kidding OR lambing) AND (validation OR prospective)

(XIAO nRF52840 Sense OR LSM6DS3TR-C) AND (IMU OR BLE OR sampling OR FIFO OR calibration)

site:github.com (goat OR sheep) (IMU OR accelerometer OR behavior) (firmware OR dataset)
```

For every run, archive the date, interface/database, exact string, filters, result count, and exported
candidate list. Deduplicate by DOI, then title/year. Do not silently replace a source when its
publisher metadata changes; append a ledger revision.

## Eligibility

Include peer-reviewed primary studies, data papers/datasets, systematic or field-defining reviews,
official hardware specifications, official research-software projects, and animal-research
guidelines that materially affect this project. Prioritize studies with goats/sheep, indoor or
intensive housing, wearable accelerometry/IMU, synchronized observable labels, and animal-held-out
evaluation.

Exclude sources that lack enough methods to identify species, setting, placement, labels, or split;
marketing claims without independent validation; GPS-only grazing work; cattle/human models
presented as small-ruminant truth; and disease/pregnancy claims without an accepted reference
standard. A useful but indirect source may remain as transfer evidence if its mismatch is explicit.

## Directness labels

| Label | Interpretation |
|---|---|
| `DIRECT_INDOOR_GOAT` | Goat primary data in indoor/intensive housing relevant to behavior sensing |
| `DIRECT_INDOOR_SHEEP` | Sheep primary data in indoor/intensive housing relevant to behavior sensing |
| `DIRECT_MIXED_SMALL_RUMINANT` | Direct goat/sheep validation with separable species results |
| `TRANSFER_PASTURE_GOAT` | Goat evidence, but grazing/GPS/environment differs from the product boundary |
| `TRANSFER_OTHER_ENDPOINT` | Relevant acquisition/analysis, but endpoint or care context differs |
| `SYNTHESIS` | Review or stakeholder synthesis; useful for framing, not device accuracy |
| `METHODS_ONLY` | Annotation/software/statistical method without animal-product validation |
| `GUIDANCE_ONLY` | Research-planning/reporting guidance |
| `OFFICIAL_SPECIFICATION` | Hardware fact only; not biological/model evidence |

Transfer, synthesis, methods, guidance, and specifications cannot satisfy an indoor animal-model
validation gate.

## Screening and extraction

Two reviewers should independently screen title/abstract and then full text for any systematic
review or claim-supporting release. Record exclusion reason and resolve disagreement without
deleting either decision. Extract title/authors/year/DOI, source type, access date/license, species,
animals, housing, placement, hardware/rate/range, label source, prediction target, partitioning,
windowing, metrics/uncertainty, open artifacts, directness, limitations, and intended project use.

Before each experiment freeze and major evidence release:

1. rerun every stored query through the new cutoff date;
2. resolve changed datasets/releases to immutable versions and checksums;
3. add records rather than rewriting history, then review directness and claim language;
4. regenerate the human evidence matrix from the reviewed ledger; and
5. record unresolved paywall, translation, license, cohort, or split details as `UNKNOWN` rather
   than inferring them.
