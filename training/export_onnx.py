"""Export a fine-tuned AASIST-L checkpoint to ONNX for the VoiceGuard backend.

Contract the backend depends on:
  input   waveform    float32[batch, 64600]   16 kHz mono, values in [-1, 1]
  output  spoof_logit float32[batch]          positive means more spoof-like

The export is verified twice before it is accepted: PyTorch vs ONNX Runtime on
random noise, and again on a batch of 3 to confirm the dynamic batch axis works.
An unverified export is worse than no export, because it fails silently at
inference time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
import yaml

from src.model import SpoofLogitExport, build_model

TRAINING_ROOT = Path(__file__).resolve().parent


def load_config(checkpoint_blob: object, config_path: str) -> tuple[dict, bool]:
    """Prefer the config embedded in the checkpoint; fall back to a YAML file."""
    if (
        isinstance(checkpoint_blob, dict)
        and "config" in checkpoint_blob
        and "model" in checkpoint_blob
    ):
        return checkpoint_blob["config"], True
    path = Path(config_path)
    if not path.is_file():
        path = TRAINING_ROOT / "configs" / "aasist_l.yaml"
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle), False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--out", default="aasist-l-indic-v0.1.onnx")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    args = parser.parse_args()

    blob = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    cfg, from_checkpoint = load_config(blob, args.config)

    model = build_model(cfg)
    if from_checkpoint:
        model.load_state_dict(blob["model"], strict=True)
        print(f"loaded fine-tuned weights from {args.ckpt} (epoch {blob.get('epoch')})")
        if "dev_eer" in blob:
            print(f"  checkpoint dev EER: {blob['dev_eer']:.4f}")
    else:
        missing, unexpected = model.load_pretrained(args.ckpt)
        print(f"loaded raw state dict: missing={len(missing)} unexpected={len(unexpected)}")
        if missing or unexpected:
            raise SystemExit("Checkpoint does not match the pinned AASIST-L architecture.")
    model.eval()

    export_model = SpoofLogitExport(model).eval()
    samples = int(cfg["model"]["window_samples"])
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        export_model,
        torch.zeros(1, samples, dtype=torch.float32),
        str(output),
        input_names=["waveform"],
        output_names=["spoof_logit"],
        opset_version=args.opset,
        dynamic_axes={"waveform": {0: "batch"}, "spoof_logit": {0: "batch"}},
    )

    session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    generator = torch.Generator().manual_seed(0)
    errors = {}
    for batch in (1, 3):
        probe = torch.randn(batch, samples, generator=generator, dtype=torch.float32)
        with torch.inference_mode():
            expected = export_model(probe).numpy()
        actual = session.run(None, {"waveform": probe.numpy()})[0]
        if actual.shape != (batch,):
            raise SystemExit(
                f"ONNX output shape {actual.shape} != expected ({batch},). "
                "The dynamic batch axis is wrong."
            )
        max_error = float(np.max(np.abs(expected - actual)))
        errors[batch] = max_error
        if not np.allclose(expected, actual, rtol=1e-3, atol=1e-4):
            raise SystemExit(f"ONNX mismatch at batch {batch}: max abs error {max_error}")
        print(f"  batch {batch}: max_abs_error={max_error:.3g}")

    size_mb = output.stat().st_size / (1024 * 1024)
    sidecar = output.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "source_checkpoint": str(Path(args.ckpt).resolve()),
                "architecture": "AASIST-L (ClovaAI, official config)",
                "parameters": model.num_parameters(),
                "opset": args.opset,
                "sample_rate": cfg["sample_rate"],
                "window_samples": samples,
                "input": "waveform float32[batch, %d]" % samples,
                "output": "spoof_logit float32[batch]; positive = more spoof-like",
                "verified_max_abs_error": errors,
                "size_mb": round(size_mb, 3),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nwrote {output} ({size_mb:.2f} MB)")
    print(f"wrote {sidecar}")
    print(
        "\nTo deploy: copy the .onnx into backend/models/, set MODEL_BACKEND=aasist-l-onnx, "
        "and restart the backend.\n"
        "Do not attach an accuracy or latency claim to this file until it has been measured "
        "on your held-out test split and on the actual target device."
    )


if __name__ == "__main__":
    main()
