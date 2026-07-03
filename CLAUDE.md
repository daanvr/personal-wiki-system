# CLAUDE.md

Guidance for Claude Code (and other AI assistants) when working in this repository.

## What this repository is

This is the **system** half of a two-repository personal wiki project. It holds the
*technology* — the tooling, structure, conventions, schemas, and automation that power a
personal knowledge wiki. It does **not** hold any knowledge content.

The project is split into two repositories that are kept strictly separate:

| Repository          | Visibility            | Contains                                                                                                                   |
| ------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `system` (this one) | **Public / shareable**| The engine: tooling, scripts, structure, conventions, templates, automation. Nothing personal.                            |
| `knowledge`         | **Private**           | The data: a `sources/` folder of source material and an Obsidian-style `wiki/` knowledge base built from it. Personal.     |

Locally the two repositories live side by side:

```
personal-wiki-system/
├── system/      ← this repository (public)
└── knowledge/   ← separate private repository
```

## The one rule that matters most

**Never put personal or private knowledge content in this repository.**

Anything about the user personally, source material, private notes, or wiki content
belongs in the separate private `knowledge` repository — not here. This repo is designed
to be public and shareable with collaborators, and it must contain nothing personal.

When in doubt about whether something belongs here, ask: *"Is this about **how** the wiki
works (system), or is it the actual knowledge stored **in** the wiki (knowledge)?"* Only
the former belongs in this repository.

## Why the split

- **Privacy** — the knowledge base is personal and stays in a private repository.
- **Shareability** — the system can be published, shared, and collaborated on by others
  without exposing anything personal.

## Repository layout

| Path                | Purpose                                                                   |
| ------------------- | ------------------------------------------------------------------------- |
| `config.example`    | Template for `config`; committed.                                         |
| `config`            | Machine-specific config (`KNOWLEDGE_PATH`); **gitignored**, never commit. |
| `init.sh`           | Scaffold a new knowledge base and write both repos' configs.              |
| `knowledge-path.sh` | Print the resolved absolute path to the knowledge base.                   |
| `lib/config.sh`     | Sourceable helpers: `resolve_path`, `get_config_value`, `knowledge_path`. |
| `modules/_shared/`  | Python helpers shared by all ingestion modules (`wikilib.py`).            |
| `modules/email/`    | Read-only IMAP ingestion: mail → Markdown notes in the knowledge base.    |
| `modules/calendar/` | Read-only CalDAV ingestion: events → Markdown notes.                      |
| `docs/`             | Design docs and proposals (e.g. the modular installer proposal).          |

`config` sets `KNOWLEDGE_PATH` — absolute, or relative to this repo's root (e.g.
`../knowledge` when the two repos are siblings). Run `./init.sh [path]` to create a
knowledge base (defaults to `../knowledge`); it also generates `config`. The created
knowledge base contains `sources/`, `wiki/`, its own `config`/`config.example`, and a
`.gitignore`.

## Status

Setup in progress. Config + init tooling and the first two ingestion modules (email over
IMAP, calendar over CalDAV — both read-only) are in place; wiki structure and conventions
are still to be designed. Keep this file up to date as the system takes shape.

Note for other agents: `AGENTS.md` is a pointer to this file — keep guidance here only.
