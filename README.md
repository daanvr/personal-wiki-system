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

## Getting started

Create a knowledge base next to this repository:

```sh
./init.sh                 # creates ../knowledge with sources/ and wiki/
./init.sh /path/to/kb     # or point it at a specific location
```

This scaffolds the knowledge base (`sources/`, `wiki/`), its `config` and `.gitignore`,
and writes this repo's `config`. Print the resolved knowledge-base path any time with:

```sh
./knowledge-path.sh
```

## Configuration

`config` (gitignored, per machine) defines where the knowledge base lives via
`KNOWLEDGE_PATH`. It may be **absolute** (a specific location on this machine) or
**relative** to this repo's root (e.g. `../knowledge` when the repos sit side by side).
Copy `config.example` to `config`, or let `init.sh` generate it.

## Status

Setup in progress — config and init tooling are in place; wiki structure and conventions
are still to be designed.
