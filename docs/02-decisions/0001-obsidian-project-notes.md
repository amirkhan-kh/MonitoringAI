# 0001: Obsidian Project Notes

## Decision

Use the project root as the Obsidian vault, with project notes under `docs/`.

## Context

The root contains application code, Docker configuration, and the main `README.md`. Obsidian should be able to link to those files while avoiding generated and secret folders.

## Consequences

- New notes go to `docs/00-inbox` by default.
- Attachments go to `docs/assets`.
- Obsidian excludes dependencies, virtual environments, session files, secrets, build outputs, and cache folders from indexing.
