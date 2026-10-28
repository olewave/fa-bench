# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0


"""PocketSphinx — CMU's HMM recognizer, run as a forced aligner.

github.com/cmusphinx/pocketsphinx, built from a pinned commit of its main
branch by evals/aligners/pocketsphinx/download_and_install.sh. Its bundled US
English model is a phonetically tied mixture HMM over 10 ms frames, which puts
the row in the HMM family beside MFA as its one member not built on Kaldi.

Mode A only. The worker aligns the transcript the way `pocketsphinx align`
does, with pronunciations from the model's CMUdict and g2p_en for the words it
lacks, and returns words and stress-free ARPAbet phones.

Runs in its own interpreter (fabench/aligners/subprocess_aligner.py), on CPU.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class PocketSphinx(SubprocessAligner):
    source = "arpabet"
    granularity = ("word", "phone")
    default_model = "en-us"
