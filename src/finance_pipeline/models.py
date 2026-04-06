"""Finance pipeline data models."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class PricePoint(BaseModel):
    symbol: str        # e.g. "NVDA", "0700.HK", "BTC"
    name: str          # e.g. "英伟达", "腾讯", "Bitcoin"
    price: float
    change_pct: float  # e.g. +1.23 means +1.23%
    currency: str = "USD"


class MarketSnapshot(BaseModel):
    mode: Literal["morning", "evening"]
    indices: list[PricePoint]
    futures: list[PricePoint]    # only populated in evening mode
    watchlist: list[PricePoint]
    crypto: list[PricePoint]
    timestamp: datetime


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str
