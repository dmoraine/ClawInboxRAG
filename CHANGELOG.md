# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]


## [0.1.0] - 2026-03-28

### Added

- Initial ClawInboxRAG mono-repo release candidate.
- Local Gmail RAG engine (`gmail_rag/`) and community skill wrapper (`clawinboxrag/`).
- Legacy Gmail RAG snapshot preserved under `packages/gmail-rag-legacy/`.
- Root project packaging with local test support and publication readiness checks.

### Changed

- Aligned docs, commands, and safety guidance with the ClawInboxRAG repo layout.
- Added repository-level test configuration and reproducible local validation.


### Added

- Publication-readiness documentation set:
  - `README.md`
  - `LICENSE` (MIT)
  - `.gitignore`
  - `CONTRIBUTING.md`
  - `docs/RELEASE_CHECKLIST.md`
- Phase 2 parity tooling and report artifacts:
  - `clawinboxrag/parity_harness.py`
  - `tests/test_phase2_parity.py`
  - `scripts/run_phase2_parity.py`
  - `docs/PHASE2_PARITY_VALIDATION.md`

### Changed

- Clarified `SKILL.md` naming, behavior, safety constraints, and command mapping.
- Aligned `references/*.md` with current parser and wrapper behavior.
- Exported parity harness helpers from `clawinboxrag/__init__.py`.
