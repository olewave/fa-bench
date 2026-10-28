# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Who each system is: its display name, its boundary family, its pipeline and
its caveat marker.

The leaderboard and the repro test both name systems this way, so the
definitions live here, beside the recipes.
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path


#: The public recipe each published row of the October 2026 snapshot goes by, where the
#: row was scored under another recipe name. The frozen system outputs behind the
#: snapshot carry those names, and the map to the public ones is kept with them,
#: outside this tree, as a JSON object at $FABENCH_PUBLIC_NAMES. Unset, every name
#: is its own.
def public_name(tool: str) -> str:
    """The name a system is published under."""
    return _public_names().get(tool, tool)


@functools.cache
def _public_names() -> dict[str, str]:
    path = os.environ.get("FABENCH_PUBLIC_NAMES", "")
    return json.loads(Path(path).read_text()) if path else {}


#: Systems whose rows carry a caveat marker in the published table.
#:
#: MAPS only. Its models are `timbuck` = TIMIT + Buckeye with no split
#: discipline, so its evaluation data IS its training data and the row cannot be
#: read as a held-out result -- the one case here where the number does not mean
#: what the column header says.
#:
#: Only MAPS. Training on a corpus and being scored on a speaker-disjoint split
#: of it is the standard every other row here meets, and is not overlap; putting
#: that under the same symbol as train==test collapsed two different situations
#: into one glyph. The overlap section of the methodology page is where the
#: finer distinction belongs, not a warning marker.
class _FlagMap(dict):
    """``name in FLAGGED`` / ``FLAGGED[name]`` also answer for cascade rows.

    A cascade inherits its base aligner's caveat -- MAPS trained on TIMIT, so
    "Qwen3-ASR -> MAPS" carries the same warning MAPS does. Resolving it here
    keeps the seven label sites that consult FLAGGED unchanged.
    """

    def _resolve(self, key: str) -> str | None:
        if dict.__contains__(self, key):
            return key
        parts = cascade_parts(key)
        if parts and dict.__contains__(self, parts[0]):
            return parts[0]
        return None

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._resolve(key) is not None

    def __getitem__(self, key: str) -> str:
        hit = self._resolve(key)
        if hit is None:
            raise KeyError(key)
        return dict.__getitem__(self, hit)


FLAGGED = _FlagMap({"maps": "⚠", "neufa": "⚠", "falcon": "⚠", "deepgram": "‡",
                    "crisperwhisper": "⚠", "crisperwhisper_fa": "⚠"})


#: How each tool is written by its own authors. The tables use these rather
#: than the internal directory slug -- `whisperx` is WhisperX, `mfa` is MFA.
#:
#: No "-FA" suffixes: every system here is a forced aligner, so the suffix
#: carries no information.
#:
#: CrisperWhisper was the exception while the ASR (decoding its own transcript)
#: and the aligner (given the reference) could land in one table. They cannot
#: any more: these pages read summary/aligners/ only, and the ASR lives in
#: summary/timestamp_asrs/, so no block can contain both and the suffix has
#: nothing left to disambiguate from.
DISPLAY = {
    # Meta writes it UnitY2, capital Y. "UnitY" is Unit plus the Y of the
    # two-pass architecture, so Unity2 reads as the game engine.
    "unity2": "UnitY2",
    "falcon": "FALCON",
    # torchaudio ships this as the MMS_FA bundle; the upstream project
    # calls it the MMS forced aligner. "MMS-FA" is the short form both
    # use and it sits at the same width as the other rows.
    "mms_fa": "MMS-FA",
    # NVIDIA's own abbreviation for the tool, and the one its paper uses. The
    # two rows are one aligner over two checkpoints, so they are named by the
    # thing that differs. A frame rate says more here than "FastConformer" and
    # "Conformer" would, and it is the property the pair exists to isolate.
    "nemo_fa": "NeMo-FA 80 ms",
    "nemo_fa_conformer": "NeMo-FA 40 ms",
    # Lowercase, like stable-ts: it is the package name, not a product.
    "whisper_ts": "Whisper-timestamped",

    # COMMERCIAL endpoints. Named product-then-model where the model is itself
    # a product (Nova-3, Universal, Scribe); Google's `latest_long` is a
    # selector rather than a name, so its row carries the service and the
    # recipe carries the model.
    # Every commercial row names the MODEL it ran, not just the vendor. These
    # are endpoints whose contents can change, so the configuration is the only
    # thing a row can honestly claim -- and Deepgram and Google were already
    # named that way, so the other three were the inconsistent ones.
    "deepgram": "Deepgram Nova-3",
    # Named by the checkpoint, as Deepgram names them. What differs
    # besides accuracy is the timestamp grid, 80 ms against 10 ms.
    "deepgram_nova2": "Deepgram Nova-2",
    "assemblyai": "AssemblyAI Universal 3.5",
    "elevenlabs": "ElevenLabs Scribe v2",
    "google_stt": "Google Cloud STT",
    "speechmatics": "Speechmatics enhanced",
    "ibm": "IBM Watson Large",
    # Transcribe selects by language code, not by a named checkpoint, so
    # there is no model name to carry here the way the others have one.
    "aws": "Amazon Transcribe",
    # Azure selects by locale, not by a named checkpoint, so like Amazon
    # there is no model name to carry here.
    "azure": "Azure AI Speech",
    # The pair is named by what differs, as the two NeMo-FA rows are.
    "google_stt_chirp2": "Google Chirp 2",

    "bfa": "BFA",
    "charsiu": "Charsiu",
    "crisperwhisper": "CrisperWhisper",
    "crisperwhisper_fa": "CrisperWhisper",
    "maps": "MAPS",
    "mfa": "MFA 3.4",
    "mfa2": "MFA 2.0",
    "neufa": "NeuFA",
    "pocketsphinx": "PocketSphinx",
    # Only the shipped configurations are named. Describing an internal variant
    # here would disclose the axes of a system whose design is not published.
    "olign": "Olign 0.9",
    # Olign 1.0, the job API. Named apart from 0.9 in every table.
    "olign_v1": "Olign 1.0",
    "olign_v1_asr": "Olign 1.0",
    "parakeet_tdt": "Parakeet-TDT",
    "whisper3": "Whisper large-v3",
    # The row IS a cascade: Qwen3-ASR decodes, Qwen3-ForcedAligner-0.6B times
    # the words it produced. Naming the pair says so on the page instead of
    # only in the recipe, and puts it in the same form as the other two-step
    # rows so a reader can see what differs between them.
    "qwen3_asr": "Qwen3 \u2192 Qwen3-FA",
    "torchaudio_asr": "TorchAudio (ASR)",
    # Same package as the track-1 `whisperx` row, run end to end. Named for what
    # it does rather than reusing "WhisperX", so the two rows cannot be read as
    # one system measured twice.
    "whisperx_asr": "Whisper \u2192 WhisperX",
    "qwen3_fa": "Qwen3-FA",   # the aligner checkpoint, scored on the reference
    "stable_ts": "stable-ts",
    "torchaudio_fa": "TorchAudio",
    "whisperx": "WhisperX",
}


#: Alignment-mechanism family. Classified by how the tool DECIDES BOUNDARIES,
#: not by its encoder -- WhisperX is Whisper (attention) for recognition but
#: aligns with a wav2vec2 CTC model, and FA-Bench measures alignment.
FAMILY = {
    "charsiu": "frame",         # wav2vec2 frame classifier + DP, 10 ms grid
    "maps": "frame",            # neural phone segmentor + interpolation
    "parakeet_tdt": "transducer",   # Token-and-Duration Transducer
    "whisper3": "attention",    # Whisper large-v3, cross-attention DTW times
    "qwen3_asr": "attention",   # Qwen3-ASR, timed by Qwen3-ForcedAligner-0.6B
    "torchaudio_asr": "ctc",    # wav2vec2 CTC greedy decode; spans are CTC frames
    "whisperx_asr": "ctc",      # Whisper decodes, but wav2vec2 CTC sets the times
    "crisperwhisper": "attention",  # Whisper encoder-decoder cross-attention
    "crisperwhisper_fa": "attention",
    "qwen3_fa": "attention",    # Qwen3 transformer
    "stable_ts": "attention",  # Whisper cross-attention + DTW
    # Same mechanism as stable-ts: DTW on Whisper cross-attention heads.
    "whisper_ts": "attention",
    # COMMERCIAL endpoints, all "Closed" for the same reason Olign is: this
    # column names the mechanism that places the boundary, and for these it is
    # not published. Guessing from a vendor blog post would put a label in the
    # table that nothing in the run can support.
    "deepgram": "proprietary",
    "deepgram_nova2": "proprietary",
    "assemblyai": "proprietary",
    "elevenlabs": "proprietary",
    "google_stt": "proprietary",
    "speechmatics": "proprietary",
    "ibm": "proprietary",
    "aws": "proprietary",
    "azure": "proprietary",
    "google_stt_chirp2": "proprietary",
    "neufa": "attention",       # bidirectional attention (not evaluated)
    "bfa": "ctc",               # CUPE + CTC
    "torchaudio_fa": "ctc",     # CTC forced alignment
    # wav2vec2 CTC forced alignment, same mechanism as torchaudio_fa. The
    # difference is the checkpoint: MMS is trained on 1000+ languages over a
    # romanised character vocabulary, which is why it has no phone tier here.
    "mms_fa": "ctc",
    # Viterbi over a NeMo ASR model's CTC posteriors. The encoder is a
    # FastConformer or a Conformer, but what places the boundary is the CTC path.
    "nemo_fa": "ctc",
    "nemo_fa_conformer": "ctc",
    "whisperx": "ctc",          # wav2vec2 phoneme CTC for the ALIGNMENT stage
    # NOT attention, despite the upstream naming. The whole aligner is four
    # nn.Conv1d layers with ReLU and dropout over text and unit embeddings,
    # then a negative L2 distance between every frame and every token,
    # log-softmaxed over the text axis, then Viterbi. There is no attention
    # module in the boundary path at all. That is a per-frame emission decoded
    # by DP, the same shape the charsiu entry above describes. The 1B
    # transformer in UnitY2 runs earlier and only turns audio into units, and
    # the rule above is about what decides boundaries.
    "unity2": "frame",
    # A frame-level boundary scorer with peak detection, differentiable DP in
    # place of a hard argmax. Same mechanism class as charsiu and maps.
    "falcon": "frame",
    "mfa": "hmm",               # Kaldi GMM-HMM + SAT/fMLLR/LDA
    "mfa2": "hmm",
    "pocketsphinx": "hmm",       # Sphinx PTM GMM-HMM, no speaker adaptation
    "olign": "proprietary",
    "olign_v1": "proprietary",
    "olign_v1_asr": "proprietary",
}


#: Displayed family names. Capitalised across the board -- "Frame" beside a
#: lowercase "transducer" reads as a typo, not a distinction.
#:
#: "proprietary" renders as "API", not "Closed" and certainly not "Prpri.".
#: This column names an ARCHITECTURE -- CTC, Frame, HMM, Attention,
#: Transducer -- so answering it with a licence was a category error. Every
#: member reaches its answer the same way, over a network endpoint whose
#: mechanism is not published: Olign, Deepgram, Google, AssemblyAI,
#: ElevenLabs, Speechmatics. "API" states that as a fact about how the row was
#: produced rather than as a judgement about the vendor, and it puts Olign in
#: exactly the same category as the five commercial services rather than in a
#: category of its own -- which is the honest arrangement and also what a
#: reader asking about conflict of interest needs to see.
FAMILY_LABEL = {"frame": "Frame", "transducer": "Transducer",
                "attention": "Attention", "ctc": "CTC", "hmm": "HMM",
                "proprietary": "API"}


def upstream_name(tool: str) -> str:
    """The recogniser's name as it reads on the LEFT of an arrow.

    Step one of a two-step row is a recogniser by definition, so spelling that
    out again in the name is redundant: "Qwen3-ASR -> MFA 3.4" says ASR twice.
    The suffix is dropped in this position only -- the standalone row keeps it
    wherever the tool is named on its own.
    """
    name = DISPLAY.get(tool, tool)
    for suffix in ("-ASR", " (ASR)", " ASR"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name.split(" \u2192 ")[0]      # already a pair: keep its first half


def disp(tool: str) -> str:
    parts = cascade_parts(tool)
    if parts:
        base, asr = parts
        return f"{upstream_name(asr)} \u2192 {disp(base)}"   # decode, then align
    return DISPLAY.get(tool, tool)


#: How a track-2 system gets its timestamps. This is NOT a directory axis: both
#: kinds decode their own words and are scored identically, so they are a fair
#: comparison and belong on one page. It is a column because it explains the
#: numbers -- notably that the best-timed ASR here is the one that is secretly
#: two-step (Qwen3-ASR loads Qwen3-ForcedAligner-0.6B and aligns its own
#: transcript), which is the hypothesis the explicit cascades test.
PIPELINE = {
    "parakeet_tdt": "one-step",     # TDT duration head, times fall out of decoding
    "crisperwhisper": "one-step",   # cross-attention
    "whisper3": "one-step",         # cross-attention DTW
    "whisper_ts": "one-step",       # cross-attention DTW, same decode
    "torchaudio_asr": "one-step",   # CTC frame spans from the same decode
    "whisperx_asr": "two-step",     # Whisper decodes, wav2vec2 re-aligns its words
    "qwen3_asr": "two-step",        # decodes, then aligns with Qwen3-ForcedAligner
    # The commercial endpoints return words and times from one request. Whether
    # a second stage runs server-side is not observable, so "one-step" here
    # means what the interface offers, which is also what a user gets.
    "olign_v1_asr": "one-step",
    "deepgram": "one-step",
    "deepgram_nova2": "one-step",
    "assemblyai": "one-step",
    "elevenlabs": "one-step",
    "google_stt": "one-step",
    "speechmatics": "one-step",
    "ibm": "one-step",
    "aws": "one-step",
    "azure": "one-step",
    "google_stt_chirp2": "one-step",
}


#: A cascade recipe is named "<base>_on_<asr>" -- the base aligner run on the
#: words that ASR decoded. Its properties are not restated per pair: display
#: name, boundary family and any train-on-test flag are inherited from the two
#: halves, so adding a cascade needs no edit here. These aliases bridge the two
#: places a short form is used in a recipe name but not as the recipe's own
#: name.
CASCADE_ALIAS = {"mfa3": "mfa", "qwen3asr": "qwen3_asr",
                 "parakeettdt": "parakeet_tdt",
                 # The recipe is named for the model, not the endpoint: the
                 # tool id google_stt_chirp2 would read as "google stt chirp2"
                 # on the left of an arrow.
                 "chirp2": "google_stt_chirp2"}


def cascade_parts(tool: str) -> tuple[str, str] | None:
    """``("mfa", "qwen3_asr")`` for ``mfa3_on_qwen3asr``; None if not a cascade."""
    if "_on_" not in tool:
        return None
    base, _, asr = tool.partition("_on_")
    return CASCADE_ALIAS.get(base, base), CASCADE_ALIAS.get(asr, asr)


def pipe(tool: str) -> str:
    """one-step / two-step, or '' for a gold-transcript system (always one-step
    by definition: it is handed the words and aligns once)."""
    if cascade_parts(tool):
        return "two-step"          # decode, then align: two models by construction
    return PIPELINE.get(tool, "")


#: Rows that ARE two-step but are not named like one, because the vendor ships
#: both halves as a single product. (aligner, recogniser), matching
#: cascade_parts. Qwen3-ASR loads Qwen3-ForcedAligner to time what it decoded,
#: and WhisperX is Whisper plus its own CTC re-alignment.
INTERNAL_CASCADE = {"qwen3_asr": ("qwen3_fa", "qwen3_asr"),
                    "whisperx_asr": ("whisperx", "whisper3")}


def cascade_halves(tool: str) -> tuple[str, str] | None:
    """``(aligner, recogniser)`` for any two-step row, named like one or not."""
    return cascade_parts(tool) or INTERNAL_CASCADE.get(tool)


def fam_label(tool: str, arrow: str = "\u2192", label: dict | None = None,
              right: dict | None = None) -> str:
    """The Family cell.

    A two-step row names BOTH halves, because one label cannot describe two
    models and the aligner's family alone hid the thing a reader most wants:
    whether the words came from something they can download. So the left of
    the arrow is availability, Open or API, and the right is the aligner's
    architecture -- Open->CTC, Open->API, API->API. The arrow reads the same
    way as in the system name, recogniser then aligner.
    """
    lab = label or FAMILY_LABEL
    h = cascade_halves(tool)
    if h:
        aligner, asr = h
        left = "API" if FAMILY.get(asr) == "proprietary" else "Open"
        rfam = FAMILY.get(aligner, "other")
        # `right` abbreviates the aligner half only. A composite is the widest
        # entry in the column and in the paper it sets the column's width, so
        # "Open -> Attention" can be shortened there without touching the
        # Track 1 rows that simply read "Attention".
        rl = right or lab
        return (f"{left} {arrow} "
                f"{rl.get(rfam) or lab.get(rfam) or FAMILY_LABEL.get(rfam, rfam)}")
    f = fam(tool)
    return lab.get(f, FAMILY_LABEL.get(f, f))


def fam(tool: str) -> str:
    # The ALIGNER decides boundaries, so a cascade sits in its base's family --
    # what the upstream ASR is shows in the name and the Pipeline column.
    parts = cascade_parts(tool)
    if parts:
        return FAMILY.get(parts[0], "other")
    return FAMILY.get(tool, "other")
