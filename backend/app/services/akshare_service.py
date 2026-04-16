from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import akshare as ak
import pandas as pd

from .cache_service import JsonCacheService


def _normalize_trade_date(trade_date: str | None) -> tuple[str, str]:
    if trade_date:
        cleaned = trade_date.replace("-", "")
    else:
        cleaned = datetime.now().strftime("%Y%m%d")
    pretty = f"{cleaned[0:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned, pretty


@dataclass
class MarketDataset:
    trade_date: str
    source: str
    limit_up_pool: pd.DataFrame
    previous_limit_up_pool: pd.DataFrame
    board_snapshot: pd.DataFrame


class AkshareDataService:
    def __init__(self, cache_service: JsonCacheService | None = None, max_retries: int = 1) -> None:
        self.cache_service = cache_service or JsonCacheService()
        self.max_retries = max_retries

    def _run_with_cache(
        self,
        cache_key: str,
        fetcher: Callable[[], pd.DataFrame],
    ) -> tuple[pd.DataFrame, str]:
        last_error: Exception | None = None
        for _ in range(self.max_retries):
            try:
                frame = fetcher()
                if frame is not None and not frame.empty:
                    records = frame.to_dict(orient="records")
                    self.cache_service.save(cache_key, records)
                    return frame, "live"
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = exc

        cached = self.cache_service.load(cache_key)
        if cached:
            return pd.DataFrame(cached), "cache"

        if last_error is not None:
            raise last_error
        return pd.DataFrame(), "empty"

    def get_market_dataset(self, trade_date: str | None = None) -> MarketDataset:
        compact_date, pretty_date = _normalize_trade_date(trade_date)
        limit_up_pool, limit_up_source = self._run_with_cache(
            f"limit_up_pool_{compact_date}",
            lambda: ak.stock_zt_pool_em(date=compact_date),
        )
        previous_limit_up_pool, previous_source = self._run_with_cache(
            f"previous_limit_up_pool_{compact_date}",
            lambda: ak.stock_zt_pool_previous_em(date=compact_date),
        )
        try:
            board_snapshot, board_source = self._run_with_cache(
                f"industry_board_snapshot_{compact_date}",
                lambda: ak.stock_board_industry_name_em(),
            )
        except Exception:  # pragma: no cover - network dependent
            board_snapshot, board_source = pd.DataFrame(), "empty"

        source = ",".join(
            sorted({limit_up_source, previous_source, board_source} - {"empty"}) or {"empty"}
        )
        return MarketDataset(
            trade_date=pretty_date,
            source=source,
            limit_up_pool=limit_up_pool,
            previous_limit_up_pool=previous_limit_up_pool,
            board_snapshot=board_snapshot,
        )

    def get_stock_history(self, symbol: str, trade_date: str | None = None) -> pd.DataFrame:
        compact_date, _ = _normalize_trade_date(trade_date)
        cache_key = f"hist_{symbol}_{compact_date}"

        def fetcher() -> pd.DataFrame:
            return ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20230101",
                end_date=compact_date,
                adjust="qfq",
            )

        frame, _ = self._run_with_cache(cache_key, fetcher)
        return frame
