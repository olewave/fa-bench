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
