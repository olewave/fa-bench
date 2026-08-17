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

"""Buckeye ingestion (Plan S1).

Buckeye gold: ``.phones`` / ``.words`` list **cumulative end-times in seconds**
after a ``#`` header; a segment spans previous_end -> this_end. Tracks are long
spontaneous interviews, so we segment each into utterance-sized chunks at silence
/ interviewer breaks and (when audio is present) write per-chunk WAV slices so
the downstream pipeline stays uniform (one audio file per utterance).
"""

from __future__ import annotations

import re
from pathlib import Path

from fabench.schema import Interval, Utterance

# word-tier tokens that are NOT subject speech (segment breaks / exclusions)
_BREAK_PREFIXES = ("<", "{")
_BREAK_LABELS = {"sil", "noise", "vocnoise", "laugh", "unknown", "iver",
                 "exclude"}


def is_break(label: str) -> bool:
    lab = label.strip()
    if lab.startswith(_BREAK_PREFIXES):
        return True
    return lab.lower() in _BREAK_LABELS


# ---------------------------------------------------------------------------
# Buckeye hides real speech inside laughter / vocal-noise tags. `<LAUGH-it>` is
# the word "it" said while laughing; `<LAUGH-open_that>` is two words;
# `<LAUGH=because_it_changes>` is three. Across the corpus: 1,552 tokens
# carrying 2,713 words and 14.4 minutes of speech. The PHONE tier segments them
# normally -- `<LAUGH=because_it_changes>` is 12 lowercase phones -- so any
# protocol that segments on the phone tier includes that audio while the word
# tier reports only an opaque marker, handing the aligner speech its transcript
# cannot explain. Measured on 10 speakers, that hit 177 utterances under
# `protocol='paper'` (0 under 'fabench', which segments on the word tier).
#
# `<IVER-um>` is deliberately NOT recoverable: that is the interviewer, not the
# subject, so it stays a break.
#
# EXT, HES and NOISE carry a real word the same way: `<EXT-I've>` is "I've"
# said with lengthening, `<HES-familiarity>` is "familiarity" produced
# hesitantly, `<NOISE-talking>` is "talking" over background noise. All are
# segmented normally on the PHONE tier -- `<EXT-I've>` is `ay v`,
# `<HES-familiarity>` 12 lowercase phones, `<NOISE-registering>` is
# `r eh jh ih s ch r ih ng` -- so the same argument applies: a phone-tier
# protocol includes that audio while the word tier shows only a marker.
#
# Checked against the phone tier corpus-wide: 100% of the 710 `<NOISE-...>`
# tokens carry real phones (EXT/HES 100%, LAUGH/VOCNOISE 98%), at 3.85 phones
# per payload word against 3.26 for ordinary words. Bare `<NOISE>` has no
# payload, does not match this pattern, and stays a kaldi `[noise]` event.
#
# ERROR and CUTOFF are NOT here, and must not be: their payload is
# `realized=intended` (`<ERROR-allowings=allowing>`, `<CUTOFF-pick=picked>`),
# so the text before `=` is what was actually said and no lexicon holds it.
# They are disqualifiers instead -- see _EXCLUDE_WORD_RE.
_HIDDEN_RE = re.compile(r"^<(LAUGH|VOCNOISE|EXT|HES|NOISE)[-=](.+)>$", re.IGNORECASE)

# Buckeye's four surviving event tags, renamed to kaldi's swbd word forms
# (`egs/swbd/s5c/local/swbd1_prepare_dict.sh:45`):
#
#     !sil sil | [vocalized-noise] spn | [noise] nsn | [laughter] lau | <unk> spn
#
# VOCNOISE is breath/cough/throat-clear, exactly what kaldi pools into `spn`,
# so it takes the `[vocalized-noise]` word form. Applied when EMITTING phone
# intervals only -- `_is_nonspeech_phone()` classifies on the raw all-caps
# labels during segmentation, and renaming before that would make these read
# as speech.
KALDI_TAG = {
    "SIL": "!sil",                    # phone sil
    "VOCNOISE": "[vocalized-noise]",  # phone spn
    "NOISE": "[noise]",               # phone nsn
    "LAUGH": "[laughter]",            # phone lau
}


def kaldi_tag(label: str) -> str:
    """Buckeye event tag -> kaldi word form; anything else unchanged."""
    return KALDI_TAG.get(label.strip().upper(), label)


def hidden_words(label: str) -> list[str] | None:
    """Words buried in a `<LAUGH-...>` / `<VOCNOISE-...>` tag, else None."""
    m = _HIDDEN_RE.match(label.strip())
    if not m:
        return None
    # A payload containing `=` is a realized=intended pair, not a word list.
    # No tag matched above uses that form today; the guard is here so adding
    # one later cannot silently turn "allowings=allowing" into two words.
    if "=" in m.group(2):
        return None
    return [w for w in re.split(r"[_-]", m.group(2)) if w] or None


def _has_real_phone(phones: list[Interval], start: float, end: float) -> bool:
    """Does the PHONE tier put at least one real phone inside [start, end)?

    Buckeye writes real phones in lowercase and every event in caps or
    brackets, so this is a reliable test for "there is speech here".
    """
    for p in phones:
        if p.end <= start or p.start >= end:
            continue
        lab = p.label.strip()
        if lab and lab[0].islower():
            return True
    return False


def _recovered(w: Interval, phones: list[Interval]) -> Interval | None:
    """A hidden-word tag as a gold word interval, or None.

    A single-word tag has an exact span, so it becomes an ordinary gold word.
    A multi-word tag keeps ONE interval labelled with all its words: the outer
    span is known but the internal splits are not, and fabricating them would
    corrupt gold word-boundary scoring. Scoring aligns labels with
    Needleman-Wunsch and only scores matched pairs, so a multi-word label
    simply goes unmatched and contributes nothing -- while the transcript,
    built by joining labels, still says what was actually spoken.

    THE PHONE TIER HAS THE CASTING VOTE. Recovery exists because the word tier
    hides speech the phone tier segments; where the phone tier holds no speech,
    there is nothing to recover and naming a word would invert the very failure
    this fixes -- a transcript with no audio instead of audio with no
    transcript. 35 of 4,183 tags corpus-wide are that shape, and they are
    exactly the ones that should not be trusted:

        <LAUGH-here>        1.15 s, phone tier: LAUGH
        <LAUGH-no>          0.52 s, phone tier: LAUGH
        <VOCNOISE=I>        0.33 s, phone tier: VOCNOISE
        <LAUGH-word_word>   a literal placeholder, 4 occurrences
        <LAUGH-UNKNOWN>     the transcriber marking that they could not tell

    Contrast <VOCNOISE-right>, which keeps its recovery: the tag describes the
    surrounding condition (a backchannel inside an interviewer turn), while the
    phone tier carries `r ey tq` -- 277 ms of genuine speech.
    """
    ws = hidden_words(w.label)
    if not ws:
        return None
    if not _has_real_phone(phones, w.start, w.end):
        return None
    return Interval(" ".join(ws), w.start, w.end)


# ---------------------------------------------------------------------------
# Paper-faithful segmentation (arXiv:2606.18466). Non-speech phone-tier tokens:
# SIL / IVER (interviewer) / VOCNOISE / NOISE / LAUGH / UNKNOWN / EXCLUDE and the
# {B_TRANS}/{E_TRANS} markers. Real Buckeye phones are lowercase, so any all-caps
# or bracketed token is non-speech.
# ---------------------------------------------------------------------------
_NONSPEECH_PHONES = {
    "SIL", "IVER", "VOCNOISE", "NOISE", "LAUGH", "UNKNOWN", "EXCLUDE", "SPN", "TRANS",
}
# word-tier markers that disqualify an utterance ("unknown, cutoff, or excised").
#
# ERROR joins them: `<ERROR-allowings=allowing>` records that the speaker said
# "allowings" while meaning "allowing". The realized form is what is in the
# audio and no lexicon has it, while the intended form is not what was said --
# so neither is a transcript an aligner can be scored against. Same reasoning
# as cutoff, which Buckeye writes in the identical `realized=intended` shape.
# 70 tokens over the first 6 speakers.
_EXCLUDE_WORD_RE = re.compile(r"(unknown|cutoff|exclud|excis|error)", re.IGNORECASE)

# A bracketed tag whose PAYLOAD carries a second `=` is a realized=intended
# pair whatever its name is spelt like, and neither side is a transcript worth
# scoring (see above). Catching the shape rather than the name covers the
# corpus's typos without hardcoding them: `<CUTFF-s=seem>` is the one
# misspelling that `_EXCLUDE_WORD_RE` misses.
#
# `<LAUGH=because_it_changes>` is deliberately NOT matched: there the `=` is
# the SEPARATOR and the payload holds no second one.
_REALIZED_INTENDED_RE = re.compile(r"^<[A-Za-z_]+[-=][^>]*=")


def disqualifies(label: str) -> bool:
    """Does this word-tier label make its utterance unscoreable?"""
    return bool(_EXCLUDE_WORD_RE.search(label)
                or _REALIZED_INTENDED_RE.match(label.strip()))


def _is_sil(label: str) -> bool:
    return label.strip().upper() == "SIL"


def _is_nonspeech_phone(label: str) -> bool:
    lab = label.strip()
    if not lab or lab[0] in "<{":
        return True
    if lab.upper() in _NONSPEECH_PHONES:
        return True
    return lab.isupper()  # real phones are lowercase; any caps token is a marker


def _is_word_marker(label: str) -> bool:
    lab = label.strip()
    return (not lab) or lab[0] in "<{"


def _sil_left_s(phones: list[Interval], i: int) -> float:
    """Seconds of contiguous silence immediately before phones[i] (paddable)."""
    t = phones[i].start
    j = i - 1
    while j >= 0 and _is_sil(phones[j].label):
        t = phones[j].start
        j -= 1
    return phones[i].start - t


def _sil_right_s(phones: list[Interval], i: int, track_end: float | None) -> float:
    """Seconds of contiguous silence immediately after phones[i] (paddable)."""
    n = len(phones)
    t = phones[i].end
    j = i + 1
    while j < n and _is_sil(phones[j].label):
        t = phones[j].end
        j += 1
    if j >= n and track_end is not None:
        t = max(t, track_end)
    return t - phones[i].end


def segment_track_paper(
    words: list[Interval],
    phones: list[Interval],
    *,
    sil_split_s: float = 0.300,
    pad_s: float = 0.200,
    min_words: int = 4,
    track_end: float | None = None,
):
    """Segment a track per the MFA-2026 paper (arXiv:2606.18466).

    Cut the recording at silences >= ``sil_split_s`` and at every non-silence
    non-speech interval (interviewer, noise, laugh, ...); silences shorter than
    ``sil_split_s`` stay inside an utterance. Pad each utterance by up to
    ``pad_s`` seconds of the *real* adjacent silence on each side. Drop
    utterances with fewer than ``min_words`` real words or containing any
    unknown/cutoff/excised word. Yields ``(t0_pad, t1_pad, words_rebased,
    phones_rebased)`` with times rebased to ``t0_pad``.
    """
    # classify each phone: S=speech, s=short silence (soft), H=hard break
    klass = []
    for p in phones:
        if not _is_nonspeech_phone(p.label):
            klass.append("S")
        elif _is_sil(p.label) and (p.end - p.start) < sil_split_s:
            klass.append("s")
        else:
            klass.append("H")

    out = []
    n = len(phones)
    i = 0
    while i < n:
        if klass[i] == "H":
            i += 1
            continue
        # maximal block of S/s
        j = i
        while j < n and klass[j] != "H":
            j += 1
        block = list(range(i, j))
        i = j
        s_idx = [k for k in block if klass[k] == "S"]
        if not s_idx:
            continue
        first, last = s_idx[0], s_idx[-1]
        s0, s1 = phones[first].start, phones[last].end
        run = phones[first : last + 1]  # speech + internal short silences

        overlapping = [w for w in words if w.end > s0 and w.start < s1]
        # Recover words hidden in <LAUGH-...>/<VOCNOISE-...>. This protocol
        # segments on the PHONE tier, where those spans are ordinary lowercase
        # phones, so their audio is already inside the utterance -- omitting
        # them from the transcript hands the aligner speech it cannot explain.
        real = []
        for wd in overlapping:
            if not _is_word_marker(wd.label):
                real.append(wd)
                continue
            rec = _recovered(wd, phones)
            if rec is not None:
                real.append(rec)
        if len(real) < min_words:
            continue
        if any(disqualifies(w.label) for w in overlapping):
            continue

        pad_l = min(pad_s, _sil_left_s(phones, first))
        pad_r = min(pad_s, _sil_right_s(phones, last, track_end))
        t0 = max(0.0, s0 - pad_l)
        t1 = s1 + pad_r
        cwords = [Interval(w.label, w.start - t0, w.end - t0) for w in real]
        cphones = [Interval(kaldi_tag(p.label), p.start - t0, p.end - t0)
                   for p in run]
        out.append((t0, t1, cwords, cphones))
    return out


# ---------------------------------------------------------------------------
# Buckeye's .words rows carry FOUR fields, of which parse_tier keeps only the
# first:
#
#     0.400000  121 the; dh ah; dh ah; DT
#                   ^word ^canonical ^realized ^POS
#
# The canonical/realized split is the corpus's whole point, and it is what
# makes the benchmark's headline numbers narrower than they look. An aligner
# is driven by a lexicon, which supplies the CANONICAL pronunciation; the gold
# .phones tier records what was REALIZED. When they differ, the scorer's
# Needleman-Wunsch pass drops the unmatched phones, so those boundaries never
# enter the MAE at all.
#
# Measured: 58.7% of Buckeye word tokens are realized differently from their
# canonical form, and 17.0% of gold phones are never scored as a result
# (13.8% on TIMIT). The discarded set is the flaps, deletions, devoicings and
# assimilations -- exactly where an aligner is forced to place a phone the
# audio does not contain. See olign md/Findings.md.
#
# Capturing both fields lets a report say how much of a result rests on
# canonically-pronounced words, and lets a run stratify or filter on it.
def parse_words_pron(path: Path) -> dict[int, tuple[str, str]]:
    """Index in `parse_tier(path)` -> (canonical, realized) pronunciation.

    Only rows that carry both are included, so markers (`<SIL>`, `<IVER>`,
    ...) and rows whose fields are `U` (unknown -- the annotator recorded
    that speech happened, not what it was) are absent. Keyed by index so it
    lines up with the Interval list without changing that structure.
    """
    out: dict[int, tuple[str, str]] = {}
    for i, (parts, _) in enumerate(_rows(path)):
        if len(parts) < 4:
            continue
        canon, real = parts[1].strip(), parts[2].strip()
        if not canon or not real or canon == "U" or real == "U":
            continue
        out[i] = (canon, real)
    return out


def is_canonical(canon: str, real: str) -> bool:
    """Whether the word was pronounced as its lexicon entry says."""
    return canon.split() == real.split()


def _rows(path: Path):
    """(semicolon-split fields, end_time) for each data row, in order."""
    lines = Path(path).read_text(errors="replace").splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "#":
            start = i + 1
            break
    for ln in lines[start:]:
        if not ln.strip():
            continue
        parts = ln.split(None, 2)
        try:
            end_t = float(parts[0])
        except (ValueError, IndexError):
            continue
        rest = parts[2] if len(parts) > 2 else ""
        yield rest.split(";"), end_t


def parse_tier(path: Path) -> list[Interval]:
    """Parse a .phones/.words file into intervals (cumulative end -> spans)."""
    lines = Path(path).read_text(errors="replace").splitlines()
    # header ends at the first line that is exactly '#'
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "#":
            start = i + 1
            break
    ivs: list[Interval] = []
    prev_end = 0.0
    for ln in lines[start:]:
        if not ln.strip():
            continue
        parts = ln.split(None, 2)  # end_time, code, rest
        try:
            end_t = float(parts[0])
        except (ValueError, IndexError):
            continue
        rest = parts[2] if len(parts) > 2 else ""
        label = rest.split(";")[0].strip()
        if not label and len(parts) > 1:
            label = parts[1]
        ivs.append(Interval(label=label, start=prev_end, end=end_t))
        prev_end = end_t
    return ivs


def segment_track(
    words: list[Interval],
    phones: list[Interval],
    *,
    min_chunk_s: float = 0.5,
    min_phones: int = 3,
):
    """Split a track into (t0, t1, chunk_words, chunk_phones), rebased to t0.

    Chunks are maximal runs of subject-speech words; breaks (silence, noise,
    interviewer) terminate a chunk.
    """
    chunks = []
    cur: list[Interval] = []

    def flush():
        if not cur:
            return
        t0, t1 = cur[0].start, cur[-1].end
        cwords = [Interval(w.label, w.start - t0, w.end - t0) for w in cur]
        cphones = [
            Interval(kaldi_tag(p.label), p.start - t0, p.end - t0)
            for p in phones
            if p.start >= t0 - 1e-6 and p.end <= t1 + 1e-6
        ]
        if (t1 - t0) >= min_chunk_s and len(cphones) >= min_phones:
            chunks.append((t0, t1, cwords, cphones))

    for w in words:
        if is_break(w.label):
            flush()
            cur = []
        else:
            cur.append(w)
    flush()
    return chunks


#: Splits live as data: datasets/languages/en/buckeye/split/<subset>.list, one
#: "<speaker_id> <utterance_id>" per line. Buckeye ships NO official split, so
#: these are a FA-Bench convention -- 60/20/20 by speaker, stratified on the
#: corpus's own design axes (sex x age; see datasets/languages/en/buckeye/speakers.tsv,
#: transcribed from the corpus manual Table 1). 60/20/20 divides the 4x10
#: design exactly: every cell contributes 6 train / 2 dev / 2 test.
from fabench.paths import split_dir as _splits_for


def _repo_root() -> Path:
    """Walk UP for the dir holding both ``fabench/`` and ``datasets/``.

    NOT a fixed ``parents[N]``: this file has already moved once
    (``fabench/dataprep/en/`` -> ``fabench/dataprep/datasets/en/``) and the
    extra level silently made ``parents[4]`` resolve to ``fabench/`` instead of
    the repo root, so the split list was not found and the ingest fell back to
    the whole corpus rather than the requested subset. Depth-counting breaks
    silently on any move; searching does not.
    """
    for d in Path(__file__).resolve().parents:
        if (d / "fabench").is_dir() and (d / "datasets").is_dir():
            return d
    raise RuntimeError("cannot locate repo root (needs fabench/ and datasets/)")


_SPLIT_DIR = _splits_for(_repo_root(), "en", "buckeye")
_SUBSETS = ("train", "dev", "test")


def _load_split(subset: str) -> set[str]:
    """Speaker ids for ``subset`` (membership is by speaker, so slicing the
    tracks is unaffected by which utterance segmentation is in force)."""
    path = _SPLIT_DIR / f"{subset}.list"
    if not path.is_file():
        raise FileNotFoundError(
            f"Buckeye split list {path} not found. The .list files define the "
            f"splits and are tracked in the repo; see datasets/languages/en/buckeye/split/."
        )
    return {ln.split()[0] for ln in path.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")}


def iter_utterances(
    root: Path,
    work_dir: Path,
    *,
    write_slices: bool = True,
    protocol: str = "fabench",
    subset: str | None = None,
):
    """Yield segmented Buckeye Utterances. Writes per-chunk WAV slices under
    ``work_dir/buckeye_audio`` when the track WAV is available.

    ``protocol='paper'`` uses the MFA-2026 segmentation (300 ms-silence split,
    200 ms padding, >=4-word filter); ``'fabench'`` (default) uses the native
    split-at-every-break segmentation.

    ``subset`` in {train, dev, test} restricts to that split's speakers, read
    from datasets/languages/en/buckeye/split/<subset>.list. ``None`` (default) yields all
    40 speakers -- the whole-corpus protocol used for published comparisons.

    Split membership is by SPEAKER, so it is independent of ``protocol``: the
    two segmentations cut the same tracks into different utterances, but a
    speaker is wholly inside one split either way.
    """

    from fabench.audio import read_audio, write_audio

    root = Path(root)
    if subset is not None and subset not in _SUBSETS:
        raise ValueError(f"unknown Buckeye subset {subset!r}; "
                         f"choose from {sorted(_SUBSETS)} or None for all 40")
    wanted = _load_split(subset) if subset else None
    phone_files = sorted(root.rglob("*.phones"))
    if wanted is not None:
        # sNN/sNNNNx/sNNNNx.phones -> speaker id is the first 3 chars of the stem
        phone_files = [p for p in phone_files if p.stem[:3] in wanted]
    if not phone_files:
        raise FileNotFoundError(
            f"No .phones files under {root}. Expected Buckeye layout "
            f"{root}/sNN/sNNNNx/sNNNNx.phones (+ .words, .wav)."
        )
    # Slices MUST be keyed by the SOURCE ROOT, not just utt_id.
    #
    # This was a flat `buckeye_audio/<utt_id>.wav` shared by every ingest, so a
    # noise-augmented run reading a shadow root OVERWROTE the clean slices in
    # place and any clean eval afterwards silently read noisy audio. Observed:
    # torchaudio_fa's buckeye/test went from 47.5 ms to 394 ms word MAE with
    # every boundary displaced by a constant ~0.465 s -- the noisy recordings
    # carry the gold-prep recipe's wav.scp `adelay=475` pad, so slicing at gold offsets
    # from a padded recording lands 475 ms late. Nothing errored; the numbers
    # were just wrong, in a plausible-looking way.
    #
    # The digest mirrors how _variant_tag discriminates the ingest caches, so
    # slices and caches stay consistent with each other.
    import hashlib

    _root_tag = hashlib.sha1(str(Path(root).resolve()).encode()).hexdigest()[:8]
    audio_out = Path(work_dir) / f"buckeye_audio__{_root_tag}"
    for phones_path in phone_files:
        stem = phones_path.with_suffix("")
        words_path = stem.with_suffix(".words")
        if not words_path.exists():
            continue
        phones = parse_tier(phones_path)
        words = parse_tier(words_path)
        track = stem.name              # e.g. s0101a
        spk = track[:3]                # s01
        wav = stem.with_suffix(".wav")
        x = sr = None
        if write_slices and wav.exists():
            try:
                x, sr = read_audio(wav)
            except Exception:
                x = sr = None
        if protocol == "paper":
            track_end = (len(x) / sr) if x is not None else (
                phones[-1].end if phones else None
            )
            segs = segment_track_paper(words, phones, track_end=track_end)
        else:
            segs = segment_track(words, phones)
        # Some Buckeye tracks have audio shorter than their annotations (e.g.
        # s1901b: 569 s WAV vs 599 s of labels), so late segments fall past the
        # audio -> empty slices that crash batch aligners (MAPS preemphasis on a
        # 0-length signal; BFA chopping errors). Clamp to the audio and skip any
        # slice with less than MIN_SLICE_S of real samples.
        MIN_SLICE_S = 0.1
        for idx, (t0, t1, cwords, cphones) in enumerate(segs):
            utt_id = f"buckeye_{track}_{idx:03d}"
            if x is not None:
                a, b = round(t0 * sr), round(t1 * sr)
                a, b = max(0, min(a, len(x))), max(0, min(b, len(x)))
                if (b - a) < int(MIN_SLICE_S * sr):
                    continue
                slice_path = audio_out / f"{utt_id}.wav"
                write_audio(slice_path, x[a:b], sr)
                audio_path, dur = str(slice_path), (b - a) / sr
            else:
                audio_path, dur = str(wav), (t1 - t0)
            yield Utterance(
                utt_id=utt_id,
                source_corpus="buckeye",
                register="spontaneous",
                speaker_id=spk,
                audio_path=audio_path,
                sample_rate=sr or 16000,
                duration_s=dur,
                words=[w for w in cwords],
                phones=[p for p in cphones],
            )
