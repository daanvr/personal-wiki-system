"""Interactive IO for the wizard.

Every prompt in the wizard goes through an object with this interface — no
other wizard file calls ``input()`` or reads the keyboard. Swap in a scripted
implementation for tests, or a different front-end later.
"""
from __future__ import annotations

import getpass


class ConsoleIO:
    """Terminal front-end: plain prompts on stdin/stdout."""

    def info(self, msg: str = "") -> None:
        print(msg)

    def warn(self, msg: str) -> None:
        print(f"! {msg}")

    def error(self, msg: str) -> None:
        print(f"error: {msg}")

    def ask(self, prompt: str, default: str | None = None, validate=None) -> str:
        """One-line free-text prompt. Empty input returns the default.
        ``validate`` maps a candidate answer to an error message (or None)."""
        suffix = f" [{default}]" if default not in (None, "") else ""
        while True:
            answer = input(f"{prompt}{suffix}: ").strip()
            if not answer and default is not None:
                answer = default
            if validate:
                problem = validate(answer)
                if problem:
                    self.warn(problem)
                    continue
            return answer

    def confirm(self, prompt: str, default: bool = False) -> bool:
        hint = "Y/n" if default else "y/N"
        answer = input(f"{prompt} [{hint}] ").strip().lower()
        if not answer:
            return default
        return answer in {"y", "yes"}

    def select(self, title: str, options: list[tuple], default=None):
        """Numbered menu. ``options`` is a list of (value, label, description)
        tuples (description may be None). Returns the chosen value."""
        self.info(title)
        default_index = None
        for i, (value, label, desc) in enumerate(options, 1):
            line = f"  {i}) {label}"
            if desc:
                line += f" — {desc}"
            if default is not None and value == default:
                default_index = i
                line += "  (default)"
            self.info(line)
        while True:
            raw = input(f"Choose 1-{len(options)}: ").strip()
            if not raw and default_index is not None:
                return options[default_index - 1][0]
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1][0]
            self.warn("Please enter one of the listed numbers.")

    def secret(self, prompt: str) -> str:
        """Read a secret without echoing it."""
        return getpass.getpass(f"{prompt}: ")
