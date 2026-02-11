from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn


class DKTModel(nn.Module):
    def __init__(self, num_kc: int, embed_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.num_kc = num_kc
        self.hidden_dim = hidden_dim
        self.embedding = nn.Embedding(2 * num_kc, embed_dim)
        self.lstm = nn.LSTM(input_size=embed_dim, hidden_size=hidden_dim, batch_first=True)
        self.output = nn.Linear(hidden_dim, num_kc)
        self.sigmoid = nn.Sigmoid()

    def forward(self, input_sequences: torch.Tensor) -> torch.Tensor:
        embeds = input_sequences
        lstm_out, _ = self.lstm(embeds)
        pred_logits = self.output(lstm_out)
        pred_probs = self.sigmoid(pred_logits)
        return pred_probs


@dataclass
class DKTArtifacts:
    model: DKTModel
    num_kc: int
    embed_dim: int
    hidden_dim: int
    kc_embedding: nn.Embedding


def load_knowledge_points(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"\bknowledge_points\b\s*=\s*\[", text)
    if not match:
        raise ValueError("knowledge_points not found in 最终结果.py")
    start = text.find("[", match.end() - 1)
    level = 0
    end = None
    for i, ch in enumerate(text[start:], start=start):
        if ch == "[":
            level += 1
        elif ch == "]":
            level -= 1
            if level == 0:
                end = i + 1
                break
    if end is None:
        raise ValueError("Failed to parse knowledge_points list")
    list_str = text[start:end]
    knowledge_points = ast.literal_eval(list_str)
    if not isinstance(knowledge_points, list):
        raise ValueError("knowledge_points is not a list")
    return knowledge_points


def load_model(model_path: Path, device: torch.device) -> DKTArtifacts:
    state_dict = torch.load(model_path, map_location=device)

    output_weight = state_dict["output.weight"]
    num_kc = int(output_weight.shape[0])
    hidden_dim = int(output_weight.shape[1])

    lstm_weight_ih = state_dict["lstm.weight_ih_l0"]
    embed_dim = int(lstm_weight_ih.shape[1])

    model = DKTModel(num_kc=num_kc, embed_dim=embed_dim, hidden_dim=hidden_dim).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    kc_embedding = nn.Embedding(2 * num_kc, embed_dim)
    if "embedding.weight" in state_dict:
        kc_embedding.weight.data.copy_(state_dict["embedding.weight"])
    kc_embedding.weight.requires_grad_(False)

    return DKTArtifacts(model=model, num_kc=num_kc, embed_dim=embed_dim, hidden_dim=hidden_dim, kc_embedding=kc_embedding)


class DKTInference:
    def __init__(self, model_path: Path, knowledge_points_path: Path) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.knowledge_points = load_knowledge_points(knowledge_points_path)
        self.kc_to_idx: dict[str, int] = {}
        for idx, name in enumerate(self.knowledge_points):
            if name not in self.kc_to_idx:
                self.kc_to_idx[name] = idx

        artifacts = load_model(model_path, self.device)
        self.model = artifacts.model
        self.num_kc = artifacts.num_kc
        self.embed_dim = artifacts.embed_dim
        self.kc_embedding = artifacts.kc_embedding

    def encode_interaction(self, kc_indices: Iterable[int], is_correct: bool) -> torch.Tensor:
        offset = 0 if is_correct else self.num_kc
        kc_indices = [kc + offset for kc in kc_indices]
        kc_indices_tensor = torch.tensor(kc_indices, dtype=torch.long)
        with torch.no_grad():
            vec = self.kc_embedding(kc_indices_tensor).sum(dim=0)
        return vec

    def predict_mastery(self, interactions: list[tuple[list[int], bool]]) -> list[float]:
        if not interactions:
            return [0.5 for _ in range(self.num_kc)]

        seq_len = len(interactions)
        X = torch.zeros(1, seq_len, self.embed_dim)
        for t, (kc_list, is_correct) in enumerate(interactions):
            X[0, t] = self.encode_interaction(kc_list, is_correct)

        X = X.to(self.device)
        with torch.no_grad():
            pred_seq = self.model(X)
            last_probs = pred_seq[0, -1].detach().cpu()
        return [float(p) for p in last_probs]

