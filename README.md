# GitPKM

GitPKM is a plain-text Personal Knowledge Management system that combines:

- Markdown for narrative notes
- CSV for relational data
- Python scripts for automation
- Git/GitHub for history and sync

The project is model-first:

1. Define the data model (entities, relationships, ID rules).
2. Define the workflow (generation, indexing, validation).
3. Apply the same model and workflow to any repository.

## Start Here

- [Quickstart](https://github.com/ragart/gitpkm/wiki/Quickstart)
- [CLI](https://github.com/ragart/gitpkm/wiki/CLI)
- [Data-Model-and-IDs](https://github.com/ragart/gitpkm/wiki/Data-Model-and-IDs)
- [Schema-Contract](https://github.com/ragart/gitpkm/wiki/Schema-Contract)
- [Automation-and-Validation](https://github.com/ragart/gitpkm/wiki/Automation-and-Validation)
- Automation config: see [schema/automation.json](schema/automation.json)
- Example automation config: see [schema/automation.example.json](schema/automation.example.json)
- Import mappings: see [schema/import_mappings](schema/import_mappings)
- [Publishing-Safety](https://github.com/ragart/gitpkm/wiki/Publishing-Safety)
- [Operational-Conventions](https://github.com/ragart/gitpkm/wiki/Operational-Conventions)

## Documentation Structure

- User-facing docs are in the project wiki: [gitpkm wiki](https://github.com/ragart/gitpkm/wiki)
- Internal AI context and full design notes live in [_instructions.md](_instructions.md)
- Release notes are tracked in [CHANGELOG.md](CHANGELOG.md)
- License is defined in [LICENSE](LICENSE)

## Core Principles

- Plain text first: Markdown + CSV
- Stable descriptive IDs as the source of truth
- Exact dataset names are part of the contract; the tooling does not singularize or pluralize them
- Separation of concerns: structured data vs narrative notes
- Safe automation using generated markers to avoid overwriting manual text

## Repository Layout

```text
data/        # CSV tables (source of truth)
notes/       # Markdown entity notes and indexes
scripts/     # generation, indexing, validation scripts
schema/      # schema documentation
notebooks/   # optional analysis
pkm.wiki/    # user-facing documentation
```
