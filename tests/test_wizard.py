"""Tests for the setup wizard engine.

Run from the system repo root:

    python3 -m unittest discover -s tests

Engine tests use a synthetic module in a temporary system root, so they never
read or write the real modules' configs. The parser tests run against the real
``config.example`` files to catch comment-format drift.
"""
from __future__ import annotations

import argparse
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SYSTEM_ROOT / "modules"))
sys.path.insert(0, str(SYSTEM_ROOT / "lib"))

from _shared.wikilib import read_kv  # noqa: E402
from wizard import base, engine, fields, manifest, migrate  # noqa: E402


class ScriptedIO:
    """Deterministic IO: answers pop off a queue; empty string means 'accept
    the default'. Raises if a select answer doesn't match an option value."""

    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.log = []

    def _pop(self) -> str:
        return self.answers.pop(0) if self.answers else ""

    def info(self, msg: str = "") -> None:
        self.log.append(str(msg))

    def warn(self, msg: str) -> None:
        self.log.append(f"! {msg}")

    def error(self, msg: str) -> None:
        self.log.append(f"error: {msg}")

    def ask(self, prompt, default=None, validate=None) -> str:
        answer = self._pop()
        if not answer and default is not None:
            answer = default
        if validate:
            problem = validate(answer)
            if problem:
                raise AssertionError(f"scripted answer {answer!r} rejected: {problem}")
        return answer

    def confirm(self, prompt, default=False) -> bool:
        answer = self._pop()
        if answer == "":
            return default
        return answer in ("y", "yes")

    def select(self, title, options, default=None):
        answer = self._pop()
        if answer == "" and default is not None:
            return default
        for value, _label, _desc in options:
            if answer == value:
                return value
        raise AssertionError(f"scripted select answer {answer!r} not in "
                             f"{[o[0] for o in options]}")

    def secret(self, prompt) -> str:
        return self._pop()


_DEMO_EXAMPLE = """\
# Demo module -- account configuration.

# Which provider profile to use.
PROVIDER=demoprov

# Your account login.
ACCOUNT=you@example.com

# Env var holding the password.
SECRET_REF=DEMO_APP_PASSWORD
#   ...or a gitignored file.
# SECRET_FILE=secret

# A plain extra setting.
EXTRA=42
"""

_DEMO_TEMPLATE = """\
# Provider template.
LABEL=Example
APP_PASSWORD_HINT=Make an app password.

# The endpoint host.
HOST=demo.example.com
AUTH=password
"""


def make_demo_system(root: Path) -> Path:
    """A minimal system repo with one synthetic module."""
    mdir = root / "modules" / "demo"
    (mdir / "providers").mkdir(parents=True)
    (mdir / "module.conf").write_text(
        "TITLE=Demo\nDESCRIPTION=A test module.\nCHECK=\n", encoding="utf-8")
    (mdir / "config.example").write_text(_DEMO_EXAMPLE, encoding="utf-8")
    (mdir / "providers" / "_template.conf").write_text(_DEMO_TEMPLATE, encoding="utf-8")
    (mdir / "providers" / "demoprov.conf").write_text(
        "LABEL=Demo Provider\nAPP_PASSWORD_HINT=Get one at demo.example.com\n"
        "HOST=demo.example.com\nAUTH=password\n", encoding="utf-8")
    return root


def make_args(knowledge: Path, **overrides) -> argparse.Namespace:
    defaults = dict(knowledge_path=str(knowledge), list=False, with_modules=[],
                    all_modules=False, no_modules=False, yes=False,
                    no_verify=True, migrate=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class ParseExampleTests(unittest.TestCase):
    """Against the real templates, so comment-format drift breaks loudly."""

    def test_email_example(self):
        specs = fields.parse_example(SYSTEM_ROOT / "modules" / "email" / "config.example")
        by_key = {s.key: s for s in specs}
        self.assertEqual(
            list(by_key),
            ["PROVIDER", "ACCOUNT", "SECRET_REF", "SECRET_FILE",
             "FOLDERS", "EXCLUDE_FOLDERS", "OUTPUT_SUBDIR", "SAVE_ATTACHMENTS"])
        self.assertEqual(by_key["PROVIDER"].default, "cirrux")
        self.assertEqual(by_key["FOLDERS"].default, "ALL")
        self.assertTrue(by_key["SECRET_FILE"].optional)
        self.assertFalse(by_key["ACCOUNT"].optional)
        self.assertTrue(by_key["ACCOUNT"].help_lines)

    def test_calendar_example(self):
        specs = fields.parse_example(SYSTEM_ROOT / "modules" / "calendar" / "config.example")
        by_key = {s.key: s for s in specs}
        self.assertEqual(
            list(by_key),
            ["PROVIDER", "ACCOUNT", "SECRET_REF", "SECRET_FILE",
             "CALENDARS", "EXCLUDE_CALENDARS", "DAYS_BACK", "DAYS_FORWARD",
             "OUTPUT_SUBDIR"])
        self.assertEqual(by_key["DAYS_BACK"].default, "30")
        self.assertEqual(by_key["EXCLUDE_CALENDARS"].default, "")

    def test_render_config_uncomments_optional(self):
        text = "# help\nA=1\n# B=x\n"
        rendered = fields.render_config(text, {"A": "9", "B": "y"})
        self.assertIn("A=9", rendered)
        self.assertIn("B=y", rendered)
        self.assertNotIn("# B=x", rendered)

    def test_render_config_leaves_unanswered(self):
        text = "# help\nA=1\n# B=x\n"
        rendered = fields.render_config(text, {"A": "9"})
        self.assertIn("# B=x", rendered)


class ManifestTests(unittest.TestCase):
    def test_discover_real_modules(self):
        modules = manifest.discover(SYSTEM_ROOT)
        by_name = {m.name: m for m in modules}
        self.assertIn("email", by_name)
        self.assertIn("calendar", by_name)
        self.assertEqual(by_name["email"].check_argv, ["ingest.py", "check"])
        self.assertEqual(by_name["calendar"].py_imports, ["caldav", "icalendar"])
        self.assertTrue(by_name["calendar"].has_requirements)
        self.assertFalse(by_name["email"].py_imports)


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysroot = self.root / "system"
        self.sysroot.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_scaffold(self):
        io = ScriptedIO()
        kb = base.scaffold(io, self.sysroot, "../kb")
        self.assertTrue((kb / "sources" / ".gitkeep").is_file())
        self.assertTrue((kb / "wiki").is_dir())
        self.assertTrue((kb / "settings" / "modules").is_dir())
        self.assertEqual(read_kv(kb / "config")["SYSTEM_PATH"], "../system")
        self.assertEqual(read_kv(self.sysroot / "config")["KNOWLEDGE_PATH"], "../kb")
        ignores = (kb / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/config", ignores)
        self.assertIn("/settings/modules/*/secret", ignores)

    def test_rescaffold_leaves_configs_untouched(self):
        io = ScriptedIO()
        kb = base.scaffold(io, self.sysroot, "../kb")
        (kb / "config").write_text("SYSTEM_PATH=/custom\n", encoding="utf-8")
        base.scaffold(io, self.sysroot, "../kb")
        self.assertEqual(read_kv(kb / "config")["SYSTEM_PATH"], "/custom")

    def test_gitignore_appends_without_clobbering(self):
        io = ScriptedIO()
        kb = base.scaffold(io, self.sysroot, "../kb")
        (kb / ".gitignore").write_text("/my-rule\n", encoding="utf-8")
        base.scaffold(io, self.sysroot, "../kb")
        text = (kb / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/my-rule", text)
        self.assertIn("/settings/modules/*/secret", text)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysroot = make_demo_system(self.root / "system")
        self.kb = self.root / "kb"

    def tearDown(self):
        self.tmp.cleanup()

    def config_path(self) -> Path:
        return self.kb / "settings" / "modules" / "demo" / "config"

    def test_full_interactive_setup(self):
        io = ScriptedIO([
            "y",           # set up Demo?
            "",            # provider -> default demoprov
            "a@b.example",  # ACCOUNT
            "",            # EXTRA -> default 42
            "",            # secret method -> env
            "",            # env var name -> DEMO_APP_PASSWORD
            "",            # skip pasting the password
        ])
        rc = engine.run(io, make_args(self.kb), self.sysroot)
        self.assertEqual(rc, 0)
        cfg = read_kv(self.config_path())
        self.assertEqual(cfg["PROVIDER"], "demoprov")
        self.assertEqual(cfg["ACCOUNT"], "a@b.example")
        self.assertEqual(cfg["EXTRA"], "42")
        self.assertEqual(cfg["SECRET_REF"], "DEMO_APP_PASSWORD")
        self.assertNotIn("SECRET_FILE", cfg)
        # the hint from the provider profile was surfaced
        self.assertTrue(any("demo.example.com" in line for line in io.log))

    def test_rerun_skip_changes_nothing(self):
        io = ScriptedIO(["y", "", "a@b.example", "", "", "", ""])
        engine.run(io, make_args(self.kb), self.sysroot)
        before = self.config_path().read_text(encoding="utf-8")
        io2 = ScriptedIO([""])  # enabled module -> default action: skip
        rc = engine.run(io2, make_args(self.kb), self.sysroot)
        self.assertEqual(rc, 0)
        self.assertEqual(self.config_path().read_text(encoding="utf-8"), before)

    def test_secret_file_flow(self):
        io = ScriptedIO([
            "y", "", "a@b.example", "",
            "file",         # secret method
            "hunter2-app",  # the password
        ])
        engine.run(io, make_args(self.kb), self.sysroot)
        cfg = read_kv(self.config_path())
        self.assertEqual(cfg["SECRET_FILE"], "secret")
        secret = self.config_path().parent / "secret"
        self.assertEqual(secret.read_text(encoding="utf-8").strip(), "hunter2-app")
        mode = stat.S_IMODE(secret.stat().st_mode)
        self.assertEqual(mode, stat.S_IRUSR | stat.S_IWUSR)

    def test_yes_scaffolds_from_defaults(self):
        io = ScriptedIO()
        rc = engine.run(io, make_args(self.kb, yes=True), self.sysroot)
        self.assertEqual(rc, 0)
        cfg = read_kv(self.config_path())
        self.assertEqual(cfg["PROVIDER"], "demoprov")
        self.assertEqual(cfg["ACCOUNT"], "you@example.com")

    def test_with_unknown_module_errors(self):
        io = ScriptedIO()
        rc = engine.run(io, make_args(self.kb, with_modules=["nope"], yes=True),
                        self.sysroot)
        self.assertEqual(rc, 2)

    def test_custom_provider_flow(self):
        io = ScriptedIO([
            "y",
            "_custom",       # provider -> Other...
            "myprov",        # short name
            "My Provider",   # display name
            "",              # APP_PASSWORD_HINT -> default
            "custom.example.org",  # HOST
            "",              # AUTH -> password
            "a@b.example", "",     # ACCOUNT, EXTRA
            "", "", "",            # env secret flow
        ])
        rc = engine.run(io, make_args(self.kb), self.sysroot)
        self.assertEqual(rc, 0)
        cfg = read_kv(self.config_path())
        self.assertEqual(cfg["PROVIDER"], "myprov")
        prof_path = (self.kb / "settings" / "modules" / "demo" / "providers"
                     / "myprov.conf")
        prof = read_kv(prof_path)
        self.assertEqual(prof["HOST"], "custom.example.org")
        self.assertEqual(prof["LABEL"], "My Provider")


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysroot = make_demo_system(self.root / "system")
        self.kb = self.root / "kb"
        self.mdir = self.sysroot / "modules" / "demo"

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrates_config_and_secret(self):
        (self.mdir / "config").write_text(
            "PROVIDER=demoprov\nACCOUNT=a@b.example\n"
            "SECRET_REF=DEMO_APP_PASSWORD\nSECRET_FILE=secret.txt\n",
            encoding="utf-8")
        (self.mdir / "secret.txt").write_text("hunter2\n", encoding="utf-8")

        modules = manifest.discover(self.sysroot)
        findings = migrate.find_old(modules)
        self.assertEqual(len(findings), 1)
        self.assertIsNotNone(findings[0].old_secret)

        io = ScriptedIO()
        migrate.run(io, findings, self.kb, assume_yes=True)

        new_dir = self.kb / "settings" / "modules" / "demo"
        self.assertFalse((self.mdir / "config").exists())
        self.assertFalse((self.mdir / "secret.txt").exists())
        cfg = read_kv(new_dir / "config")
        self.assertEqual(cfg["SECRET_FILE"], "secret")
        self.assertEqual((new_dir / "secret").read_text(encoding="utf-8").strip(),
                         "hunter2")

    def test_stale_legacy_config_is_left_alone(self):
        (self.mdir / "config").write_text("PROVIDER=demoprov\nACCOUNT=x\n",
                                          encoding="utf-8")
        new_dir = self.kb / "settings" / "modules" / "demo"
        new_dir.mkdir(parents=True)
        (new_dir / "config").write_text("PROVIDER=demoprov\nACCOUNT=new\n",
                                        encoding="utf-8")
        modules = manifest.discover(self.sysroot)
        io = ScriptedIO()
        migrate.run(io, migrate.find_old(modules), self.kb, assume_yes=True)
        self.assertTrue((self.mdir / "config").exists())
        self.assertEqual(read_kv(new_dir / "config")["ACCOUNT"], "new")


if __name__ == "__main__":
    unittest.main()
