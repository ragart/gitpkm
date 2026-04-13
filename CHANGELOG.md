# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.5.0] - 2026-04-13

### Added

- Extended `pkm.py new` to accept repeated `--set key=value` pairs so entity rows can be created with all existing table columns in one command.
- Added CLI contract tests for creating entities with additional fields and for rejecting unknown columns.

### Changed

- Updated CLI documentation to include `new` command syntax with optional `--set` values and examples.

## [0.4.1] - 2026-03-15

### Fixed

- Fixed execution workflow for rendering a content directory in `README.md`.

## [0.4.0] - 2026-03-15

### Added

- Implemented automation to render a content directory in `README.md`.

## [0.3.1] - 2026-03-15

### Changed

- Replaced id-based output format for a name-based approach in auto-generated indexes.

## [0.3.0] - 2026-03-15

### Changed

- Changed output format for auto-generated indexes.

## [0.2.1] - 2026-03-15

### Added

- Added migration script for wiki links.

### Changed

- Changed link generation behavior to use standard relative Markdown links.

## [0.2.0] - 2026-03-15

### Added

- Auto-generated entity indexes and preserved explicit config precedence.

## [0.1.1] - 2026-03-15

### Fixed

- Added fallback to system Python when Conda environment is unavailable.

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