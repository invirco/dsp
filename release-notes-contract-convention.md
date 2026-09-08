# release notes contract convention

Status: active
Date: 2026-09-08
Scope: required notes whenever matrix contract changes are introduced.

## Rule

Any change that modifies matrix definition contract inputs or generated contract outputs must include a contract note in the PR description and merge commit message.

## Required fields

- Contract version: defs-vYYYY.MM.DD or equivalent
- Source repo/ref: invirco/defs + tag (the `defs/` submodule)
- Source commit: full or short sha
- Changed products: D24, D32, or both
- Change class: schema, counts/capability, behavior profile, mapping-only
- Risk level: low, medium, high
- Validation evidence: command output references from regenerate workflow

## PR template snippet

Contract bump:
- version:
- source repo/ref:
- source commit:
- products affected:
- change class:
- risk:
- validation run:

## Merge commit footer format

Contract-Version: defs-vYYYY.MM.DD
Contract-Source: invirco/defs@<sha>
Contract-Products: D24,D32
Contract-Change-Class: schema|counts|behavior|mapping

## Example

Contract bump:
- version: defs-v2026.09.08
- source repo/ref: invirco/defs, tag defs-v2026.09.08 (the `defs/` submodule)
- source commit: b0e4b487fdca25d6e4558dc953d7400aef13d686
- products affected: D24,D32
- change class: schema
- risk: medium
- validation run: ./regenerate-dsp-contract.sh

Merge footer:
- Contract-Version: defs-v2026.09.08
- Contract-Source: invirco/defs@b0e4b487fdca25d6e4558dc953d7400aef13d686
- Contract-Products: D24,D32
- Contract-Change-Class: schema
