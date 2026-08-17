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

"""Config loading + validation (Plan Section 0 is the contract).

A run's settings are COMPOSED, not stored in one file: each subsystem owns its
own defaults (``fabench/config.yaml``, ``fabench/noise/config.yaml``,
``datasets/languages/<lang>/config.yaml``, ``evals/config.yaml``, ``evals/<kind>/<tool>/
config.yaml``, ...), and this module merges them per key, validates the
frozen-scope invariants (additive-noise-only, English, SNR band), and exposes
typed accessors the rest of the pipeline consumes.

Precedence is **run config > environment > composed defaults**, so
``load_config(None)`` is itself a complete, valid run and an optional YAML file
states only what that run CHANGES.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Frozen v0 scope constants (Plan Section 0). Deviating from these should be a
# conscious act (edit the plan first), so we warn/err loudly.
V0_SNR_BAND = {10, 15, 20}
V0_NOISE_TYPES = {"white", "pink", "musan_ambient", "babble"}

# Machine-aligned corpora that are INVALID as gold (Plan 1.3, sanity gate #7):
# their boundaries are themselves forced-alignment output. This is POLICY, not
# configuration — built in so no config copy can silently drop the guard. A
# config's optional `datasets.excluded_as_gold` list EXTENDS it, never shrinks it.
EXCLUDED_AS_GOLD_DEFAULT = (
    "librispeech-alignments",
    "libritts",
    "libritts-r",
    "common-voice-alignments",
    "commonvoice",
    "cmu-arctic",       # EHMM machine alignments
    "mfa-aligned",
)


class ConfigError(ValueError):
    """Raised when a config violates a hard invariant."""


@dataclass
class AlignerSpec:
    name: str
    adapter: str
    enabled: bool
    modes: list[str]
    granularity: list[str]
    emits_confidence: bool
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AlignerSpec:
        return cls(
            name=d["name"],
            adapter=d["adapter"],
            enabled=bool(d.get("enabled", False)),
            modes=list(d.get("modes", [])),
            granularity=list(d.get("granularity", [])),
            emits_confidence=bool(d.get("emits_confidence", False)),
            params=dict(d.get("params", {})),
        )


@dataclass
class Condition:
    name: str
    noise_type: str | None
    snr_db: float | None

    @property
    def is_clean(self) -> bool:
        return self.noise_type is None


@dataclass
class Config:
    raw: dict
    path: Path

    # ---- convenience typed views ----
    @property
    def version(self) -> str:
        return self.raw.get("version", "unknown")

    @property
    def scope(self) -> dict:
        return self.raw.get("scope", {})

    @property
    def seeds(self) -> dict:
        return self.raw.get("seeds", {})

    @property
    def datasets(self) -> dict:
        return self.raw.get("datasets", {})

    @property
    def conditions_raw(self) -> dict:
        return self.raw.get("conditions", {})

    @property
    def normalize(self) -> dict:
        return self.raw.get("normalize", {})

    @property
    def scoring(self) -> dict:
        return self.raw.get("scoring", {})

    @property
    def paths(self) -> dict:
        return self.raw.get("paths", {})

    @property
    def excluded_as_gold(self) -> list[str]:
        extra = self.datasets.get("excluded_as_gold", [])
        return sorted({s.lower() for s in (*EXCLUDED_AS_GOLD_DEFAULT, *extra)})

    def aligners(self, enabled_only: bool = False) -> list[AlignerSpec]:
        specs = [AlignerSpec.from_dict(d) for d in self.raw.get("aligners", [])]
        if enabled_only:
            specs = [s for s in specs if s.enabled]
        return specs

    def aligner(self, name: str) -> AlignerSpec:
        for s in self.aligners():
            if s.name == name:
                return s
        raise KeyError(f"no aligner named {name!r} in config")

    # ---- condition matrix (Plan 3.3) ----
    def conditions(self) -> list[Condition]:
        conds: list[Condition] = []
        if self.conditions_raw.get("include_clean", True):
            conds.append(Condition(name="clean", noise_type=None, snr_db=None))
        for nt in self.conditions_raw.get("noise_types", []):
            for snr in self.conditions_raw.get("snr_db", []):
                conds.append(
                    Condition(
                        name=f"{nt}_snr{int(snr)}",
                        noise_type=nt,
                        snr_db=float(snr),
                    )
                )
        return conds

    def enabled_gold(self) -> Iterator[tuple[str, dict]]:
        for name, spec in self.datasets.get("gold", {}).items():
            if isinstance(spec, dict) and spec.get("enabled", False):
                yield name, spec

    def work_dir(self) -> Path:
        return Path(self.paths.get("work_dir", "data/work"))

    def condition_tag(self) -> str:
        """Noise condition for this run, or "" for clean.

        Set by evals/gen_noisy_configs.py. Keeps a noisy run's hyp and results
        from landing on top of the clean baseline.
        """
        return str(self.raw.get("condition_tag", "") or "")

    def repo_root(self) -> Path:
        """Repo root, for locating evals/<kind>/<tool>/ (see fabench.paths).

        Found by walking UP for the directory that holds both `fabench/` and
        `evals/`, not by a fixed number of `.parent`s: configs live at different
        depths (a variant config anywhere on disk vs `evals/configs/<cell>.yaml`),
        and a fixed count silently resolved to `<root>/evals` for the latter,
        which made every hyp lookup miss and every cell score as empty.
        """
        here = self.path.resolve().parent
        for d in (here, *here.parents):
            if (d / "fabench").is_dir() and (d / "evals").is_dir():
                return d
        return here.parent

    def subset_of(self, corpus: str) -> str:
        """The subset this run evaluates for `corpus` -- part of the hyp path."""
        return str(self.datasets.get("gold", {}).get(corpus, {}).get("subset", "all"))

    def results_dir(self) -> Path:
        """Where derived, cross-tool artefacts go (leaderboards, reports).

        A relative `results_dir` is anchored to `repo_root()`, NOT to
        `path.parent.parent`. The latter is only correct for a config sitting one
        level down; for one at `<root>/evals/configs/` it resolves a level
        short, so `results` would land at `<root>/evals/results`. That was latent
        rather than observed — `evals/gen_config.py` writes an absolute
        `results_dir` — but it is the same defect that broke every hyp lookup
        when `repo_root` used the fixed-depth idiom.
        """
        rd = Path(self.paths.get("results_dir", "summary"))
        if not rd.is_absolute():
            rd = self.repo_root() / rd
        return rd


def is_excluded_gold(path_or_name: str, excluded: list[str]) -> str | None:
    """Return the offending token if ``path_or_name`` looks like a machine-aligned
    corpus banned as gold (Plan 1.3, gate #7); else ``None``.

    Matching is on normalized path tokens so ``/ws/.../LibriTTS-R/...`` trips the
    ``libritts-r`` / ``libritts`` guard.
    """
    hay = str(path_or_name).lower().replace("_", "-")
    for tok in excluded:
        t = tok.lower().replace("_", "-")
        if t in hay:
            return tok
    return None


#: Synthetic path for a configless run. Never opened; it only anchors
#: ``repo_root()`` at the repo providing this package, so ``datasets/`` and
#: ``evals/`` resolve exactly as they would for a real config file.
_COMPOSED_DEFAULTS = "<composed-defaults>"


def load_config(path: str | Path | None = None) -> Config:
    """Load a run config with every subsystem's defaults composed into it.

    ``path=None`` composes the defaults *alone* — a complete, valid run with
    no file at all, because each default lives with the subsystem that owns
    it (scope/seeds/paths in ``fabench/config.yaml``, corpora under
    ``datasets/``, aligners under ``evals/``, and so on). A run config exists to
    state what a run *chooses*, so a run that chooses nothing needs none.
    """
    if path is None:
        raw: dict = {}
        path = Path(__file__).resolve().parents[1] / _COMPOSED_DEFAULTS
    else:
        path = Path(path).resolve()
        if not path.exists():
            raise ConfigError(f"config not found: {path}")
        with open(path) as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ConfigError(f"config root must be a mapping: {path}")
    cfg = Config(raw=raw, path=path)
    _merge_env_overrides(cfg)       # before the defaults: env beats them,
                                    # loses to anything the run config states
    _merge_benchmark_defaults(cfg)  # first: validate() and the normalize
    _merge_dataset_defaults(cfg)    # merge both read scope
    _merge_noise_defaults(cfg)
    _merge_aligner_defaults(cfg)
    _merge_normalize_defaults(cfg)
    _merge_scoring_defaults(cfg)
    validate(cfg)
    return cfg


def _params(path: Path) -> dict:
    """Parse one ``config.yaml`` into a mapping; ``{}`` if absent or malformed.

    Every composition source is optional by design: a bare wheel install, or a
    config outside any repo, simply composes less and the config must then
    carry complete entries (the pre-composition behavior).
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except OSError:
        return {}
    return data if isinstance(data, dict) else {}


def corpus_root_env(corpus: str) -> str:
    """Env var naming a staged corpus root: ``timit`` -> ``FABENCH_TIMIT_ROOT``."""
    return "FABENCH_" + re.sub(r"[^A-Z0-9]+", "_", corpus.upper()) + "_ROOT"


def _merge_env_overrides(cfg: Config) -> None:
    """Apply the ``FABENCH_*`` directory overrides.

    Three things are machine-specific rather than benchmark-specific — where
    the licensed corpora are staged, where bulk intermediates go, and where
    results land — so each can be set once in the environment instead of in
    every config:

    ==========================  ==================================
    ``FABENCH_<CORPUS>_ROOT``   ``datasets.gold.<corpus>.root``
    ``FABENCH_WORK_DIR``        ``paths.work_dir``
    ``FABENCH_RESULTS_DIR``     ``paths.results_dir``
    ==========================  ==================================

    Precedence is **run config > environment > composed defaults**: this runs
    before the defaults merge and uses ``setdefault``, so an explicit value in
    a config always wins (the config is the more specific statement, and a
    sweep must not change meaning because a shell exported something).

    Corpus roots are applied in :func:`_merge_dataset_defaults` instead, where
    the corpus list is known; a root there is only taken from the environment
    when nothing else supplied one.
    """
    paths = cfg.raw.setdefault("paths", {})
    for key, var in (("work_dir", "FABENCH_WORK_DIR"),
                     ("results_dir", "FABENCH_RESULTS_DIR")):
        val = os.environ.get(var)
        if val:
            paths.setdefault(key, val)


def _merge_benchmark_defaults(cfg: Config) -> None:
    """Compose ``scope``, the benchmark-wide seed, and the output paths from
    ``fabench/config.yaml`` — the benchmark-level contract, living beside this
    module, which consumes all three. Merged per key; a run config's ``scope``
    override is scope drift (``validate()`` hard-errors on ``channel``, warns
    on ``language``), while ``seeds.global`` and ``paths`` are legitimate
    per-run knobs."""
    defaults = _params(Path(__file__).resolve().parent / "config.yaml")
    if "version" in defaults:
        cfg.raw.setdefault("version", defaults["version"])
    for section in ("scope", "seeds", "paths"):
        target = cfg.raw.setdefault(section, {})
        for key, val in (defaults.get(section) or {}).items():
            target.setdefault(key, val)


def _merge_dataset_defaults(cfg: Config) -> None:
    """Compose ``datasets.gold`` from each dataset's own folder.

    Two layers live under ``datasets/``, both optional, lowest first:

    * ``datasets/languages/<lang>/<corpus>/config.yaml`` — the corpus's own config
      (beside its split lists): ``root: null``, its default subset, and
      corpus-intrinsic options like ``protocol`` or ``merge_closures``. The
      analogue of ``evals/<kind>/<tool>/config.yaml`` for aligners.
    * ``datasets/languages/<lang>/config.yaml`` — the language's ``gold:`` selection:
      which corpora the benchmark evaluates by default, and on which subset.

    The run config wins over both, per key, which is how ``gen_config.py``
    pins one corpus per cell. Corpora named by neither layer's ``gold:`` are
    still injected (disabled, from their own file), so ``fabench config``
    lists what is available.

    Anchoring: the config file's own repo (``repo_root()``) first, then the
    repo providing this package (editable installs) — so a generated config
    written outside the tree still composes. With neither available (e.g. a
    bare wheel install), the config is left untouched and must carry complete
    entries — the pre-composition behavior.
    """
    from fabench.paths import languages_dir

    droot = languages_dir(cfg.repo_root())
    if not droot.is_dir():
        droot = languages_dir(Path(__file__).resolve().parents[1])
    if not droot.is_dir():
        return

    # Language layer, collected first: <lang>/config.yaml sits at depth 1,
    # corpus files at depth 2, so the two globs cannot collide.
    lang: dict[str, dict] = {}
    for p in sorted(droot.glob("*/config.yaml")):
        for name, spec in (_params(p).get("gold") or {}).items():
            if isinstance(spec, dict):
                lang.setdefault(name, {}).update(spec)

    gold = cfg.raw.setdefault("datasets", {}).setdefault("gold", {})
    for p in sorted(droot.glob("*/*/config.yaml")):
        defaults = _params(p)
        if not defaults:
            continue
        name = p.parent.name
        merged = {**defaults, **lang.get(name, {})}
        user = gold.get(name)
        if isinstance(user, dict):
            merged.update(user)
        # Staged corpus roots are machine-specific and licensed, so they may
        # come from the environment (FABENCH_TIMIT_ROOT, ...) — but only when
        # nothing else supplied one, keeping config > env > default.
        if not merged.get("root"):
            env_root = os.environ.get(corpus_root_env(name))
            if env_root:
                merged["root"] = env_root
        gold[name] = merged


def _merge_noise_defaults(cfg: Config) -> None:
    """Compose noise config from ``fabench/noise/config.yaml``.

    That file lives beside the code that consumes it and ships with the
    package. Its ``sources`` section merges under ``datasets.noise`` (per key
    within each source), ``conditions`` under the top-level ``conditions``,
    and ``seeds`` (the noise split and mix seeds, which belong to this
    subsystem) under the top-level ``seeds``. The run config always wins.
    """
    defaults = _params(Path(__file__).resolve().parent / "noise" / "config.yaml")

    noise = cfg.raw.setdefault("datasets", {}).setdefault("noise", {})
    for source, dspec in (defaults.get("sources") or {}).items():
        merged = dict(dspec) if isinstance(dspec, dict) else dspec
        user = noise.get(source)
        if isinstance(merged, dict) and isinstance(user, dict):
            merged.update(user)
        elif user is not None:
            merged = user
        noise[source] = merged

    for section in ("conditions", "seeds"):
        target = cfg.raw.setdefault(section, {})
        for key, val in (defaults.get(section) or {}).items():
            target.setdefault(key, val)


def _merge_aligner_defaults(cfg: Config) -> None:
    """Compose each ``aligners:`` entry from its canonical tool folder.

    ``evals/<kind>/<tool>/config.yaml`` (beside the tool's install script and
    lock file) is the canonical definition of every aligner, so a run config's
    entry needs only run-scoped keys — typically ``name`` + ``enabled``, plus
    any per-run param overrides. Merge is per key, one level deep into
    ``params``; the run config wins. An entry with no matching folder is left
    untouched and must be complete inline — how a machine-local one-off
    aligner is declared.

    The LIST itself composes from ``evals/config.yaml`` when a run config does
    not state one, the same way ``datasets/languages/<lang>/config.yaml`` supplies the
    default corpora: ``fabench run`` with no config has to mean something, and
    "compare nothing" is not it. A run config that names ``aligners:`` replaces
    the list outright rather than merging into it — a comparison set is a
    single choice, and a half-overridden one would be nobody's intent.
    """
    roots = [cfg.repo_root(), Path(__file__).resolve().parents[1]]
    entries = cfg.raw.get("aligners")
    if not isinstance(entries, list):
        if entries is not None:
            return                     # present but malformed: validate() reports it
        for r in roots:
            default = _params(r / "evals" / "config.yaml").get("aligners")
            if isinstance(default, list):
                entries = cfg.raw["aligners"] = [dict(e) if isinstance(e, dict) else e
                                                 for e in default]
                break
        else:
            return
    kinds = ("aligners", "timestamp_asrs")
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        name = str(entry["name"])
        cands = (r / "evals" / k / name / "config.yaml" for r in roots for k in kinds)
        p = next((c for c in cands if c.is_file()), None)
        if p is None:
            continue
        with open(p) as f:
            defaults = yaml.safe_load(f) or {}
        if not isinstance(defaults, dict):
            continue
        merged = dict(defaults)
        params = dict(defaults.get("params") or {})
        user_params = entry.get("params")
        merged.update(entry)
        if isinstance(user_params, dict):
            params.update(user_params)
        if params:
            merged["params"] = params
        entries[i] = merged


# scope.language value -> language package under fabench/normalize/.
_NORMALIZE_LANG_DIRS = {"english": "en"}


def _merge_normalize_defaults(cfg: Config) -> None:
    """Compose ``normalize`` from the language package's own config.yaml.

    ``fabench/normalize/<lang>/config.yaml`` holds the language's canonical
    inventory choice and the unmapped-rate gate, beside the tables they
    describe. Selected by ``scope.language``; merged per key, run config wins.
    """
    lang = _NORMALIZE_LANG_DIRS.get(str(cfg.scope.get("language", "english")).lower())
    if not lang:
        return
    p = Path(__file__).resolve().parent / "normalize" / lang / "config.yaml"
    if not p.is_file():
        return
    with open(p) as f:
        defaults = yaml.safe_load(f) or {}
    if not isinstance(defaults, dict):
        return
    harm = cfg.raw.setdefault("normalize", {})
    for key, val in defaults.items():
        harm.setdefault(key, val)


def _merge_scoring_defaults(cfg: Config) -> None:
    """Compose ``scoring`` from ``fabench/score/config.yaml``.

    The scoring defaults live beside the scoring engine and ship with the
    package. Merge is per key, one level deep into the ``mfa_paper`` sub-dict;
    the run config wins, so a run states only what it changes
    (``protocol``, ``boundary_unit``, thresholds, ...).
    """
    p = Path(__file__).resolve().parent / "score" / "config.yaml"
    if not p.is_file():
        return
    with open(p) as f:
        defaults = yaml.safe_load(f) or {}
    if not isinstance(defaults, dict):
        return
    scoring = cfg.raw.setdefault("scoring", {})
    for key, val in defaults.items():
        user = scoring.get(key)
        if isinstance(val, dict):
            merged = dict(val)
            if isinstance(user, dict):
                merged.update(user)
            scoring[key] = merged
        else:
            scoring.setdefault(key, val)


def validate(cfg: Config) -> None:
    """Enforce v0 frozen-scope invariants. Hard errors raise; soft drifts warn
    to stderr (the run continues but the deviation is on the record)."""
    import sys

    scope = cfg.scope
    # Hard invariant: additive-noise-only is the whole basis for zero-offset
    # gold transfer (Plan Section 0). Anything else needs the deferred offset
    # machinery, which v0 does not have.
    channel = scope.get("channel")
    if channel != "additive_noise_only":
        raise ConfigError(
            f"v0 requires scope.channel == 'additive_noise_only' (got {channel!r}). "
            "Reverb/codec/far-field need offset correction — deferred to v1 (Plan 8)."
        )

    if scope.get("language") != "english":
        print(
            f"[config] WARNING: scope.language={scope.get('language')!r}; v0 is "
            "English-only (Plan 0).",
            file=sys.stderr,
        )

    # SNR band drift.
    snrs = {int(s) for s in cfg.conditions_raw.get("snr_db", [])}
    if not snrs <= V0_SNR_BAND:
        print(
            f"[config] WARNING: snr_db {sorted(snrs)} outside frozen band "
            f"{sorted(V0_SNR_BAND)} (Plan 0).",
            file=sys.stderr,
        )
    nts = set(cfg.conditions_raw.get("noise_types", []))
    if not nts <= V0_NOISE_TYPES:
        print(
            f"[config] WARNING: noise_types {sorted(nts)} outside frozen set "
            f"{sorted(V0_NOISE_TYPES)} (Plan 0).",
            file=sys.stderr,
        )

    # Excluded-gold guard on any pointed gold roots (gate #7).
    excluded = cfg.excluded_as_gold
    for name, spec in cfg.datasets.get("gold", {}).items():
        root = spec.get("root") if isinstance(spec, dict) else None
        if root:
            hit = is_excluded_gold(root, excluded)
            if hit:
                raise ConfigError(
                    f"gold corpus {name!r} points at {root!r} which matches banned "
                    f"machine-aligned source {hit!r}. These are forced/MFA alignments, "
                    "invalid as ground truth (Plan 1.3)."
                )

    # At least one enabled gold corpus, else nothing to score.
    if not list(cfg.enabled_gold()):
        print(
            "[config] WARNING: no gold corpus enabled — only synthetic/self-test "
            "runs are possible.",
            file=sys.stderr,
        )
