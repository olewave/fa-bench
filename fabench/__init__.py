# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""fabench, the FA-Bench scorer and runner.

FA-Bench measures how close forced aligners and timestamped ASR place word and
phone boundaries to the hand-marked boundaries of TIMIT and Buckeye, on clean
speech and under four degradations. Everything is seeded and config-driven.
"""

__version__ = "2.0.0"
