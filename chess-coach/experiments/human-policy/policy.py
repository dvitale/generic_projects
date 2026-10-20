"""Small rating-conditioned human move policy; no engine or search at inference."""
from dataclasses import asdict, dataclass
import math

import chess
import torch
from torch import nn
from torch.nn import functional as F

from features import PROMOTIONS, encode, move_id


@dataclass
class Config:
    dim: int = 128
    layers: int = 4
    heads: int = 4
    head_dim: int = 32
    dropout: float = 0.1


class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.heads = cfg.heads
        self.dropout = cfg.dropout
        self.norm1 = nn.LayerNorm(cfg.dim)
        self.qkv = nn.Linear(cfg.dim, 3 * cfg.dim)
        self.proj = nn.Linear(cfg.dim, cfg.dim)
        self.norm2 = nn.LayerNorm(cfg.dim)
        self.ff = nn.Sequential(nn.Linear(cfg.dim, 4 * cfg.dim), nn.GELU(),
                                nn.Dropout(cfg.dropout), nn.Linear(4 * cfg.dim, cfg.dim))

    def forward(self, x, bias):
        batch, squares, dim = x.shape
        q, k, v = self.qkv(self.norm1(x)).view(
            batch, squares, 3, self.heads, dim // self.heads
        ).permute(2, 0, 3, 1, 4).unbind(0)
        attn = F.scaled_dot_product_attention(
            q, k, v, attn_mask=bias.to(q.dtype),
            dropout_p=self.dropout if self.training else 0.0,
        )
        x = x + self.proj(attn.transpose(1, 2).reshape(batch, squares, dim))
        return x + self.ff(self.norm2(x))


class Policy(nn.Module):
    def __init__(self, cfg=Config()):
        super().__init__()
        self.cfg = cfg
        self.piece = nn.Embedding(13, cfg.dim)
        self.ep = nn.Embedding(2, cfg.dim)
        self.square = nn.Embedding(64, cfg.dim)
        self.context = nn.Sequential(nn.Linear(8, cfg.dim), nn.GELU(),
                                     nn.Linear(cfg.dim, cfg.dim))
        # Relative file/rank bias: simple baseline, not Chessformer's dynamic GAB.
        squares = torch.arange(64)
        files, ranks = squares % 8, squares // 8
        relative = (files[:, None] - files[None, :] + 7) * 15
        relative += ranks[:, None] - ranks[None, :] + 7
        self.register_buffer("relative", relative)
        self.geometry = nn.Embedding(225, cfg.heads)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.layers)])
        self.norm = nn.LayerNorm(cfg.dim)
        self.origin = nn.Linear(cfg.dim, 5 * cfg.head_dim)
        self.destination = nn.Linear(cfg.dim, 5 * cfg.head_dim)
        self.origin_bias = nn.Linear(cfg.dim, 5)
        self.destination_bias = nn.Linear(cfg.dim, 5)

    def forward(self, pieces, ep, context, legal):
        batch = pieces.shape[0]
        x = self.piece(pieces) + self.ep(ep)
        x = x + self.square(torch.arange(64, device=x.device))[None]
        x = x + self.context(context)[:, None]
        bias = self.geometry(self.relative).permute(2, 0, 1)[None]
        for block in self.blocks:
            x = block(x, bias)
        x = self.norm(x)
        a = self.origin(x).view(batch, 64, 5, self.cfg.head_dim)
        b = self.destination(x).view(batch, 64, 5, self.cfg.head_dim)
        # Only score legal candidates; avoid materializing 20,480 action logits.
        ids = legal.clamp_min(0)
        frm, to, promo = ids // 320, ids // 5 % 64, ids % 5
        row = torch.arange(batch, device=x.device)[:, None]
        logits = (a[row, frm, promo] * b[row, to, promo]).sum(-1)
        logits = logits / math.sqrt(self.cfg.head_dim)
        logits = logits + self.origin_bias(x)[row, frm, promo]
        logits = logits + self.destination_bias(x)[row, to, promo]
        return logits.masked_fill(legal < 0, float("-inf"))


def collate(items):
    width = max(len(item["legal"]) for item in items)
    legal = [item["legal"] + [-1] * (width - len(item["legal"])) for item in items]
    return {
        "pieces": torch.tensor([item["pieces"] for item in items], dtype=torch.long),
        "ep": torch.tensor([item["ep"] for item in items], dtype=torch.long),
        "context": torch.tensor([item["context"] for item in items], dtype=torch.float32),
        "legal": torch.tensor(legal, dtype=torch.long),
        "target": torch.tensor([item["target"] for item in items], dtype=torch.long),
        "elo": torch.tensor([item["elo"] for item in items], dtype=torch.long),
    }


def inputs(batch, device):
    return [batch[key].to(device) for key in ("pieces", "ep", "context", "legal")]


@torch.inference_mode()
def predict(checkpoint, fen, elo, device="cpu", top_k=5):
    if top_k < 1:
        raise ValueError("top_k deve essere positivo")
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("FEN non valida")
    bounds = ckpt["rating_bounds"]
    if not bounds[0] <= elo <= bounds[1]:
        raise ValueError(f"Rating fuori dal campione addestrato: {bounds}")
    legal = list(board.legal_moves)
    if not legal:
        return {"moves": [], "legal_move_count": 0, "other_probability": 0.,
                "terminal": True, "warning": "Prototipo non calibrato"}
    model = Policy(Config(**ckpt["config"])).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    pieces, ep, context = encode(board, elo)
    batch = collate([dict(pieces=pieces, ep=ep, context=context, elo=elo,
                          legal=[move_id(m) for m in legal], target=0)])
    probs = model(*inputs(batch, device)).float().softmax(-1)[0].cpu().tolist()
    moves = sorted(
        [{"uci": m.uci(), "san": board.san(m), "probability": p}
         for m, p in zip(legal, probs)],
        key=lambda m: m["probability"], reverse=True,
    )
    shown = moves[:top_k]
    return {"moves": shown, "legal_move_count": len(moves),
            "other_probability": sum(m["probability"] for m in moves[top_k:]),
            "elo": elo, "rating_system": "Lichess Glicko-2",
            "speed": ckpt["dataset"]["speed"], "step": ckpt["step"],
            "warning": "Prototipo sperimentale: probabilità non ancora calibrate",
            "config": asdict(model.cfg)}
