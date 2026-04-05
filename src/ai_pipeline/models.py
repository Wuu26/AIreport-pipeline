from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class RawItem(BaseModel):
    title: str
    url: str
    source: str  # "arxiv" | "huggingface" | "venturebeat" | "qbitai" | ...
    published_at: datetime
    content: str
    upvotes: int = 0


class FilterResult(BaseModel):
    score: float          # 0.0 - 1.0
    reason: str
    category: Literal["paper", "news", "china", "oss", "funding", "skip"]


class ScoredItem(RawItem):
    score: float
    reason: str
    category: Literal["paper", "news", "china", "oss", "funding", "skip"]
