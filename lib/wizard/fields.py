"""Turn a module's ``config.example`` into prompt specs.

The template the module already maintains *is* the wizard UI: every
``KEY=value`` line becomes a prompt whose default is the example value and
whose help text is the ``#`` comment block directly above it. A commented-out
``# KEY=value`` line marks an optional field. A blank line ends a comment
block, so the file header never bleeds into the first field's help.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_KV = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
_OPTIONAL = re.compile(r"^#\s*([A-Z][A-Z0-9_]*)=(.*)$")


@dataclass
class FieldSpec:
    key: str
    default: str
    help_lines: list[str] = field(default_factory=list)
    optional: bool = False  # was commented out in the example


def parse_example(path: Path) -> list[FieldSpec]:
    specs: list[FieldSpec] = []
    help_buf: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip():
            help_buf = []
            continue
        opt = _OPTIONAL.match(line)
        if opt:
            specs.append(FieldSpec(opt.group(1), opt.group(2).strip(),
                                   list(help_buf), optional=True))
            help_buf = []
            continue
        if line.lstrip().startswith("#"):
            help_buf.append(line.lstrip("# ").rstrip())
            continue
        kv = _KV.match(line)
        if kv:
            specs.append(FieldSpec(kv.group(1), kv.group(2).strip(), list(help_buf)))
            help_buf = []
    return specs


def render_config(example_text: str, answers: dict[str, str]) -> str:
    """The example template with answered values substituted in place, so the
    written config keeps all its documentation comments. Optional fields with
    an answer are uncommented; unanswered lines stay exactly as they were."""
    out = []
    for line in example_text.splitlines():
        key = None
        m = _KV.match(line)
        opt = _OPTIONAL.match(line) if not m else None
        if m:
            key = m.group(1)
        elif opt:
            key = opt.group(1)
        if key is not None and key in answers:
            out.append(f"{key}={answers[key]}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"
