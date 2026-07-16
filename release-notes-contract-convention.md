# release notes contract convention

Status: active
Date: 2026-07-15
Scope: required notes whenever matrix contract changes are introduced.

## Rule

Any change that modifies matrix definition contract inputs or generated contract outputs must include a contract note in the PR description and merge commit message.

## Required fields

- Contract version: defs-vYYYY.MM.DD or equivalent
- Source repo/ref: invirco/mx26 + branch/tag
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
Contract-Source: invirco/mx26@<sha>
Contract-Products: D24,D32
Contract-Change-Class: schema|counts|behavior|mapping

## Example

Contract bump:
- version: defs-v2026.07.15
- source repo/ref: invirco/mx26 main
- source commit: 96c54d0632a43bfcd53a3ae3012393949bfbdc3c
- products affected: D24,D32
- change class: mapping
- risk: medium
- validation run: ./regenerate-dsp-contract.sh

Merge footer:
- Contract-Version: defs-v2026.07.15
- Contract-Source: invirco/mx26@96c54d0632a43bfcd53a3ae3012393949bfbdc3c
- Contract-Products: D24,D32
- Contract-Change-Class: mapping
