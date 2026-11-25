"""Versioned original personas and small, transparent lexical retrieval."""

import json
from importlib.resources import files

from jewelmentor.models import Evidence, Expert


class Catalog:
    def __init__(self):
        root = files("jewelmentor").joinpath("data")
        self.experts = [
            Expert.model_validate(v)
            for v in json.loads(root.joinpath("experts.json").read_text(encoding="utf-8"))
        ]
        self.knowledge = [
            Evidence.model_validate(v)
            for v in json.loads(root.joinpath("knowledge.json").read_text(encoding="utf-8"))
        ]

    def expert(self, expert_id: str) -> Expert:
        for expert in self.experts:
            if expert.id == expert_id:
                return expert
        raise KeyError(expert_id)

    def recommend(self, intent: str, requested: str | None) -> Expert:
        if requested:
            return self.expert(requested)
        return next((e for e in self.experts if intent in e.tags), self.experts[0])

    def search(self, text: str, intent: str) -> list[Evidence]:
        ranked = []
        for item in self.knowledge:
            score = (2 if intent != "clarify" and intent in item.tags else 0) + sum(
                len(tag) for tag in item.tags if tag.lower() in text.lower()
            )
            if score:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in ranked[:3]]

    def evidence(self, evidence_id: str) -> Evidence:
        return next(item for item in self.knowledge if item.id == evidence_id)
