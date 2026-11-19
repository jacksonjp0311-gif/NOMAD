# CI

## Historical
`.github/workflows/ci.yml` preserves the original v0.18 sealed-byte verification. It runs only on manual dispatch. The frozen release inventory is not rewritten for continuous development files.

## Development
`.github/workflows/ci-dev.yml` runs tests and a continuous-module import smoke on every push. It does not require the sealed v0.18 manifest to match the current tree.

This separates historical release integrity from current development validation.
