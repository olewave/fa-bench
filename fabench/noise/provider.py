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

"""Unified noise source (Plan 1.4). Hides where a segment comes from so the
manifest builder is testable with synthetic pools."""

from __future__ import annotations

from pathlib import Path

from fabench.noise import musan, synth


class NoiseProvider:
    def __init__(
        self,
        musan_noise_eval: list[Path] | None = None,
        musan_speech_eval: list[Path] | None = None,
        babble_min_sources: int = 6,
        sr: int = 16000,
    ):
        self.noise_eval = musan_noise_eval or []
        self.speech_eval = musan_speech_eval or []
        self.babble_min_sources = babble_min_sources
        self.sr = sr

    @classmethod
    def from_config(cls, cfg) -> NoiseProvider:
        spec = cfg.datasets.get("noise", {}).get("musan", {})
        noise_eval = speech_eval = []
        if spec.get("enabled", False):
            root = musan.ensure_musan(cfg)
            seed = int(cfg.seeds.get("noise_split", 0))
            _, noise_eval = musan.held_out_split(musan.list_files(root, "noise"), seed)
            _, speech_eval = musan.held_out_split(musan.list_files(root, "speech"), seed)
        return cls(
            musan_noise_eval=noise_eval,
            musan_speech_eval=speech_eval,
            babble_min_sources=int(spec.get("babble_min_sources", 6)),
        )

    def segment(self, noise_type: str, length: int, seed: int):
        """Return (segment float64[length], source_file:str, offset_s:float)."""
        if noise_type in ("white", "pink"):
            return synth.generate(noise_type, length, seed), f"synthetic:{noise_type}", 0.0
        if noise_type == "musan_ambient":
            if not self.noise_eval:
                raise RuntimeError("musan_ambient requested but MUSAN not available")
            return musan.get_ambient(self.noise_eval, length, seed, self.sr)
        if noise_type == "babble":
            if not self.speech_eval:
                raise RuntimeError("babble requested but MUSAN speech not available")
            return musan.build_babble(
                self.speech_eval, length, seed, self.babble_min_sources, self.sr
            )
        raise ValueError(f"unknown noise_type {noise_type!r}")
