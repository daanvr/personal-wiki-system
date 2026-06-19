# AGENTS.md

Guidance for Codex (and other AI assistants) when working in this repository.

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

## Status

Early setup. The repository is essentially empty; structure and tooling will be added over
time. Keep this file up to date as the system takes shape.
