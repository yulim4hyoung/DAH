"""🔴 Recon 에이전트 — 대상 신호/인프라 식별(통합본 Part 4 §8)."""
from __future__ import annotations


class ReconAgent:
    def __init__(self, llm=None):
        self.llm = llm

    def run(self, scn) -> str:
        base = f"대상: {scn.TARGET} · 계층 {scn.LAYER} · 관점 {scn.PERSPECTIVE}"
        return base
