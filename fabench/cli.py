# Copyright 2026  Olewave, LLC

# See LICENSE at the repository root for the full terms
#
# Licensed under the PolyForm Noncommercial License 1.0.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Noncommercial use is permitted -- research, teaching, personal study, and work
# by charitable, educational, public-safety, environmental and government
# organisations. Any commercial use requires a separate licence from Olewave, LLC.
#
# AS FAR AS THE LAW ALLOWS, THE SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR
# CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING
# OUT OF THESE TERMS OR THE USE OR NATURE OF THE SOFTWARE, UNDER ANY KIND OF
# LEGAL CLAIM.

"""fabench command-line entrypoints (Plan S0 / S6).

Subcommands are thin: they parse args, load config, and dispatch into the stage
modules. Heavy stage imports are lazy so ``--help`` and unrelated commands stay
fast and importable even before every optional dependency (torch, whisperx, …)
is installed.

``--config`` is optional everywhere: omit it and the run is the composed
defaults (fabench/config.yaml, fabench/noise/, datasets/, evals/<kind>/<tool>/).
Pass one to state what a run changes — staged corpus roots, which aligners,
a scoring protocol.

    python -m fabench.cli --help
    fabench config                                     # print the resolved run
    fabench init                                      # say where corpora are staged
    fabench ingest                                    # -> canonical gold
    fabench mix
    fabench align     --aligner torchaudio_fa
    fabench score
    fabench run                                       # S3->S6 end to end
    fabench report
    fabench run       --config my_variant.yaml        # a deliberate variant
    fabench selftest  --out summary/selftest           # synthetic E2E, no corpora
    fabench gates                                      # data-independent sanity gates
"""

from __future__ import annotations

import argparse
import os
import sys

#: No default config FILE: every default composes from the subsystem that owns
#: it (fabench/config.yaml, fabench/noise/, datasets/, evals/<kind>/<tool>/), so
#: omitting --config runs those composed defaults. Pass a config to state what
#: a run changes — staged corpus roots, which aligners, a scoring protocol.
DEFAULT_CONFIG = None


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="run config YAML stating what this run changes; omit to use "
             "$FABENCH_CONFIG, else the composed defaults",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fabench",
        description="English forced-alignment benchmark (v1): paired additive-noise "
        "degradation over TIMIT + Buckeye gold.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--version", action="store_true", help="print version and exit")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    pin = sub.add_parser(
        "init",
        help="set this machine up: asks where corpora are and which GPUs to "
             "use, then writes .fabench.env",
    )
    pin.add_argument("--root", action="append", metavar="CORPUS=PATH",
                     help="staged corpus root, e.g. --root timit=/data/TIMIT "
                          "(repeatable; skips the search)")
    pin.add_argument("--search", action="append", metavar="DIR",
                     help="where to look for staged corpora (repeatable; "
                          "default: common data directories)")
    pin.add_argument("--non-interactive", "--yes", "-y", action="store_true",
                     dest="non_interactive",
                     help="never prompt; keep what is already set and take what is "
                          "found (automatic when stdin is not a terminal)")

    pc = sub.add_parser("config", help="validate config and print resolved summary")
    _add_config_arg(pc)

    pi = sub.add_parser("ingest", help="S1: corpora -> canonical gold JSON")
    _add_config_arg(pi)
    pi.add_argument("--corpus", help="restrict to one corpus (timit|buckeye|l2arctic)")
    pi.add_argument("--limit", type=int, default=None, help="ingest at most N utts")

    ph = sub.add_parser("normalize-check", help="S2: report unmapped-label rates")
    _add_config_arg(ph)

    pn = sub.add_parser("noise", help="S3: noise pool ops")
    _add_config_arg(pn)
    pn.add_argument("noise_cmd", choices=["fetch", "split", "info"], help="operation")

    pm = sub.add_parser("mix", help="S3: build condition matrix + mix manifest")
    _add_config_arg(pm)
    pm.add_argument("--limit", type=int, default=None)

    pa = sub.add_parser("align", help="S4: run an aligner over the matrix")
    _add_config_arg(pa)
    pa.add_argument("--aligner", required=True, help="aligner name from config registry")
    pa.add_argument("--mode", choices=["A", "B"], default=None, help="input mode")
    pa.add_argument("--limit", type=int, default=None)

    ps = sub.add_parser("score", help="S5: gold + hyp -> metrics")
    _add_config_arg(ps)

    pr = sub.add_parser("run", help="S3->S6 end to end (deterministic)")
    _add_config_arg(pr)
    pr.add_argument("--limit", type=int, default=None)

    prep = sub.add_parser("report", help="S6: leaderboard + curves from scored results")
    _add_config_arg(prep)

    pst = sub.add_parser(
        "selftest",
        help="synthetic oracle-corpus E2E (no restricted data) — exercises "
        "mix->score->report with known-answer metrics",
    )
    pst.add_argument("--out", default="summary/selftest", help="output dir")
    pst.add_argument("--seed", type=int, default=20240607)

    pg = sub.add_parser(
        "gates", help="run all data-independent sanity gates (Plan 7) and report"
    )
    pg.add_argument("--out", default="summary/gates", help="scratch output dir")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version or args.command is None and getattr(args, "version", False):
        from fabench import __version__

        print(f"fabench {__version__}")
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    # The machine's settings, before anything reads a config. Applied HERE and
    # not in the library, so importing fabench never silently absorbs the
    # settings of whatever directory it happens to be imported from.
    from fabench.envfile import load_env_file

    load_env_file()

    if hasattr(args, "config"):
        args.config = _resolve_config(args.config)

    # Lazy dispatch — import the handler only for the chosen command.
    if args.command == "init":
        from fabench import init

        return init.cmd_init(args)
    if args.command == "config":
        return _cmd_config(args)
    if args.command == "ingest":
        from fabench.dataprep.datasets import runner

        return runner.cmd_ingest(args)
    if args.command == "normalize-check":
        from fabench.normalize import check

        return check.cmd_normalize_check(args)
    if args.command == "noise":
        from fabench.noise import runner

        return runner.cmd_noise(args)
    if args.command == "mix":
        from fabench.noise import runner

        return runner.cmd_mix(args)
    if args.command == "align":
        from fabench.aligners import runner

        return runner.cmd_align(args)
    if args.command == "score":
        from fabench.score import runner

        return runner.cmd_score(args)
    if args.command == "run":
        from fabench import pipeline

        return pipeline.cmd_run(args)
    if args.command == "report":
        from fabench.report import runner

        return runner.cmd_report(args)
    if args.command == "selftest":
        from fabench import selftest

        return selftest.cmd_selftest(args)
    if args.command == "gates":
        from fabench import gates

        return gates.cmd_gates(args)

    parser.print_help()
    return 1


def _resolve_config(explicit: str | None) -> str | None:
    """Which config a command should load: ``--config``, else ``$FABENCH_CONFIG``,
    else ``None`` — the composed defaults, which are a complete, valid run.

    There is deliberately no magic filename. A config that is picked up because
    it happens to sit in the working directory makes a command mean different
    things in different checkouts, and the things it used to carry now have
    real owners: staged roots are machine settings (``.fabench.env``), and
    which corpora / systems / scoring a default run uses compose from
    ``datasets/languages/<lang>/``, ``evals/`` and ``fabench/*/``. A run config is now
    only ever a deliberate variant, named on the command line.
    """
    if explicit:
        return explicit
    return os.environ.get("FABENCH_CONFIG") or None


def _cmd_config(args) -> int:
    from fabench.config import load_config

    cfg = load_config(args.config)
    print(f"fabench config: {cfg.path}")
    print(f"  version : {cfg.version}")
    print(f"  scope   : {cfg.scope}")
    print(f"  seeds   : {cfg.seeds}")
    conds = cfg.conditions()
    print(f"  conditions ({len(conds)}): {', '.join(c.name for c in conds)}")
    print("  aligners:")
    for a in cfg.aligners():
        flag = "on " if a.enabled else "off"
        print(
            f"    [{flag}] {a.name:14s} adapter={a.adapter:14s} "
            f"modes={a.modes} conf={a.emits_confidence}"
        )
    print("  gold corpora:")
    for name, spec in cfg.datasets.get("gold", {}).items():
        en = spec.get("enabled") if isinstance(spec, dict) else False
        root = spec.get("root") if isinstance(spec, dict) else None
        status = "staged" if root else "NOT STAGED"
        print(f"    [{'on ' if en else 'off'}] {name:10s} root={root} ({status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
