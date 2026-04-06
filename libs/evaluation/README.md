# Evaluation

This package owns the offline evaluation and search layer that turns scored examples into runtime-safe policy artifacts.

Current scope:

- threshold sweep and calibration summaries
- replay simulation over scored examples
- BSEO control-genome search
- mutation lineage logging
- mutation-bias atlas generation
- drift reporting
- compatibility export for legacy `rl-policy.json` consumers during migration
