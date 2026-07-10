"""Setup wizard for the wiki system.

Convention-driven: modules self-describe via ``module.conf`` and their
``config.example``; the engine never names a specific module. All interactive
IO goes through the object in ``console.py`` so a different front-end (tests,
a future web UI) can swap in.
"""
