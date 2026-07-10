"""Wizard orchestration.

First run: base scaffold -> migration offer -> per-module guided setup with a
live verification. Re-run: enabled modules offer reconfigure / verify / skip.
Configs are written atomically, rendered from each module's ``config.example``
so the user's file keeps all its documentation comments.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from _shared.wikilib import read_kv

from . import base, deps, fields, manifest, migrate, providers, secrets, verify

# Keys with dedicated sub-flows; everything else is a plain prompt-with-default.
RESERVED_KEYS = {"PROVIDER", "SECRET_REF", "SECRET_FILE"}


def run(io, args, system_root: Path) -> int:
    modules = manifest.discover(system_root)

    if args.list:
        return _cmd_list(io, modules, system_root)

    knowledge = base.scaffold(io, system_root, args.knowledge_path, assume_yes=args.yes)

    findings = migrate.find_old(modules)
    if findings:
        io.info("")
        io.info("Module config(s) found in the legacy location (inside the system repo).")
        migrate.run(io, findings, knowledge, assume_yes=args.yes or args.migrate)

    if args.no_modules:
        _summary(io, modules, knowledge)
        return 0

    if args.with_modules:
        by_name = {m.name: m for m in modules}
        unknown = [n for n in args.with_modules if n not in by_name]
        if unknown:
            io.error(f"Unknown module(s): {', '.join(unknown)}. "
                     f"Available: {', '.join(sorted(by_name))}")
            return 2
        for name in args.with_modules:
            _setup_module(io, by_name[name], knowledge, args)
    elif args.all_modules or args.yes:
        for module in modules:
            _setup_module(io, module, knowledge, args)
    else:
        _interactive_menu(io, modules, knowledge, args)

    _summary(io, modules, knowledge)
    return 0


def _interactive_menu(io, modules, knowledge: Path, args) -> None:
    io.info("")
    io.info("Optional modules:")
    for module in modules:
        io.info("")
        enabled = manifest.is_enabled(module, knowledge)
        io.info(f"  {module.title} - {module.description}")
        if enabled:
            action = io.select(
                f"{module.title} is already set up.",
                [("skip", "Skip", None),
                 ("verify", "Verify only", "run the live connection check"),
                 ("reconfigure", "Reconfigure", "walk through the settings again")],
                default="skip",
            )
            if action == "skip":
                continue
            if action == "verify":
                existing = read_kv(manifest.config_path(module, knowledge))
                _verify_flow(io, module, knowledge, existing, {})
                continue
        elif not io.confirm(f"Set up {module.title}?", default=True):
            continue
        _setup_module(io, module, knowledge, args)


def _setup_module(io, module: manifest.Module, knowledge: Path, args) -> None:
    cfg_path = manifest.config_path(module, knowledge)
    example = module.dir / "config.example"

    if args.yes:
        # Non-interactive: scaffold from defaults, never overwrite.
        if cfg_path.is_file():
            io.info(f"{module.title}: config already exists at {cfg_path}, leaving it untouched")
            return
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(cfg_path, example.read_text(encoding="utf-8"))
        io.info(f"{module.title}: scaffolded {cfg_path} from defaults — "
                f"edit it, then run the module's check.")
        return

    io.info("")
    io.info(f"--- {module.title} setup ---")
    if not deps.ensure(io, module):
        io.warn(f"Skipping {module.title} until its requirements are met.")
        return

    specs = fields.parse_example(example)
    existing = read_kv(cfg_path)
    answers: dict[str, str] = {}

    # Provider picker.
    profile = None
    if any(s.key == "PROVIDER" for s in specs):
        profs = providers.list_profiles(module, knowledge)
        options = [(p.name, p.label, None) for p in profs]
        options.append(("_custom", "Other...", "create a new provider profile"))
        default = existing.get("PROVIDER") or next(
            (s.default for s in specs if s.key == "PROVIDER"), None)
        if default not in {p.name for p in profs}:
            default = None
        choice = io.select("Which provider?", options, default=default)
        if choice == "_custom":
            profile = providers.create_custom(io, module, knowledge)
        else:
            profile = next(p for p in profs if p.name == choice)
        answers["PROVIDER"] = profile.name
        if profile.hint:
            io.info("")
            io.info(profile.hint)
        if profile.docs_url:
            io.info(f"Docs: {profile.docs_url}")

    # Plain fields, straight from config.example.
    for spec in specs:
        if spec.key in RESERVED_KEYS:
            continue
        io.info("")
        for line in spec.help_lines:
            io.info(f"  {line}")
        value = io.ask(spec.key, default=existing.get(spec.key, spec.default))
        if value or not spec.optional:
            answers[spec.key] = value

    # Secret sub-flow.
    runtime_env: dict[str, str] = {}
    if any(s.key in ("SECRET_REF", "SECRET_FILE") for s in specs):
        io.info("")
        defaults = {s.key: existing.get(s.key, s.default) for s in specs}
        updates, runtime_env = secrets.configure(io, module, knowledge, defaults)
        answers.update(updates)

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(cfg_path, fields.render_config(example.read_text(encoding="utf-8"), answers))
    io.info("")
    io.info(f"Wrote {cfg_path}")

    if args.no_verify or not module.check_argv:
        return
    can_verify = (bool(runtime_env) or "SECRET_FILE" in answers
                  or bool(os.environ.get(answers.get("SECRET_REF", ""))))
    if not can_verify:
        io.info("Skipping the live check (no password available this session). Run it later:")
        io.info(f"  cd modules/{module.name} && python3 {' '.join(module.check_argv)}")
        return
    _verify_flow(io, module, knowledge, answers, runtime_env)


def _verify_flow(io, module: manifest.Module, knowledge: Path,
                 answers: dict[str, str], runtime_env: dict[str, str]) -> bool:
    while True:
        io.info("")
        io.info(f"Verifying {module.title} (live connection check)...")
        rc = verify.run_check(module, runtime_env)
        if rc == 0:
            io.info(f"{module.title}: verified OK.")
            return True
        action = io.select(
            f"{module.title}: the check failed (exit {rc}).",
            [("retry", "Retry", None),
             ("secret", "Re-enter the password and retry", None),
             ("keep", "Keep the config and continue", "you can fix it and re-run later")],
            default="retry",
        )
        if action == "keep":
            return False
        if action == "secret":
            value = io.secret("App password")
            if answers.get("SECRET_FILE"):
                secret_path = manifest.settings_dir(module, knowledge) / answers["SECRET_FILE"]
                secret_path.write_text(value + "\n", encoding="utf-8")
            elif answers.get("SECRET_REF"):
                runtime_env[answers["SECRET_REF"]] = value


def _cmd_list(io, modules, system_root: Path) -> int:
    raw = read_kv(system_root / "config").get("KNOWLEDGE_PATH")
    knowledge = None
    if raw:
        from _shared.wikilib import resolve_path
        candidate = Path(resolve_path(raw, system_root))
        if candidate.is_dir():
            knowledge = candidate.resolve()
    if knowledge is None:
        io.info("Not initialized yet — run ./init.sh first.")
    for module in modules:
        if knowledge is None:
            status = "unknown"
        else:
            status = "enabled" if manifest.is_enabled(module, knowledge) else "not set up"
        io.info(f"  {module.name:10} {module.title} - {module.description} [{status}]")
    return 0


def _summary(io, modules, knowledge: Path) -> None:
    io.info("")
    io.info(f"Done. Knowledge base: {knowledge}")
    enabled = [m for m in modules if manifest.is_enabled(m, knowledge)]
    if enabled:
        io.info("Enabled modules and their next steps:")
        for m in enabled:
            io.info(f"  {m.title}:  cd modules/{m.name} && python3 ingest.py sync --dry-run")
        io.info("")
        io.info("Your module settings live in the knowledge repo — version them:")
        io.info(f"  cd \"{knowledge}\" && git add settings && git commit -m 'Module settings'")
    else:
        io.info("No modules enabled yet. Re-run ./init.sh any time to set them up.")


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
