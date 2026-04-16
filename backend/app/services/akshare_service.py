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


@dataclass
class MarketOverviewSnapshot:
    market_overview: str
    turnover_overview: str
    notes: list[str]


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

    def get_limit_down_pool(self, trade_date: str | None = None) -> pd.DataFrame:
        compact_date, _ = _normalize_trade_date(trade_date)
        frame, _ = self._run_with_cache(
            f"limit_down_pool_{compact_date}",
            lambda: ak.stock_zt_pool_dtgc_em(date=compact_date),
        )
        return frame

    def get_market_overview(self, trade_date: str | None = None) -> MarketOverviewSnapshot:
        compact_date, pretty_date = _normalize_trade_date(trade_date)
        notes: list[str] = []
        snapshots: list[dict[str, float | str]] = []
        cached_indexes: list[str] = []
        for display_name, symbol in (
            ("沪指", "sh000001"),
            ("深成指", "sz399001"),
            ("创业板指", "sz399006"),
        ):
            try:
                index_frame, source = self._run_with_cache(
                    f"index_daily_tx_{symbol}_{compact_date}",
                    lambda symbol=symbol: ak.stock_zh_index_daily_tx(symbol=symbol),
                )
                if source == "cache":
                    cached_indexes.append(display_name)
                snapshot = self._extract_index_snapshot(index_frame, pretty_date, display_name)
                if snapshot is not None:
                    snapshots.append(snapshot)
            except Exception:  # pragma: no cover - network dependent
                continue

        if cached_indexes:
            notes.append(f"部分指数行情来自本地缓存：{'、'.join(cached_indexes)}。")
        if len(snapshots) < 3:
            notes.append("部分指数行情获取失败，已使用可用指数样本继续生成情绪信号。")

        market_overview = self._format_index_overview(snapshots)
        turnover_overview = self._format_turnover_overview(snapshots)
        if turnover_overview != "成交额暂不可用。":
            notes.append("成交额采用沪指、深成指、创业板指样本汇总口径。")
        if market_overview == "指数行情暂不可用。" and turnover_overview == "成交额暂不可用。":
            notes.append("指数行情暂不可用，已仅基于涨停/跌停/连板指标生成情绪信号。")
        return MarketOverviewSnapshot(
            market_overview=market_overview,
            turnover_overview=turnover_overview,
            notes=notes,
        )

    @staticmethod
    def _extract_index_snapshot(
        index_frame: pd.DataFrame,
        trade_date: str,
        display_name: str,
    ) -> dict[str, float | str] | None:
        if index_frame.empty or "date" not in index_frame.columns:
            return None
        frame = index_frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"]).sort_values("date")
        if frame.empty:
            return None
        target_date = pd.Timestamp(trade_date)
        eligible = frame[frame["date"] <= target_date]
        if eligible.empty:
            return None
        current_idx = eligible.index[-1]
        current_pos = frame.index.get_loc(current_idx)
        if current_pos == 0:
            return None
        current_row = frame.iloc[current_pos]
        previous_row = frame.iloc[current_pos - 1]
        close_price = pd.to_numeric(current_row.get("close"), errors="coerce")
        prev_close = pd.to_numeric(previous_row.get("close"), errors="coerce")
        amount = pd.to_numeric(current_row.get("amount"), errors="coerce")
        prev_amount = pd.to_numeric(previous_row.get("amount"), errors="coerce")
        if pd.isna(close_price) or pd.isna(prev_close) or prev_close <= 0:
            return None
        pct_change = (close_price / prev_close - 1) * 100
        amount_change = 0.0
        if not pd.isna(amount) and not pd.isna(prev_amount):
            amount_change = float(amount - prev_amount)
        return {
            "name": display_name,
            "pct_change": float(pct_change),
            "amount": float(amount) if not pd.isna(amount) else 0.0,
            "amount_change": amount_change,
        }

    @staticmethod
    def _format_index_overview(index_snapshots: list[dict[str, float | str]]) -> str:
        if not index_snapshots:
            return "指数行情暂不可用。"
        values: list[str] = []
        for snapshot in index_snapshots:
            display_name = str(snapshot.get("name", "")).strip()
            pct = pd.to_numeric(snapshot.get("pct_change"), errors="coerce")
            if not display_name or pd.isna(pct):
                continue
            values.append(f"{display_name}{pct:+.2f}%")
        return "，".join(values) if values else "指数行情暂不可用。"

    @staticmethod
    def _format_turnover_overview(index_snapshots: list[dict[str, float | str]]) -> str:
        if not index_snapshots:
            return "成交额暂不可用。"
        turnover = sum(
            pd.to_numeric(snapshot.get("amount"), errors="coerce")
            for snapshot in index_snapshots
        )
        turnover_change = sum(
            pd.to_numeric(snapshot.get("amount_change"), errors="coerce")
            for snapshot in index_snapshots
        )
        if pd.isna(turnover) or turnover <= 0:
            return "成交额暂不可用。"
        direction = "放量" if turnover_change >= 0 else "缩量"
        return (
            f"{turnover / 1_000_000_000:.2f}万亿，"
            f"较上个交易日{direction}{abs(turnover_change) / 100_000_000:.2f}亿"
        )
