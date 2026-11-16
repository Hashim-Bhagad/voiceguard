#!/usr/bin/env bash
# Fetch every training source straight from Hugging Face and build the manifest.
#
# Run this ON the GPU machine (Colab, SageMaker, any cloud box), from training/.
# Nothing has to be uploaded from your laptop: all sources are public or gated
# Hugging Face datasets, and a datacentre pulls them far faster than a home
# connection can push them.
#
#   export HF_TOKEN=hf_...                       # read token, IndicVoices terms accepted
#   export ACCEPT_MLAAD_NONCOMMERCIAL=1          # optional, see licence note below
#   bash scripts/prepare_data.sh
#
# Re-running is cheap: a source whose candidate CSV already exists is skipped
# (set FORCE=1 to redo everything). Every knob below can be overridden from the
# environment, e.g. ITW_MAX_PER_LABEL=0 bash scripts/prepare_data.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"

INDIC_LANGS="${INDIC_LANGS:-hindi marathi tamil bengali}"
INDIC_MAX_PER_LANG="${INDIC_MAX_PER_LANG:-600}"
ITW_MAX_PER_LABEL="${ITW_MAX_PER_LABEL:-6000}"      # 0 = all ~31.8k In-the-Wild clips
MLAAD_LANGS="${MLAAD_LANGS:-hi}"                    # Hindi has 9 TTS generators
MLAAD_MAX_PER_GEN="${MLAAD_MAX_PER_GEN:-300}"
VOCODED_MAX_PER_LANG="${VOCODED_MAX_PER_LANG:-400}"
FORCE="${FORCE:-0}"

# Spoof generators held out of training entirely. dev picks the checkpoint,
# test is the headline number, so both must be synthesisers the model never saw.
DEV_GENERATORS="${DEV_GENERATORS:-elevenlabs}"
TEST_GENERATORS="${TEST_GENERATORS:-speechify hexgrad_kokoro in_the_wild_unknown}"

have() { [[ "$FORCE" != "1" && -s "data/candidates/$1.csv" ]]; }
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [[ -z "${HF_TOKEN:-}" && ! -s .env ]]; then
  echo "HF_TOKEN is not set and training/.env does not exist." >&2
  echo "IndicVoices is gated: accept its terms on Hugging Face, then export HF_TOKEN=hf_..." >&2
  exit 1
fi

step "1/8  Official AASIST source (pinned) and pretrained AASIST-L weights"
[[ -f third_party/aasist/models/AASIST.py ]] || "$PY" scripts/bootstrap_aasist.py
[[ -f weights/AASIST-L.pth ]] || "$PY" scripts/resolve_pretrained.py

step "2/8  garystafford: English real + 6 commercial TTS systems"
have garystafford && echo "skip (exists)" || "$PY" scripts/ingest_garystafford.py

step "3/8  In-the-Wild: real-world celebrity speech and deepfakes"
have in_the_wild && echo "skip (exists)" || \
  "$PY" scripts/ingest_in_the_wild.py --max-per-label "$ITW_MAX_PER_LABEL"

step "4/8  IndicVoices: Indic bona-fide ($INDIC_LANGS)"
# shellcheck disable=SC2086
have indicvoices && echo "skip (exists)" || \
  "$PY" scripts/ingest_indicvoices.py --languages $INDIC_LANGS --max-per-language "$INDIC_MAX_PER_LANG"

step "5/8  MLAAD: Indic TTS spoof ($MLAAD_LANGS)"
if [[ "${ACCEPT_MLAAD_NONCOMMERCIAL:-0}" == "1" ]]; then
  # MLAAD is CC-BY-NC-4.0: fine for coursework and research, not for a product.
  # It is the only source here with real Indic-language deepfakes, so it is what
  # breaks the "sounds Indic -> genuine" shortcut. Hold two of its generators out.
  DEV_GENERATORS="$DEV_GENERATORS ${MLAAD_DEV_GENERATORS:-veena}"
  TEST_GENERATORS="$TEST_GENERATORS ${MLAAD_TEST_GENERATORS:-indicf5}"
  # shellcheck disable=SC2086
  have mlaad && echo "skip (exists)" || \
    "$PY" scripts/ingest_mlaad.py --languages $MLAAD_LANGS \
      --max-per-generator "$MLAAD_MAX_PER_GEN" --accept-noncommercial
else
  echo "skip: set ACCEPT_MLAAD_NONCOMMERCIAL=1 to include MLAAD (CC-BY-NC-4.0)."
  echo "      Without it every Indic clip is bona-fide except the vocoded set below."
fi

step "6/8  Vocoded Indic spoof (same channel as IndicVoices)"
have vocoded_indic && echo "skip (exists)" || \
  "$PY" scripts/make_vocoded_spoof.py --max-per-language "$VOCODED_MAX_PER_LANG"

step "7/8  Manifest: speaker-disjoint splits, unseen generators in dev/test"
echo "dev generators:  $DEV_GENERATORS"
echo "test generators: $TEST_GENERATORS"
# shellcheck disable=SC2086
"$PY" scripts/build_manifest.py --check-files \
  --dev-generators $DEV_GENERATORS --test-generators $TEST_GENERATORS

step "8/8  Validate"
"$PY" scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files

echo
du -sh data/audio 2>/dev/null || true
echo "Data ready: data/metadata.csv"
