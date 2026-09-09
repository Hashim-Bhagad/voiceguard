"""Export AASIST-L as a fixed-window ONNX model with one spoof logit output."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import onnxruntime as ort
import torch

from src.model import SpoofLogitExport, build_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--out", default="aasist-l-indic-v0.1.onnx")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    args = parser.parse_args()

    import yaml
    blob = torch.load(args.ckpt, map_location="cpu")
    if isinstance(blob, dict) and "config" in blob and "model" in blob:
        cfg = blob["config"]
        model = build_model(cfg)
        model.load_state_dict(blob["model"], strict=True)
    else:
        cfg_path = Path(args.config)
        if not cfg_path.is_file():
            cfg_path = Path(__file__).parent / "configs" / "aasist_l.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        # Ensure upstream_dir is resolved relative to training/
        if not Path(cfg["model"]["upstream_dir"]).is_dir():
            cfg["model"]["upstream_dir"] = str(Path(__file__).parent / "third_party" / "aasist")
        model = build_model(cfg)
        missing, unexpected = model.load_pretrained(args.ckpt)
        print(f"Loaded pretrained weights. Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")
    model.eval()
    export_model = SpoofLogitExport(model).eval()
    samples = int(cfg["model"]["window_samples"])
    waveform = torch.zeros(1, samples, dtype=torch.float32)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        export_model,
        waveform,
        str(output),
        input_names=["waveform"],
        output_names=["spoof_logit"],
        opset_version=args.opset,
        dynamic_axes={"waveform": {0: "batch"}, "spoof_logit": {0: "batch"}},
    )

    probe = torch.randn(1, samples, dtype=torch.float32)
    with torch.inference_mode():
        expected = export_model(probe).numpy()
    session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"waveform": probe.numpy()})[0]
    max_error = float(np.max(np.abs(expected - actual)))
    if not np.allclose(expected, actual, rtol=1e-3, atol=1e-4):
        raise RuntimeError(f"ONNX mismatch: max absolute error {max_error}")
    print(f"wrote {output}; verified ONNX max_abs_error={max_error:.6g}")
    print("Copy this file to backend/models/ and set MODEL_BACKEND=aasist-l-onnx.")


if __name__ == "__main__":
    main()
