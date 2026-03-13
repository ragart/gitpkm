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

- Quickstart: see [pkm.wiki/Quickstart.md](pkm.wiki/Quickstart.md)
- CLI usage: see [pkm.wiki/CLI.md](pkm.wiki/CLI.md)
- Data model and ID rules: see [pkm.wiki/Data-Model-and-IDs.md](pkm.wiki/Data-Model-and-IDs.md)
- Formal schema contract: see [pkm.wiki/Schema-Contract.md](pkm.wiki/Schema-Contract.md)
- Automation workflow: see [pkm.wiki/Automation-and-Validation.md](pkm.wiki/Automation-and-Validation.md)
- Automation config: see [schema/automation.json](schema/automation.json)
- Example automation config: see [schema/automation.example.json](schema/automation.example.json)
- Publishing safety: see [pkm.wiki/Publishing-Safety.md](pkm.wiki/Publishing-Safety.md)
- Operational conventions: see [pkm.wiki/Operational-Conventions.md](pkm.wiki/Operational-Conventions.md)

## Documentation Structure

- User-facing docs are in the project wiki folder: [pkm.wiki](pkm.wiki)
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
