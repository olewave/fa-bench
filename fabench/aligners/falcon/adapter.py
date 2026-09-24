# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""FALCON (Rousso, Cohen & Keshet 2026) -- PHONE TIER, MODE B ONLY.

Mode B is not a choice: it is the only English path FALCON exposes. Its
`resolve_internal_language(lang, mode, annotation)` returns "english" for
exactly one combination -- lang=english, mode=phoneme, annotation=phn -- and
falls through to a Dutch panphon G2P for everything else, word-level input and
plain text included. Handed English orthography that branch produces
`y aa g ae` for "wage", so there is no word tier here and no mode A: the phone
sequence has to be supplied, and FALCON places its boundaries.

That makes it the same kind of row as torchaudio_fa's phone tier -- an easier
question than the aligners that derive their own phones -- and it is marked in
the table accordingly (PHONE_MODE_B in evals/gen_paper_tables.py).

Its released checkpoints are trained on TIMIT and Buckeye. TIMIT is safe: the
FA-Bench dev and core-test lists both come from TIMIT's test portion, which
FALCON holds out. Buckeye is not: FALCON uses its own 80/10/10 speaker split,
which does not coincide with ours, so its training speakers overlap our dev and
test. Those cells carry the same disclosure MAPS does.
"""
from fabench.aligners.base import BatchItem
from fabench.aligners.subprocess_aligner import SubprocessAligner
from fabench.normalize import make_canon

#: FA-Bench and FALCON agree on the 39 classes and disagree on three of the
#: labels: FALCON keeps the syllabic forms and the low-back `ao` as its class
#: representatives where FA-Bench keeps `aa`, `l`, `n`. Its phone sequence is a
#: model INPUT -- predict.py passes it straight into the network -- so handing
#: it `aa` means handing it a symbol it never saw in training. Scoring is
#: unaffected: the echoed labels fold back through `arpabet` and both sides
#: agree on the partition.
_TO_FALCON = {"aa": "ao", "l": "el", "n": "en"}


class Falcon(SubprocessAligner):
    #: Mode B echoes back the phone sequence it was handed, so the hypothesis
    #: is in the GOLD alphabet of whichever corpus the cell is on -- `timit` for
    #: TIMIT, `buckeye` for Buckeye. Same shape as torchaudio_fa's
    #: phoneme_source: the recipe carries a default and a cell overrides it.
    source = "timit"
    emits_confidence = False
    granularity = ("phone",)
    default_model = "pretrained_models/falcon_joint_multilingual.pt"
    #: Boundaries come off spectral-frame peaks at the encoder's resolution.
    frame_s = 0.010

    def load(self) -> None:
        super().load()
        # FALCON is HANDED TIMIT-39 (see _job), so that is the alphabet its
        # echoed labels come back in. `arpabet` is the source table that leaves
        # the folded set alone -- `timit` would re-map `sil` to UNMAPPED,
        # because sil is a fold OUTPUT, not a TIMIT-61 input symbol.
        self.source = "arpabet"
        self._canon = make_canon(str(self.params.get("phoneme_source", "timit")))

    def _job(self, it: BatchItem) -> dict:
        """Mode B: the phone sequence IS the input, folded to TIMIT-39 first.

        Its English path documents the contract -- "assumes labels are already
        TIMIT-39 phonemes" -- and handing it the raw corpus alphabet breaks it
        silently. Buckeye's nasalised vowels, glottal stop and !sil are symbols
        FALCON has never modelled, and the first run put it 16ms behind every
        other system on Buckeye while it sat mid-pack on TIMIT. Both corpora
        fold to exactly the same 39 symbols, so this is also what makes the two
        halves comparable.
        """
        j = super()._job(it)
        if it.phone_seq:
            folded = (self._canon(p) for p in it.phone_seq)
            # DELETE and UNMAPPED are sentinels, not phones.
            j["phone_seq"] = [_TO_FALCON.get(p, p) for p in folded
                              if not p.startswith("\x00")]
        return j

    def _extra_argv(self) -> list[str]:
        return [str(self.params.get("repo_path", "")), "phoneme"]
