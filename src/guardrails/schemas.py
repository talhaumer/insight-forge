from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MarketFact(BaseModel):
    fact: str = Field(description="The extracted fact")
    source: str = Field(description="Source URL or reference")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")


class MarketReport(BaseModel):
    topic: str = Field(description="Research topic")
    summary: str = Field(description="Concise report summary")
    references: List[str] = Field(description="List of source URLs")
    timestamp: str = Field(description="ISO8601 timestamp")
    facts: List[MarketFact] = Field(description="Structured facts")


def validate_facts(facts: List[dict]) -> bool:
    """Validate facts against schema"""
    try:
        for fact in facts:
            MarketFact(**fact)
        return True
    except Exception:
        return False


def validate_report(report: dict) -> bool:
    """Validate report against schema"""
    try:
        MarketReport(**report)
        return True
    except Exception:
        return False
