"""Structural and source-membership checks, not factual verification."""

from pydantic import BaseModel, Field, ConfigDict
from typing import List
from urllib.parse import urlsplit


class MarketFact(BaseModel):
    model_config = ConfigDict(strict=True)
    fact: str = Field(min_length=1)
    source: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class MarketReport(BaseModel):
    topic: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    references: List[str] = Field(min_length=1)
    timestamp: str
    facts: List[MarketFact] = Field(min_length=1)


def validate_facts(facts: List[dict], allowed_sources=None) -> bool:
    try:
        if not isinstance(facts, list) or not facts:
            return False
        for item in facts:
            fact = MarketFact.model_validate(item)
            url = urlsplit(fact.source)
            if (
                not fact.fact.strip()
                or url.scheme not in {"http", "https"}
                or not url.hostname
            ):
                return False
            if url.username or url.password:
                return False
            if allowed_sources is not None and fact.source not in allowed_sources:
                return False
        return True
    except (ValueError, TypeError):
        return False


def validate_report(report: dict, allowed_sources=None) -> bool:
    try:
        parsed = MarketReport.model_validate(report)
        if not parsed.topic.strip() or not parsed.summary.strip():
            return False
        if not validate_facts(report["facts"], allowed_sources):
            return False
        fact_sources = {fact.source for fact in parsed.facts}
        return set(parsed.references) == fact_sources
    except (ValueError, TypeError, KeyError):
        return False
