# Personal Wiki System

The **system** half of a personal wiki project — the tooling, structure, and conventions
that power a personal knowledge base. It contains no personal data, so it can be shared
and worked on openly.

## Two-repository design

This project is deliberately split into two repositories that are kept strictly separate:

- **`system`** (this repo, public) — the engine: tooling, structure, conventions,
  templates, and automation. Nothing personal lives here.
- **`knowledge`** (separate, private) — the data: source material and an Obsidian-style
  wiki built from it. This stays private.

Keeping the system and the data apart means the system can be public and reusable while
the knowledge it organizes remains private.

```
personal-wiki-system/
├── system/      ← this repository (public)
└── knowledge/   ← separate private repository
```

## Status

Early setup — structure and tooling are being added.
