# Federation code review — 2026-10-07

Review base: `3a3c4982aee328592443fe95593a6f5e025f37ff`.

Scope: repository API and data boundaries, federation metadata, existing regression tests, GUI capability gates, and shared infrastructure where applicable. This is a targeted review with automated validation, not a claim that every possible defect has been eliminated.

## Changes

- **P1:** Nonfinite coordinates could escape number parsing into JSON and GeoJSON responses. Return null for nonfinite parsed values and omit invalid point features.

## Validation

Validation results are recorded in the pull request description. Regression cases include invalid inputs and preservation of normal behavior. GUI parity baselines were not regenerated.

The review uses isolated local checkouts and synthetic regression fixtures. Existing frozen-source receipts retain their original scope and date; they do not establish live source freshness. Shared-package consumer pins remain immutable until a separate release/pin update.
