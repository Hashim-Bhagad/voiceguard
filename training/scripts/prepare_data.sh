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
#   export ACCEPT_XTTS_NONCOMMERCIAL=1           # optional, XTTS-v2 voice clones (step 7)
#   bash scripts/prepare_data.sh
#
# Re-running is cheap: a source whose candidate CSV already exists is skipped
# (set FORCE=1 to redo everything). Every knob below can be overridden from the
# environment, e.g. ITW_MAX_PER_LABEL=0 bash scripts/prepare_data.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
# Xet transfers ask the Hub API for a read token per file, and free accounts get
# 1000 API calls per 5 minutes: a 1,866-file dataset hits that limit. Plain
# HTTP downloads go through the CDN instead. Set HF_HUB_DISABLE_XET=0 to undo.
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

INDIC_LANGS="${INDIC_LANGS:-hindi marathi tamil bengali}"
INDIC_MAX_PER_LANG="${INDIC_MAX_PER_LANG:-600}"
ITW_MAX_PER_LABEL="${ITW_MAX_PER_LABEL:-6000}"      # 0 = all ~31.8k In-the-Wild clips
MLAAD_LANGS="${MLAAD_LANGS:-hi}"                    # Hindi has 9 TTS generators
MLAAD_MAX_PER_GEN="${MLAAD_MAX_PER_GEN:-300}"
VOCODED_MAX_PER_LANG="${VOCODED_MAX_PER_LANG:-400}"
# Zero-shot voice clones of the bona-fide speakers (needs a GPU; ~1 h on a T4 at 200/lang).
MAKE_CLONES="${MAKE_CLONES:-1}"
CLONE_ENGINES="${CLONE_ENGINES:-xtts indicf5}"
CLONES_PER_LANG="${CLONES_PER_LANG:-200}"
CLONE_ENV="${CLONE_ENV:-.clone-env}"
FORCE="${FORCE:-0}"

# Spoof generators held out of training entirely. dev picks the checkpoint,
# test is the headline number, so both must be synthesisers the model never saw.
DEV_GENERATORS="${DEV_GENERATORS:-elevenlabs}"
TEST_GENERATORS="${TEST_GENERATORS:-speechify hexgrad_kokoro}"
# Not one synthesiser each, so split by speaker instead (see build_manifest.py):
# In-the-Wild's unlabelled deepfakes, and our clones of the bona-fide speakers.
SPEAKER_SPLIT_GENERATORS="${SPEAKER_SPLIT_GENERATORS:-in_the_wild_unknown xtts_v2_clone indicf5_clone}"

have() { [[ "$FORCE" != "1" && -s "data/candidates/$1.csv" ]]; }
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

if [[ -z "${HF_TOKEN:-}" && ! -s .env ]]; then
  echo "HF_TOKEN is not set and training/.env does not exist." >&2
  echo "IndicVoices is gated: accept its terms on Hugging Face, then export HF_TOKEN=hf_..." >&2
  exit 1
fi

step "1/9  Official AASIST source (pinned) and pretrained AASIST-L weights"
[[ -f third_party/aasist/models/AASIST.py ]] || "$PY" scripts/bootstrap_aasist.py
[[ -f weights/AASIST-L.pth ]] || "$PY" scripts/resolve_pretrained.py

step "2/9  garystafford: English real + 6 commercial TTS systems"
have garystafford && echo "skip (exists)" || "$PY" scripts/ingest_garystafford.py

step "3/9  In-the-Wild: real-world celebrity speech and deepfakes"
have in_the_wild && echo "skip (exists)" || \
  "$PY" scripts/ingest_in_the_wild.py --max-per-label "$ITW_MAX_PER_LABEL"

step "4/9  IndicVoices: Indic bona-fide ($INDIC_LANGS)"
# shellcheck disable=SC2086
have indicvoices && echo "skip (exists)" || \
  "$PY" scripts/ingest_indicvoices.py --languages $INDIC_LANGS --max-per-language "$INDIC_MAX_PER_LANG"

step "5/9  MLAAD: Indic TTS spoof ($MLAAD_LANGS)"
if [[ "${ACCEPT_MLAAD_NONCOMMERCIAL:-0}" == "1" ]]; then
  # MLAAD is CC-BY-NC-4.0: fine for coursework and research, not for a product.
  # It is the only source here with real Indic-language deepfakes, so it is what
  # breaks the "sounds Indic -> genuine" shortcut. Hold two of its generators out.
  # IndicF5 and XTTS also make our own clones (step 7), so neither can be the
  # "unseen" MLAAD test generator any more; Bark is used nowhere else.
  DEV_GENERATORS="$DEV_GENERATORS ${MLAAD_DEV_GENERATORS:-veena}"
  TEST_GENERATORS="$TEST_GENERATORS ${MLAAD_TEST_GENERATORS:-bark}"
  # shellcheck disable=SC2086
  have mlaad && echo "skip (exists)" || \
    "$PY" scripts/ingest_mlaad.py --languages $MLAAD_LANGS \
      --max-per-generator "$MLAAD_MAX_PER_GEN" --accept-noncommercial
else
  echo "skip: set ACCEPT_MLAAD_NONCOMMERCIAL=1 to include MLAAD (CC-BY-NC-4.0)."
  echo "      Without it every Indic clip is bona-fide except the vocoded set below."
fi

step "6/9  Vocoded Indic spoof (same channel as IndicVoices)"
have vocoded_indic && echo "skip (exists)" || \
  "$PY" scripts/make_vocoded_spoof.py --max-per-language "$VOCODED_MAX_PER_LANG"

step "7/9  Voice clones of the bona-fide speakers ($CLONE_ENGINES)"
if [[ "$MAKE_CLONES" != "1" ]]; then
  echo "skip: MAKE_CLONES=0"
elif have clones; then
  echo "skip (exists)"
elif [[ "${CLONE_ALLOW_CPU:-0}" != "1" ]] && ! "$PY" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
  echo "skip: no GPU. Clones need one (set MAKE_CLONES=0 to silence this, or CLONE_ALLOW_CPU=1"
  echo "      to generate a handful slowly on CPU)."
else
  engines=""
  for engine in $CLONE_ENGINES; do
    if [[ "$engine" == "xtts" && "${ACCEPT_XTTS_NONCOMMERCIAL:-0}" != "1" ]]; then
      echo "  dropping xtts: it is under the Coqui Public Model License (non-commercial)."
      echo "  Set ACCEPT_XTTS_NONCOMMERCIAL=1 to accept it."
    else
      engines="$engines $engine"
    fi
  done
  if [[ -z "$engines" ]]; then
    echo "skip: no clone engine left"
  else
    # The TTS packages pin NumPy < 2 and a newer Transformers than training uses, so
    # they live in their own virtualenv that still sees the system CUDA PyTorch.
    if [[ ! -x "$CLONE_ENV/bin/python" ]] || ! "$CLONE_ENV/bin/python" -m pip --version >/dev/null 2>&1; then
      rm -rf "$CLONE_ENV"
      # Colab's Python ships without ensurepip, so plain venv cannot seed pip there;
      # virtualenv brings its own copy.
      "$PY" -m venv --system-site-packages "$CLONE_ENV" 2>/dev/null || {
        rm -rf "$CLONE_ENV"
        "$PY" -m pip install -q virtualenv
        "$PY" -m virtualenv -q --system-site-packages "$CLONE_ENV"
      }
    fi
    pkgs=""
    # coqui-tts imports GPT-2 classes that the training stack's Transformers 4.x (from
    # the system site-packages) cannot provide under NumPy 1.x, so pin 5.x in here.
    [[ "$engines" == *xtts* ]] && pkgs="$pkgs coqui-tts transformers>=5"
    [[ "$engines" == *indicf5* ]] && pkgs="$pkgs git+https://github.com/ai4bharat/IndicF5.git"
    # shellcheck disable=SC2086
    # (pip's "X requires numpy>=2" warnings are about system packages this env never imports.)
    "$CLONE_ENV/bin/python" -m pip install -q $pkgs > "$CLONE_ENV/pip.log" 2>&1 || {
      tail -30 "$CLONE_ENV/pip.log" >&2; echo "pip install for the clone engines failed" >&2; exit 1; }
    # shellcheck disable=SC2086
    COQUI_TOS_AGREED="${ACCEPT_XTTS_NONCOMMERCIAL:-0}" "$CLONE_ENV/bin/python" scripts/make_clone_spoof.py \
      --engines $engines --per-language "$CLONES_PER_LANG"
  fi
fi

step "8/9  Manifest: speaker-disjoint splits, unseen generators in dev/test"
echo "dev generators:           $DEV_GENERATORS"
echo "test generators:          $TEST_GENERATORS"
echo "split-by-speaker sources: $SPEAKER_SPLIT_GENERATORS"
# shellcheck disable=SC2086
"$PY" scripts/build_manifest.py --check-files \
  --dev-generators $DEV_GENERATORS --test-generators $TEST_GENERATORS \
  --speaker-split-generators $SPEAKER_SPLIT_GENERATORS

step "9/9  Validate"
"$PY" scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files

echo
du -sh data/audio 2>/dev/null || true
echo "Data ready: data/metadata.csv"
