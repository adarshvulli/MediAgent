from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from transformers import AutoModel, AutoTokenizer

from app_config import settings


TEMPLATES_PATH = Path(__file__).parent / "conversation_templates.json"


@dataclass
class IntentTemplate:
    name: str
    examples: List[str]
    response: str


class ConversationEngine:
    """
    Lightweight intent classifier using Qwen embeddings and template-based responses.
    Designed so that a generative model can be dropped in later without changing callers.
    """

    def __init__(self) -> None:
        self.device = torch.device("cpu")
        self.templates: Dict[str, IntentTemplate] = {}
        self.example_embeddings: Dict[str, torch.Tensor] = {}

        # Try to load Qwen embeddings, but fall back to keyword rules if the
        # architecture isn't supported by the installed transformers version.
        self.tokenizer = None
        self.model = None
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(settings.hf_model_path, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(settings.hf_model_path, trust_remote_code=True)
            self.model.to(self.device)
            self.model.eval()
        except Exception:
            # Embedding model unavailable – we will use simple keyword-based intent
            # classification but keep the same public API.
            self.tokenizer = None
            self.model = None

        self._load_templates()

    def _load_templates(self) -> None:
        raw = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
        for item in raw.get("intents", []):
            tmpl = IntentTemplate(
                name=item["name"],
                examples=item.get("examples", []),
                response=item.get("response", ""),
            )
            self.templates[tmpl.name] = tmpl
        # Pre-embed examples
        for intent_name, tmpl in self.templates.items():
            for ex in tmpl.examples:
                key = f"{intent_name}::{ex}"
                self.example_embeddings[key] = self._embed_text(ex)

    @torch.no_grad()
    def _embed_text(self, text: str) -> torch.Tensor:
        if self.tokenizer is None or self.model is None:
            # Fallback embedding: simple bag-of-words vector over a small vocab.
            # For demo purposes this is enough to keep classify_intent working.
            vocab = [
                "hello",
                "insurance",
                "accept",
                "availability",
                "appointment",
                "schedule",
                "issue",
                "symptoms",
                "confirm",
                "book",
            ]
            text_lower = text.lower()
            vec = torch.zeros(len(vocab), dtype=torch.float32)
            for i, token in enumerate(vocab):
                if token in text_lower:
                    vec[i] = 1.0
            return vec

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model(**inputs)
        # Use mean pooling over last hidden state as a simple sentence embedding
        last_hidden = outputs.last_hidden_state  # (1, seq_len, hidden)
        mask = inputs["attention_mask"].unsqueeze(-1)  # (1, seq_len, 1)
        masked = last_hidden * mask
        summed = masked.sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1)
        return (summed / counts).cpu().squeeze(0)

    def classify_intent(self, text: str) -> Tuple[str, float]:
        """
        Return (intent_name, confidence).
        """
        if not text.strip():
            return "fallback", 0.0

        query_emb = self._embed_text(text)
        best_intent = "fallback"
        best_sim = -1.0

        for key, emb in self.example_embeddings.items():
            intent_name, _ = key.split("::", 1)
            sim = self._cosine_similarity(query_emb, emb)
            if sim > best_sim:
                best_sim = sim
                best_intent = intent_name

        # simple thresholding; below this treat as fallback
        if best_sim < 0.3:
            return "fallback", float(best_sim)
        return best_intent, float(best_sim)

    @staticmethod
    def _cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
        return float(torch.nn.functional.cosine_similarity(a, b, dim=0))

    def generate_reply(self, intent: str, context: Dict[str, str]) -> str:
        tmpl = self.templates.get(intent) or self.templates.get("fallback")
        base = tmpl.response
        try:
            text = base.format(**context)
        except KeyError:
            text = base
        # Make sure it's short and phone friendly
        return text.strip()


@lru_cache(maxsize=1)
def get_conversation_engine() -> ConversationEngine:
    return ConversationEngine()

