from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScreeningRequest(BaseModel):
    trade_date: str | None = Field(
        default=None,
        description="Trade date in YYYY-MM-DD or YYYYMMDD format. Defaults to today.",
    )
    use_demo_on_failure: bool = Field(
        default=True,
        description="Fallback to bundled demo data when Akshare is unavailable.",
    )


class ScreeningItem(BaseModel):
    stockName: str
    symbol: str
    floatMarketCap: str
    turnoverRate: str
    sealTime: str
    sealAmountOrLots: str
    limitUpDriver: str
    boardName: str
    boardLimitUpCount: int
    totalScore: float
    strategyTag: Literal["first_board_to_second", "weak_to_strong_2nd"]
    recommendReason: str


class MarketSummary(BaseModel):
    tradeDate: str
    limitUpCount: int
    firstBoardCount: int
    weakToStrongCount: int
    source: str
    notes: list[str] = Field(default_factory=list)


class ScreeningResponse(BaseModel):
    trade_date: str
    market_summary: MarketSummary
    items: list[ScreeningItem] = Field(default_factory=list)
    error: str | None = None


class ApiError(BaseModel):
    detail: str
