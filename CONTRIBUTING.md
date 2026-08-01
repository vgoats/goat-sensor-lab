# Contributing

## Principles

- Preserve the canonical `SensorFrame` contract across every sensor source.
- Separate measured facts, observer labels, model outputs, and clinical outcomes.
- Require digest-bound experiment manifests, independent annotations, and frozen consensus for
  every research-model artifact; live recorder labels are engineering diagnostics only.
- Never report random-row accuracy as animal-independent performance.
- Do not add diagnosis, pregnancy, estrus, or parturition claims without a prospective protocol,
  ground truth, and held-out-animal validation.
- Keep raw animal/video data and personally identifiable farm information out of Git.

## Checks

```bash
./gradlew testDebugUnitTest assembleDebug
uv sync --directory analysis --extra dev --frozen
uv run --directory analysis ruff check .
uv run --directory analysis pytest
uvx --from platformio==6.1.19 platformio run -d firmware/xiao-nrf52840-sense
```

Changes to the protocol must update firmware, Android decoding tests, and `protocol/ble-v2.md`
together. Scientific claims must cite a primary paper or official hardware source and identify
vendor-only claims explicitly.
