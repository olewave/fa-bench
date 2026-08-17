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

"""Phone-set mapping tables into CANONICAL_39 (Plan S2).

Every table maps a source label to a canonical symbol, or to ``None`` meaning
"intentionally deleted" (e.g. glottal stop ``q``, which the standard TIMIT
folding drops). A source label absent from its table is *unmappable* — surfaced
and counted, never silently dropped (Plan S2 acceptance).
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------
# TIMIT-61 -> 39 (Lee & Hon 1989 / Kaldi phones.60-48-39.map, 39-col).
# None = deleted by the standard folding.
# --------------------------------------------------------------------------
TIMIT61_TO_39: dict[str, str | None] = {
    "aa": "aa", "ao": "aa",
    "ae": "ae",
    "ah": "ah", "ax": "ah", "ax-h": "ah",
    "aw": "aw",
    "ay": "ay",
    "b": "b", "bcl": "sil",
    "ch": "ch",
    "d": "d", "dcl": "sil",
    "dh": "dh",
    "dx": "dx",
    "eh": "eh",
    "el": "l",
    "em": "m",
    "en": "n", "nx": "n",
    "eng": "ng",
    "epi": "sil",
    "er": "er", "axr": "er",
    "ey": "ey",
    "f": "f",
    "g": "g", "gcl": "sil",
    "hh": "hh", "hv": "hh",
    "ih": "ih", "ix": "ih",
    "iy": "iy",
    "jh": "jh",
    "k": "k", "kcl": "sil",
    "l": "l",
    "m": "m",
    "n": "n",
    "ng": "ng",
    "ow": "ow",
    "oy": "oy",
    "p": "p", "pcl": "sil",
    "pau": "sil", "h#": "sil", "epi ": "sil",
    "q": None,  # glottal stop: deleted by the standard folding
    "r": "r",
    "s": "s",
    "sh": "sh", "zh": "sh",
    "t": "t", "tcl": "sil",
    "th": "th",
    "uh": "uh",
    "uw": "uw", "ux": "uw",
    "v": "v",
    "w": "w",
    "y": "y",
    "z": "z",
}

# --------------------------------------------------------------------------
# ARPABET (MFA english_us_arpa, torchaudio phoneme models, L2-ARCTIC) -> 39.
# Stress digits are stripped before lookup.
# --------------------------------------------------------------------------
ARPABET_TO_39: dict[str, str | None] = {
    "aa": "aa", "ao": "aa",
    "ae": "ae",
    "ah": "ah", "ax": "ah",
    "aw": "aw",
    "ay": "ay",
    "b": "b",
    "ch": "ch",
    "d": "d",
    "dh": "dh",
    "dx": "dx",
    "eh": "eh",
    "er": "er", "axr": "er",
    "ey": "ey",
    "f": "f",
    "g": "g",
    "hh": "hh",
    "ih": "ih", "ix": "ih",
    "iy": "iy",
    "jh": "jh",
    "k": "k",
    "l": "l", "el": "l",
    "m": "m", "em": "m",
    "n": "n", "en": "n", "nx": "n",
    "ng": "ng", "eng": "ng",
    "ow": "ow",
    "oy": "oy",
    "p": "p",
    "r": "r",
    "s": "s",
    "sh": "sh", "zh": "sh",
    "t": "t",
    "th": "th",
    "uh": "uh",
    "uw": "uw", "ux": "uw",
    "v": "v",
    "w": "w",
    "y": "y",
    "z": "z",
    # non-speech tokens emitted by MFA/CTC/MAPS/Charsiu
    "sil": "sil", "sp": "sil", "spn": "sil", "": "sil", "h#": "sil", "pau": "sil",
    "[sil]": "sil", "[noise]": "sil", "[unk]": None, "[pad]": None,
}

# --------------------------------------------------------------------------
# Buckeye -> 39. Buckeye's phonetic tier is ARPABET-like with flaps, syllabics,
# glottal stop (tq), nasal flap (nx), and non-speech markers.
# --------------------------------------------------------------------------
BUCKEYE_TO_39: dict[str, str | None] = {
    **ARPABET_TO_39,
    "dx": "dx", "nx": "n",
    "tq": None,   # glottal stop allophone of /t/: deleted (analogous to q)
    "en": "n", "em": "m", "eng": "ng", "el": "l",
    # non-speech / silence markers (various Buckeye conventions). Both the
    # raw Buckeye spellings and the kaldi swbd word forms the ingest now
    # emits (see fabench/ingest/buckeye.py:KALDI_TAG) -- keep BOTH, so
    # previously staged data still normalizes.
    "sil": "sil", "SIL": "sil", "!sil": "sil",
    "noise": "sil", "NOISE": "sil", "[noise]": "sil",
    "vocnoise": "sil", "VOCNOISE": "sil", "[vocalized-noise]": "sil",
    "laugh": "sil", "LAUGH": "sil", "[laughter]": "sil",
    "unknown": None, "UNKNOWN": None,
    "iver": None, "IVER": None,   # interviewer overlap: exclude
    "<exclude-name>": None, "excluded": None,
}

# --------------------------------------------------------------------------
# IPA (Charsiu en model) -> 39. Best-effort over the common English IPA symbols;
# unmapped symbols are counted (Charsiu is off by default).
# --------------------------------------------------------------------------
IPA_TO_39: dict[str, str | None] = {
    # vowels
    "i": "iy", "iː": "iy", "ɪ": "ih", "e": "ey", "eɪ": "ey", "ɛ": "eh",
    "æ": "ae", "ə": "ah", "ʌ": "ah", "ɐ": "ah", "ɑ": "aa", "ɑː": "aa",
    "ɒ": "aa", "ɔ": "aa", "ɔː": "aa", "o": "ow", "oʊ": "ow", "əʊ": "ow",
    "ʊ": "uh", "u": "uw", "uː": "uw", "aɪ": "ay", "aʊ": "aw", "ɔɪ": "oy",
    "ɝ": "er", "ɚ": "er", "ɜ": "er", "ɜː": "er", "ɹ̩": "er",
    # consonants
    "p": "p", "b": "b", "t": "t", "d": "d", "k": "k", "g": "g", "ɡ": "g",
    "tʃ": "ch", "dʒ": "jh", "f": "f", "v": "v", "θ": "th", "ð": "dh",
    "s": "s", "z": "z", "ʃ": "sh", "ʒ": "sh", "h": "hh",
    "m": "m", "n": "n", "ŋ": "ng", "l": "l", "ɫ": "l", "r": "r", "ɹ": "r",
    "w": "w", "j": "y", "ʔ": None, "ɾ": "dx", "ˈ": None, "ˌ": None,
    # espeak r-colored (rhotic) vowels -> rhotic 'er' (BFA/espeak G2P)
    "ɑːɹ": "er", "ʊɹ": "er", "ɔːɹ": "er", "ɪɹ": "er", "oːɹ": "er", "ɛɹ": "er",
    "aɪɚ": "er", "ɑɹ": "er", "ɔɹ": "er", "ɜːɹ": "er", "əɹ": "er", "ʊəɹ": "er",
    "ɛəɹ": "er", "ɪəɹ": "er", "aʊɹ": "er",
    # syllabic consonants
    "əl": "l", "l̩": "l", "n̩": "n", "m̩": "m", "ŋ̍": "ng",
    # other espeak vowels / near-diphthongs collapsed to the closest monophthong
    "ᵻ": "ih", "ɨ": "ih", "iə": "iy", "oː": "ow", "aɪə": "ay", "eə": "eh",
    "ʉ": "uw", "tʃɹ": "ch",
    # espeak clause/phone-boundary marker: not a phone -> delete
    "-": None,
    # silence
    "sil": "sil", "sp": "sil", "spn": "sil", "": "sil", "[SIL]": "sil",
}

_STRESS = re.compile(r"[0-2]$")


def norm_arpabet(label: str) -> str:
    """Lowercase and strip a trailing stress digit (AH0 -> ah)."""
    return _STRESS.sub("", label.strip().lower())


def norm_timit(label: str) -> str:
    return label.strip().lower()


def norm_buckeye(label: str) -> str:
    # keep case for the marker set; ARPABET part is lowercased on lookup
    return label.strip()


def norm_ipa(label: str) -> str:
    return label.strip()
