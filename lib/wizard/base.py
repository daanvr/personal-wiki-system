"""Base scaffolding: the knowledge repo and the two pointer configs.

The Python port of what ``init.sh`` used to do itself, plus the settings home.
Idempotent: existing configs are left untouched, and the knowledge repo's
``.gitignore`` is appended to (never overwritten — it may carry user rules).
"""
from __future__ import annotations

from pathlib import Path

from _shared.wikilib import read_kv, resolve_path

# Rules the knowledge repo's .gitignore must contain. The pointer config is
# machine-specific; module secret files must never be committed, even privately.
_REQUIRED_IGNORES = [
    ("# Machine-specific config (use config.example as the template)", "/config"),
    ("# Module secrets written by the setup wizard — never commit these", "/settings/modules/*/secret"),
    ("# macOS", ".DS_Store"),
    (None, "._*"),
]

_KNOWLEDGE_CONFIG_EXAMPLE = """\
# Path back to the system repository (the public tooling repo).
#
# May be absolute (e.g. /Users/you/personal-wiki-system/system) or relative to
# this knowledge base's root (e.g. ../system when it sits beside system/).
SYSTEM_PATH=../system
"""


def resolve_knowledge(io, system_root: Path, knowledge_arg: str | None,
                      assume_yes: bool = False) -> str:
    """The raw knowledge path: CLI argument, then existing config, then a
    prompt (or the default when running non-interactively)."""
    if knowledge_arg:
        return knowledge_arg
    existing = read_kv(system_root / "config").get("KNOWLEDGE_PATH")
    if existing:
        return existing
    if assume_yes:
        return "../knowledge"
    return io.ask("Where should the knowledge base live?", default="../knowledge")


def _ensure_gitignore(path: Path) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = {line.strip() for line in text.splitlines()}
    additions = []
    for comment, rule in _REQUIRED_IGNORES:
        if rule in lines:
            continue
        if comment:
            additions.append(comment)
        additions.append(rule)
    if additions:
        if text and not text.endswith("\n"):
            text += "\n"
        if text:
            text += "\n"
        path.write_text(text + "\n".join(additions) + "\n", encoding="utf-8")


def scaffold(io, system_root: Path, knowledge_arg: str | None,
             assume_yes: bool = False) -> Path:
    """Create/refresh the knowledge base skeleton; returns its absolute path."""
    raw = resolve_knowledge(io, system_root, knowledge_arg, assume_yes)
    system_root = system_root.resolve()  # canonical, so sibling detection works
    knowledge = Path(resolve_path(raw, system_root))

    io.info("Setting up knowledge base")
    io.info(f"  system:    {system_root}")
    io.info(f"  knowledge: {knowledge}")
    io.info("")

    for sub in ("sources", "wiki", "settings/modules"):
        (knowledge / sub).mkdir(parents=True, exist_ok=True)
    knowledge = knowledge.resolve()
    (knowledge / "sources" / ".gitkeep").touch()
    (knowledge / "wiki" / ".gitkeep").touch()

    # Relative cross-references when the two repos are siblings, else absolute.
    if system_root.parent == knowledge.parent:
        knowledge_ref = f"../{knowledge.name}"
        system_ref = f"../{system_root.name}"
    else:
        knowledge_ref = str(knowledge)
        system_ref = str(system_root)

    (knowledge / "config.example").write_text(_KNOWLEDGE_CONFIG_EXAMPLE, encoding="utf-8")

    knowledge_config = knowledge / "config"
    if knowledge_config.exists():
        io.info("  - knowledge config already exists, leaving it untouched")
    else:
        knowledge_config.write_text(
            "# Path back to the system repository (the public tooling repo).\n"
            f"SYSTEM_PATH={system_ref}\n",
            encoding="utf-8",
        )
        io.info(f"  - wrote knowledge config (SYSTEM_PATH={system_ref})")

    _ensure_gitignore(knowledge / ".gitignore")

    system_config = system_root / "config"
    if system_config.exists():
        io.info("  - system config already exists, leaving it untouched")
    else:
        system_config.write_text(
            "# Path to the knowledge base (the private data repo).\n"
            f"KNOWLEDGE_PATH={knowledge_ref}\n",
            encoding="utf-8",
        )
        io.info(f"  - wrote system config (KNOWLEDGE_PATH={knowledge_ref})")

    return knowledge
