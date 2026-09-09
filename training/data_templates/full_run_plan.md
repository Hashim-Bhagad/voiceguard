# Full Indic AASIST-L run: acquisition and target composition

## Languages

Use exactly `hi` (Hindi), `en-IN` (Indian English), `mr` (Marathi), and `ta` (Tamil) in the first full run. Preserve source-native language tags in provenance notes, but map them consistently to these model tags in candidate CSVs.

## Target clip counts

| Split | Bona-fide | Spoof | Target | Sources |
|---|---:|---:|---:|---|
| Train | 1,600 | 1,600 | 3,200 | IndicVoices; IndicF5; VC-A; consented replay/partial clips |
| Dev | 400 | 400 | 800 | IndicVoices-R; TTS-B/VC-B/replay/partial, all spoof generators unseen in train |
| Test | 400 | 600 | 1,000 | IndicVoices-R plus Lahaja (Hindi) and Svarah (Indian English); TTS-C/VC-C/replay/partial unseen in train |

Distribute each train class approximately equally across four languages. Small external accent benchmarks do not need equal size; preserve their provenance and report their metrics separately.

## Source use and access

1. **IndicVoices:** stream and cap bona-fide training clips; never mirror the whole dataset. Record the resolved Hugging Face revision.
2. **IndicVoices-R:** stream and cap bona-fide development/test clips from speakers absent from train.
3. **Lahaja:** gated Hugging Face access; explicitly accept its terms before loading. Use only as Hindi test holdout.
4. **Svarah:** download from its repository-linked resource. Convert its published manifest and speaker metadata into a candidate CSV. Use only as Indian-English test holdout.
5. **IndicF5 / TTS-A:** generate only from licensed text and consented voice donors for training spoof. Log model revision, donor consent, and prompts.
6. **TTS-B/VC-B and TTS-C/VC-C:** do not use these generators in training. Use B in dev and C in test where available. If only two generators exist, use B in both dev/test but hold out speakers and generation settings.
7. **Replay / partial insert:** generate from material already in the correct split. Do not replay a train speaker into dev/test.

## Expected directory layout

```text
data/
  audio/{train,dev,test}/{bonafide,spoof}/<source>/
  candidates/
    indicvoices_train_bonafide.csv
    indicvoices_r_dev_bonafide.csv
    generated_indicf5_train_spoof.csv
    generated_tts_b_dev_spoof.csv
    generated_tts_c_test_spoof.csv
  augmentation/{musan,rirs}/
  metadata.csv
```

## Commands

Inspect source metadata before selecting a config or field names:

```bash
python scripts/inspect_hf_dataset.py --repo-id ai4bharat/IndicVoices
python scripts/inspect_hf_dataset.py --repo-id ai4bharat/indicvoices_r
```

After you identify the actual source fields/configs, stream a capped source subset rather than downloading an entire repository:

```bash
python scripts/collect_hf_bonafide.py \
  --repo-id ai4bharat/IndicVoices --config <verified-config> --source-split <verified-split> \
  --source-name indicvoices --target-split train --languages hi en-IN mr ta \
  --max-per-language 400 --audio-field <verified-audio-field> \
  --language-field <verified-language-field> --speaker-field <verified-speaker-field> \
  --license-or-consent "IndicVoices terms accepted" --output-root data
```

Generate candidate CSVs for synthetic, VC, replay, and partial clips using `full_run_source_candidates.csv`, then assemble only reviewed candidate files:

```bash
python scripts/assemble_full_manifest.py --candidates-dir data/candidates --out data/metadata.csv --check-files
python scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files
```

Do not begin model training until both validations pass.
