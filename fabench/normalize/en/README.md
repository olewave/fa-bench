# English (en) normalization

The English phone-set content for normalization. The language-agnostic machinery
(`canonicalize`, `make_canon`, `unmapped_rate`, DELETE/UNMAPPED) stays in
`fabench/normalize/`; this package holds the English specifics.

- `canonical.py` — `CANONICAL_39` (the TIMIT-39 reduced set, **General
  American**), `manner_of` (6-class display taxonomy), `manner_class_paper`
  (the MFA-2026 paper's 8-class exclusion taxonomy).
- `maps.py` — `{ARPABET,TIMIT61,BUCKEYE,IPA}_TO_39` tables + `norm_*` label
  normalizers.
- `__init__.py` — assembles `SOURCES` (source → (table, normalizer)) and the
  `sources(accent)` seam.

## Accent (us | uk)

The canonical set is ARPABET/TIMIT-39 = **US / General American**, the only
implemented accent (`IMPLEMENTED_ACCENTS = ("us",)`). **UK (RP)** genuinely
differs — non-rhotic, and a larger vowel inventory (LOT/PALM, TRAP/BATH split) —
and is a recognized but **not-yet-populated** accent: adding it means
accent-specific source maps (and a few fold rules) here, reachable via
`sources("uk")`, not a separate language. Requesting `"uk"` today raises
`NotImplementedError`.

Adding another language is a sibling package (`fabench/normalize/ko/`, …)
re-exported from `fabench/normalize/__init__.py`.
