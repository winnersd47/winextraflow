"""Deep signal analysis using LLM reasoning models.

Uses DeepSeek V3.2-Speciale (ultra-reasoning) as primary, with OpenAI GPT-4o fallback.
Provides SWOT analysis, BCG portfolio matrix, and period performance reviews.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Primary: DeepSeek V3.2 API (OpenAI-compatible)
_DEEPSEEK_BASE = "https://api.deepseek.com/v1"
_OPENAI_BASE = "https://api.openai.com/v1"


@dataclass
class DeepAnalysisResult:
    analysis_type: str
    content: dict[str, Any]
    provider: str
    model: str
    raw_text: str = ""


class DeepAnalysisService:
    """LLM-powered deep analysis for trading signals and portfolios."""

    def __init__(self, deepseek_key: str = "", openai_key: str = "") -> None:
        self._deepseek_key = deepseek_key
        self._openai_key = openai_key

    async def _chat(self, prompt: str, system: str, json_mode: bool = True) -> tuple[str, str, str]:
        """Call DeepSeek reasoner with OpenAI fallback. Returns (text, provider, model)."""
        if self._deepseek_key:
            try:
                return await self._call_openai_compat(
                    _DEEPSEEK_BASE, self._deepseek_key,
                    "deepseek-reasoner", prompt, system, json_mode,
                )
            except Exception as exc:
                logger.warning("DeepSeek failed: %s — falling back to OpenAI", exc)

        if self._openai_key:
            return await self._call_openai_compat(
                _OPENAI_BASE, self._openai_key,
                "gpt-4o", prompt, system, json_mode,
            )

        # Stub mode — no API keys
        return self._stub(prompt), "stub", "stub"

    async def _call_openai_compat(
        self, base: str, key: str, model: str, prompt: str, system: str, json_mode: bool
    ) -> tuple[str, str, str]:
        extra: dict[str, Any] = {}
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(base_url=base, timeout=120) as client:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4096,
                    **extra,
                },
            )
            resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"] or ""
        return text, base.split(".")[1], model

    def _stub(self, prompt: str) -> str:
        if "swot" in prompt.lower():
            return json.dumps({
                "strengths": ["Strong trend momentum", "High R:R ratio"],
                "weaknesses": ["Low volume confirmation", "Single timeframe analysis"],
                "opportunities": ["Breakout from key resistance level"],
                "threats": ["Upcoming economic data release", "Market volatility spike"],
                "recommendation": "buy",
                "confidence": 0.72,
            })
        if "bcg" in prompt.lower() or "portfolio" in prompt.lower():
            return json.dumps({
                "stars": [{"ticker": "BTC", "reason": "High growth, high share"}],
                "cash_cows": [{"ticker": "ETH", "reason": "Stable returns, large position"}],
                "question_marks": [{"ticker": "SOL", "reason": "High growth potential, uncertain"}],
                "dogs": [{"ticker": "XRP", "reason": "Low growth, low returns"}],
                "rebalancing": "Reduce dogs, increase stars exposure by 10%",
            })
        return json.dumps({"summary": "[STUB] Deep analysis placeholder", "confidence": 0.5})

    # ── Public API ────────────────────────────────────────────────────────────

    async def swot_analysis(
        self,
        ticker: str,
        entry_price: float,
        current_price: float,
        take_profit: float | None,
        stop_loss: float | None,
        provider_win_rate: float | None,
        recent_news: str = "",
    ) -> DeepAnalysisResult:
        """Generate SWOT analysis for a trading signal."""
        system = (
            "You are a professional quant analyst. Analyze trading signals with precise, "
            "data-driven SWOT analysis. Always include a final recommendation and confidence score."
        )
        prompt = f"""Perform a SWOT analysis for this trading signal:

Ticker: {ticker}
Entry price: {entry_price}
Current price: {current_price}
Take profit: {take_profit or 'not set'}
Stop loss: {stop_loss or 'not set'}
Provider win rate: {f'{provider_win_rate:.1%}' if provider_win_rate else 'unknown'}
Recent news context: {recent_news or 'none provided'}

Return JSON with keys:
  strengths (list of strings),
  weaknesses (list of strings),
  opportunities (list of strings),
  threats (list of strings),
  recommendation (buy|hold|sell),
  confidence (0.0 to 1.0),
  summary (one sentence)
"""
        text, provider, model = await self._chat(prompt, system)
        try:
            content = json.loads(text)
        except json.JSONDecodeError:
            content = {"error": "Failed to parse response", "raw": text[:500]}
        return DeepAnalysisResult("swot", content, provider, model, text)

    async def bcg_portfolio(
        self,
        positions: list[dict[str, Any]],
        market_growth_rates: dict[str, float] | None = None,
    ) -> DeepAnalysisResult:
        """BCG matrix analysis for a portfolio of positions.

        positions: [{"ticker": str, "weight": float, "pnl_pct": float, "volume_rank": int}]
        """
        system = (
            "You are a portfolio strategist. Use the BCG Growth-Share Matrix to classify "
            "portfolio positions and provide rebalancing recommendations."
        )
        positions_str = json.dumps(positions, ensure_ascii=False, indent=2)
        growth_str = json.dumps(market_growth_rates or {}, ensure_ascii=False)
        prompt = f"""Classify this portfolio using the BCG matrix:

Positions:
{positions_str}

Market growth rates (annual %): {growth_str}

Classify each ticker as: Stars (high growth + high share), Cash Cows, Question Marks, Dogs.

Return JSON:
  stars (list of {{ticker, reason}}),
  cash_cows (list of {{ticker, reason}}),
  question_marks (list of {{ticker, reason}}),
  dogs (list of {{ticker, reason}}),
  rebalancing (string recommendation),
  summary (one sentence)
"""
        text, provider, model = await self._chat(prompt, system)
        try:
            content = json.loads(text)
        except json.JSONDecodeError:
            content = {"error": "Parse failed", "raw": text[:500]}
        return DeepAnalysisResult("bcg_portfolio", content, provider, model, text)

    async def period_review(
        self,
        period: str,
        signals_summary: dict[str, Any],
        provider_name: str = "",
    ) -> DeepAnalysisResult:
        """AI-generated performance review for a trading period (month/quarter/year)."""
        system = (
            "You are a trading performance coach. Generate a concise but insightful "
            "review of trading period results. Identify patterns, strengths, and areas for improvement."
        )
        prompt = f"""Generate a trading performance review for: {period}
Provider: {provider_name or 'Portfolio'}

Statistics:
{json.dumps(signals_summary, ensure_ascii=False, indent=2)}

Return JSON:
  headline (one-line summary),
  performance_grade (A/B/C/D/F),
  key_wins (list of strings),
  key_losses (list of strings),
  patterns_identified (list of strings),
  recommendations (list of 3 actionable improvements),
  outlook (brief forward-looking statement)
"""
        text, provider, model = await self._chat(prompt, system)
        try:
            content = json.loads(text)
        except json.JSONDecodeError:
            content = {"error": "Parse failed", "raw": text[:500]}
        return DeepAnalysisResult("period_review", content, provider, model, text)


def _make_service() -> DeepAnalysisService:
    try:
        from app.config import settings
        return DeepAnalysisService(
            deepseek_key=settings.deepseek_api_key,
            openai_key=settings.openai_api_key,
        )
    except Exception:
        return DeepAnalysisService()


deep_analysis_service = _make_service()
