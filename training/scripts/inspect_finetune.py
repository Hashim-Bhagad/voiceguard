"""Report exactly what fine-tuning changed inside AASIST-L, block by block.

"Did we fine-tune the whole network or only the head?" has a precise answer, and
the answer is not just "requires_grad=True everywhere". This script measures
three things for every top-level block of the model:

1. **trainable** parameters (``requires_grad``) -- what the optimiser was given;
2. **gradient reach** -- whether a real loss actually produces a usable gradient
   there, measured with the *pretrained* weights on real training clips;
3. **drift** -- the relative L2 change ``||w_ft - w_pre|| / ||w_pre||`` between
   the released AASIST-L checkpoint and your fine-tuned one.

(2) matters because AASIST-L has parameters that are trainable on paper but
receive no learning signal: the attention projections of the four heterogeneous
graph-attention layers sit behind a softmax with temperature 100 and a saturated
tanh, so their gradients underflow to ~1e-43, and the ``bn1`` layers of encoder
blocks 2-6 are never called in the upstream forward pass. Both stay bit-identical
to the pretrained checkpoint after fine-tuning.

  python scripts/inspect_finetune.py \
      --pretrained weights/AASIST-L.pth \
      --finetuned outputs/aasist_l_indic/best.pt \
      --markdown outputs/aasist_l_indic/finetune_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.dataset import load_metadata, read_audio, repeat_pad  # noqa: E402
from src.model import build_model, model_type  # noqa: E402

# Below this, a gradient is numerically indistinguishable from zero for Adam
# (eps=1e-8): the update it produces is smaller than float32 can represent.
DEAD_GRAD = 1e-30


XLSR_BLOCKS = {
    "feature_extractor": "xlsr.cnn_feature_encoder",
    "feature_projection": "xlsr.feature_projection",
    "masked_spec_embed": "xlsr.mask_embedding",
}


def block_of(name: str) -> str:
    """Map a parameter name to its block, e.g. 'encoder.3' or 'xlsr.layer.17'."""
    parts = name.removeprefix("net.").split(".")
    if parts[0] == "ssl":  # XLS-R front-end
        if parts[1] == "encoder":
            if parts[2] == "layers":
                return f"xlsr.layer.{int(parts[3]):02d}"
            return f"xlsr.{parts[2]}"
        return XLSR_BLOCKS.get(parts[1], f"xlsr.{parts[1]}")
    if parts[0] == "encoder" and len(parts) > 1:
        return f"encoder.{parts[1]}"
    return parts[0]


def real_batch(cfg: dict, per_label: int, seed: int) -> tuple[torch.Tensor, torch.Tensor] | None:
    """A few real training clips, so gradient reach reflects real activations."""
    try:
        df = load_metadata(TRAINING_ROOT / cfg["data"]["metadata_csv"])
    except FileNotFoundError:
        return None
    train = df[df["split"] == cfg["data"]["train_split"]]
    if train.empty:
        return None
    picked = pd.concat(
        group.sample(min(per_label, len(group)), random_state=seed)
        for _, group in train.groupby("label")
    )
    samples = int(cfg["model"]["window_samples"])
    waves = [repeat_pad(read_audio(p, cfg["sample_rate"]), samples) for p in picked["clip_path"]]
    labels = (picked["label"] == "spoof").astype(int).to_numpy()
    return torch.from_numpy(np.stack(waves)), torch.from_numpy(labels)


def gradient_reach(model: torch.nn.Module, batch) -> dict[str, float | None]:
    model.train()
    model.zero_grad(set_to_none=True)
    waveform, label = batch
    loss = torch.nn.functional.cross_entropy(model(waveform), label)
    loss.backward()
    return {
        name: (None if p.grad is None else float(p.grad.abs().max()))
        for name, p in model.named_parameters()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    parser.add_argument("--pretrained", default="weights/AASIST-L.pth")
    parser.add_argument("--finetuned", default="outputs/aasist_l_indic/best.pt")
    parser.add_argument("--clips-per-label", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", default=None, help="Write the per-block report as JSON")
    parser.add_argument("--markdown", default=None, help="Write the per-block report as a Markdown table")
    args = parser.parse_args()

    with open(TRAINING_ROOT / args.config, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    torch.manual_seed(args.seed)

    model = build_model(cfg)  # XLS-R loads its pre-trained encoder here
    if model_type(cfg) == "aasist_l":
        missing, unexpected = model.load_pretrained(TRAINING_ROOT / args.pretrained)
        if missing or unexpected:
            raise SystemExit(f"pretrained checkpoint does not match: missing={missing} unexpected={unexpected}")
    pretrained = {k: v.detach().clone() for k, v in model.state_dict().items()}

    batch = real_batch(cfg, args.clips_per_label, args.seed)
    source = "real training clips"
    if batch is None:
        source = "random noise (no manifest found; reach may be optimistic)"
        batch = (torch.randn(2, int(cfg["model"]["window_samples"])) * 0.1, torch.tensor([0, 1]))
    grads = gradient_reach(model, batch)

    blob = torch.load(TRAINING_ROOT / args.finetuned, map_location="cpu", weights_only=False)
    finetuned = blob.get("model", blob)

    blocks: OrderedDict[str, dict] = OrderedDict()
    for name, param in model.named_parameters():
        row = blocks.setdefault(block_of(name), {
            "params": 0, "trainable": 0, "learning": 0, "frozen_in_practice": 0,
            "_diff": 0.0, "_norm": 0.0,
        })
        n = param.numel()
        row["params"] += n
        row["trainable"] += n if param.requires_grad else 0
        g = grads[name]
        if param.requires_grad and g is not None and g > DEAD_GRAD:
            row["learning"] += n
        else:
            row["frozen_in_practice"] += n
        before, after = pretrained[name].float(), finetuned[name].float()
        row["_diff"] += float((after - before).pow(2).sum())
        row["_norm"] += float(before.pow(2).sum())

    for row in blocks.values():
        row["relative_change"] = (row.pop("_diff") ** 0.5) / max(row.pop("_norm") ** 0.5, 1e-12)

    total = {k: sum(r[k] for r in blocks.values()) for k in ("params", "trainable", "learning", "frozen_in_practice")}
    layer_types = {"Conv2d": 0, "Linear": 0, "BatchNorm": 0}
    for module in model.modules():
        kind = type(module).__name__
        if kind in ("Conv2d", "Linear"):
            layer_types[kind] += 1
        elif kind.startswith("BatchNorm"):
            layer_types["BatchNorm"] += 1

    print(f"gradient reach measured on: {source}")
    print(f"fine-tuned checkpoint: {args.finetuned} (epoch {blob.get('epoch', '?')}, dev EER {blob.get('dev_eer', float('nan')):.4f})")
    if hasattr(model, "describe"):
        print(model.describe())
    else:
        print(f"weight layers: {layer_types}  (+1 fixed sinc-conv front end)")
    print()
    header = (f"{'block':26s} {'params':>12s} {'trainable':>12s} {'learning':>12s} "
              f"{'not learn.*':>12s} {'rel. change':>11s}")
    print(header)
    print("-" * len(header))
    for name, row in blocks.items():
        print(f"{name:26s} {row['params']:>12,} {row['trainable']:>12,} {row['learning']:>12,} "
              f"{row['frozen_in_practice']:>12,} {row['relative_change']:>11.2%}")
    print("-" * len(header))
    print(f"{'total':26s} {total['params']:>12,} {total['trainable']:>12,} {total['learning']:>12,} "
          f"{total['frozen_in_practice']:>12,}")
    print("\n* not learning: frozen on purpose, or trainable but receiving no usable gradient\n"
          "  (max |grad| <= 1e-30, or never used in the forward pass)")

    report = {"source": source, "layer_types": layer_types, "total": total, "blocks": blocks,
              "epoch": blob.get("epoch"), "dev_eer": blob.get("dev_eer")}
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    if args.markdown:
        lines = ["| Block | Params | Trainable | Learning | Not learning | Weight change |",
                 "|---|---:|---:|---:|---:|---:|"]
        for name, row in blocks.items():
            lines.append(f"| `{name}` | {row['params']:,} | {row['trainable']:,} | {row['learning']:,} | "
                         f"{row['frozen_in_practice']:,} | {row['relative_change']:.2%} |")
        lines.append(f"| **Total** | **{total['params']:,}** | **{total['trainable']:,}** | "
                     f"**{total['learning']:,}** | **{total['frozen_in_practice']:,}** | |")
        Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.markdown}")


if __name__ == "__main__":
    main()
