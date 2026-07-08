"""LLM 클라이언트 래퍼 — Claude(Anthropic) 있으면 사용, 없으면 규칙 폴백.

에이전트의 '판단'은 결정적(규칙+DNN)으로 유지해 지표를 재현 가능하게 하고,
LLM은 위협 분석·사고보고의 '자연어 서술'을 담당한다(통합본 Part 6 'LLM 위협분석').
키가 없거나 호출 실패 시 None을 반환 → 호출측이 규칙 기반 템플릿으로 폴백.
"""
from __future__ import annotations
import os


class LLMClient:
    def __init__(self, cfg: dict):
        llm = cfg.get("llm", {})
        self.model = llm.get("model", "claude-haiku-4-5")
        self.max_tokens = int(llm.get("max_tokens", 1200))
        mode = llm.get("enabled", "auto")
        self.available = False
        self._client = None
        if mode != "off" and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                self.available = True
            except Exception:
                self.available = False

    @property
    def status(self) -> str:
        return f"Claude({self.model})" if self.available else "규칙 폴백(LLM 키 없음)"

    def complete(self, system: str, user: str) -> str | None:
        if not self.available:
            return None
        try:
            msg = self._client.messages.create(
                model=self.model, max_tokens=self.max_tokens,
                system=system, messages=[{"role": "user", "content": user}])
            parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
            text = "\n".join(parts).strip()
            return text or None
        except Exception:
            return None
