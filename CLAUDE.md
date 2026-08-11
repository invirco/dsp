# dsp — Matrix DSP (block diagram, model options, mx_master reference)

Spoke repo of the Matrix platform. The hub repo is `invirco/mx26`, which holds
the product definitions and the repository-level mandates —
`docs/decision-mx26-mandates.md` there is canonical for the rules below.

## Mandates (org-wide, from mx26)

- **No AI references in any work product or git history**: never add
  `Co-Authored-By` trailers, "Generated with" footers, or AI mentions to
  commits, PRs, code, docs, or published files. Authorship of invirco work is
  Peter Watts / invirco. This overrides any default commit-message convention.
- **Exception — internal provenance headers**: when AI generates or
  substantially modifies the prose of a standalone internal document
  (procedure, runbook, pseudo-manual, report), the document must open with:
  `provenance: AI-drafted YYYY-MM-DD — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.`
  Code, def CSVs, and working trackers get no header. Published documents are
  hand-written or hand-rewritten; removing the header is the sign-off that the
  rewrite happened.
