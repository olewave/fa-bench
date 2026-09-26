# English (en) normalization

The English phone-set content for normalization. The language-agnostic
machinery (`canonicalize`, `make_canon`, `unmapped_rate`, DELETE/UNMAPPED)
stays in `fabench/normalize/`. This package holds the English specifics.

- `canonical.py` holds `CANONICAL_39` (the TIMIT-39 reduced set, **General
  American**), `manner_of` (the 6-class display taxonomy) and
  `manner_class_paper` (the MFA-2026 paper's 8-class exclusion taxonomy).
- `maps.py` holds the `{ARPABET,TIMIT61,BUCKEYE,IPA}_TO_39` tables and the
  `norm_*` label normalizers.
- `__init__.py` assembles `SOURCES` (source → (table, normalizer)) and the
  `sources(accent)` seam.

## Accent (us | uk)

The canonical set is ARPABET/TIMIT-39, **US / General American**, the only
implemented accent (`IMPLEMENTED_ACCENTS = ("us",)`). **UK (RP)** differs. It
is non-rhotic and has a larger vowel inventory (the LOT/PALM and TRAP/BATH
splits). It is a recognized but **not-yet-populated** accent. Adding it means
accent-specific source maps (and a few fold rules) here, reachable through
`sources("uk")`, rather than a separate language. Requesting `"uk"` today
raises `NotImplementedError`.

Adding another language is a sibling package (`fabench/normalize/ko/`, …)
re-exported from `fabench/normalize/__init__.py`.
