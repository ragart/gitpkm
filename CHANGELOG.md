# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.1.0] - 2026-03-13

### Added

- First working CLI with `new` and `link` commands in `pkm.py`.
- Exact dataset-name contract (no singularization/pluralization inference).
- Automated note rendering via generated blocks (`header`, `list:<table>`, `table:<table>`).
- Config-driven index generation from `schema/automation.json`.
- Validation script for CSV schema, IDs, FK integrity, note frontmatter, and links.
- Bootstrap, hook, and CI workflow for deterministic checks.
- Public export script with private-ID filtering and note policy options (`redact`, `drop`).
- Attachment export from note-relative links with private-file denylist support.
- Public docs set under `pkm.wiki/` and root `README.md`.

### Notes

- This is the first release candidate milestone suitable for initial public use.