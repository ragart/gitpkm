# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.8.0] - 2026-04-15

### Added

- Added local CLI command `python pkm.py bulk-import --input <file.csv> [--mapping <name|path|auto>] [--mappings-dir <dir>] [--apply]` for reusable mapping-driven CSV imports.
- Added dry-run-by-default import execution with optional `--apply` mode for writing table updates.
- Added reusable mapping files under `schema/import_mappings/` with named files and auto-selection by source headers.
- Added mapping support for ordered entity upserts and optional relation upserts using `ref:<entity_key>` references.
- Added `python pkm.py mappings list` to discover mappings and report mapping validity.
- Added `python pkm.py mappings validate` to validate mapping structure and optional source-CSV compatibility.
- Added `--validate-only` mode to `bulk-import` for preflight validation without row processing.
- Added `schema/import_mapping.contract.schema.json` and a CI validation step for reusable mapping files.
- Added `required_csv_columns` as a contract alias for header matching so the design is closer to the original 0.8.0 sketch.

### Changed

- Updated CLI documentation with bulk import syntax, behavior, and mapping token rules.

## [0.7.0] - 2026-04-15

### Added

- Added local CLI command `python pkm.py update <dataset> <id> --set key=value` to update existing entity rows by ID.
- Added support for updating in-table relationship fields (for example `*_id` columns) through the new `update` command.
- Added GitHub Issue Form support for update operations (`Update Entity`) mapped to `pkm.py update`.
- Added issue workflow mode for entity updates with maintainer guard, full pipeline execution, and direct commit to default branch.

### Changed

- Updated CLI documentation with `update` command usage and examples.

## [0.6.4] - 2026-04-15

### Changed

- Updated GitHub issue-form automation to run the full pipeline after entity/link operations so generated outputs (including README dataset inventory counters) stay synchronized.

## [0.6.3] - 2026-04-15

### Fixed

- Fixed note header generation so entity note frontmatter includes all entity-table columns, not only `id` and `type`.

### Added

- Added `python pkm.py reprocess-notes` to re-render all note headers and generated note blocks from current CSV tables.

## [0.6.2] - 2026-04-14

### Changed

- Documented the recommended `main` + `issue-ops` branch strategy for GitHub issue-form editing.
- Documented that issue form visibility is controlled by the repository default branch, while `.github/pkm-issue-ops.enabled` only gates automation.
- Documented maintenance sync guidance for updating `issue-ops` from `main`.

## [0.6.1] - 2026-04-14

### Added

- Added a maintainer-only guard for GitHub issue-form automation so only `OWNER`, `MEMBER`, and `COLLABORATOR` can trigger entity and relationship updates.

### Changed

- Documented that issue form visibility is controlled by the repository default branch, while `.github/pkm-issue-ops.enabled` only gates automation.

## [0.6.0] - 2026-04-13

### Added

- Added dataset bootstrap support in `pkm.py new`: when a dataset does not exist, columns can be created from `--columns` and from keys provided via `--set`.
- Added GitHub Issue Forms for adding entities and relationships without manual CSV edits.
- Added issue-driven GitHub Actions automation that applies form requests with `pkm.py` and updates the repository directly.

### Changed

- Updated CLI documentation with the remote GitHub issue-form workflow.
- Updated issue-form workflow to commit changes directly to the default branch and close processed issues.
- Updated issue-form workflow JavaScript actions to Node 24-compatible configuration (`actions/github-script@v8` and `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`).

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