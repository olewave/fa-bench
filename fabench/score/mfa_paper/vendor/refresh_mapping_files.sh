#!/usr/bin/env bash
# Re-fetch the vendored MFA-2026 benchmark-repo mapping files. Diff the result
# against git before committing an update (see THIRD_PARTY_NOTICES.md) — this is
# a deliberate manual step, not an automatic sync.
set -euo pipefail
cd "$(dirname "$0")/mapping_files"

REPO="MontrealCorpusTools/mfa-interspeech2026"
BRANCH="main"

for f in arpa_timit_mapping arpa_buckeye_mapping \
         bournemouth_timit_mapping bournemouth_buckeye_mapping \
         charsiu_timit_mapping charsiu_buckeye_mapping \
         maps_timit_mapping maps_buckeye_mapping; do
  curl -sf "https://raw.githubusercontent.com/${REPO}/${BRANCH}/data/mapping_files/${f}.yaml" -o "${f}.yaml"
  echo "fetched ${f}.yaml"
done

curl -sf "https://raw.githubusercontent.com/${REPO}/${BRANCH}/LICENSE" -o ../LICENSE
echo "fetched LICENSE"

SHA=$(curl -sf "https://api.github.com/repos/${REPO}/commits/${BRANCH}" | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])")
echo "HEAD commit: ${SHA}"
echo "Update the commit SHA in ../THIRD_PARTY_NOTICES.md if these files changed."
