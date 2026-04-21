from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import os
from zoneinfo import ZoneInfo

import pandas as pd

from ..data.sample_data import build_demo_first_board, build_demo_weak_to_strong
from ..models.schemas import (
    MarketSignalIndicator,
    MarketSignalResponse,
    MarketSummary,
    ScreeningItem,
    ScreeningResponse,
)
from .akshare_service import AkshareDataService, MarketDataset

CN_TZ = ZoneInfo("Asia/Shanghai")
MIN_CANDIDATE_PRICE = 2.0
MAX_CANDIDATE_PRICE = 40.0


@dataclass
class CandidateContext:
    board_counts: dict[str, int]
    board_ranks: dict[str, int]
    board_strength: dict[str, float]
    board_drivers: dict[str, str]


@dataclass
class ScreeningBuildResult:
    items: list[ScreeningItem]
    notes: list[str]


class ScreenerService:
    def __init__(self, data_service: AkshareDataService | None = None) -> None:
        self.data_service = data_service or AkshareDataService()

    def screen_first_board(
        self,
        trade_date: str | None,
        use_demo_on_failure: bool,
        force_refresh: bool = False,
    ) -> ScreeningResponse:
        guard_response = self._screening_trade_date_guard(trade_date)
        if guard_response is not None:
            return guard_response
        try:
            dataset = self.data_service.get_market_dataset(trade_date, force_refresh=force_refresh)
            first_board_result = self._build_first_board_items(dataset, force_refresh=force_refresh)
            items = first_board_result.items
            if self._should_use_demo(dataset, items) and use_demo_on_failure:
                return build_demo_first_board(dataset.trade_date)
            return ScreeningResponse(
                trade_date=dataset.trade_date,
                market_summary=self._market_summary(
                    dataset,
                    len(items),
                    0,
                    extra_notes=first_board_result.notes,
                ),
                items=sorted(items, key=lambda item: item.totalScore, reverse=True),
                error=None,
            )
        except Exception as exc:
            if use_demo_on_failure:
                return build_demo_first_board(self._normalize_date(trade_date))
            raise RuntimeError(f"Failed to screen first-board pool: {exc}") from exc

    def screen_weak_to_strong(
        self,
        trade_date: str | None,
        use_demo_on_failure: bool,
        force_refresh: bool = False,
    ) -> ScreeningResponse:
        guard_response = self._screening_trade_date_guard(trade_date)
        if guard_response is not None:
            return guard_response
        try:
            dataset = self.data_service.get_market_dataset(trade_date, force_refresh=force_refresh)
            weak_to_strong_result = self._build_weak_to_strong_items(dataset)
            items = weak_to_strong_result.items
            if self._should_use_demo(dataset, items) and use_demo_on_failure:
                return build_demo_weak_to_strong(dataset.trade_date)
            return ScreeningResponse(
                trade_date=dataset.trade_date,
                market_summary=self._market_summary(
                    dataset,
                    0,
                    len(items),
                    extra_notes=weak_to_strong_result.notes,
                ),
                items=sorted(
                    items,
                    key=lambda item: (
                        item.totalScore if item.totalScore is not None else 0.0,
                        item.boardLimitUpCount,
                        -item.boardRank,
                    ),
                    reverse=True,
                ),
                error=None,
            )
        except Exception as exc:
            if use_demo_on_failure:
                return build_demo_weak_to_strong(self._normalize_date(trade_date))
            raise RuntimeError(f"Failed to screen weak-to-strong pool: {exc}") from exc

    def screen_top5(
        self,
        trade_date: str | None,
        use_demo_on_failure: bool,
        force_refresh: bool = False,
    ) -> ScreeningResponse:
        guard_response = self._screening_trade_date_guard(trade_date)
        if guard_response is not None:
            return guard_response
        try:
            dataset = self.data_service.get_market_dataset(trade_date, force_refresh=force_refresh)
            first_board_result = self._build_first_board_items(dataset, force_refresh=force_refresh)
            weak_to_strong_result = self._build_weak_to_strong_items(dataset)
            first_board_items = first_board_result.items
            weak_to_strong_items = weak_to_strong_result.items

            if self._should_use_demo(dataset, [*first_board_items, *weak_to_strong_items]) and use_demo_on_failure:
                first_board = build_demo_first_board(dataset.trade_date)
                weak_to_strong = build_demo_weak_to_strong(dataset.trade_date)
            else:
                first_board = ScreeningResponse(
                    trade_date=dataset.trade_date,
                    market_summary=self._market_summary(
                        dataset,
                        len(first_board_items),
                        0,
                        extra_notes=first_board_result.notes,
                    ),
                    items=sorted(first_board_items, key=lambda item: item.totalScore, reverse=True),
                    error=None,
                )
                weak_to_strong = ScreeningResponse(
                    trade_date=dataset.trade_date,
                    market_summary=self._market_summary(
                        dataset,
                        0,
                        len(weak_to_strong_items),
                        extra_notes=weak_to_strong_result.notes,
                    ),
                    items=sorted(
                        weak_to_strong_items,
                        key=lambda item: (
                            item.totalScore if item.totalScore is not None else 0.0,
                            item.boardLimitUpCount,
                            -item.boardRank,
                        ),
                        reverse=True,
                    ),
                    error=None,
                )
        except Exception as exc:
            if use_demo_on_failure:
                normalized_date = self._normalize_date(trade_date)
                first_board = build_demo_first_board(normalized_date)
                weak_to_strong = build_demo_weak_to_strong(normalized_date)
            else:
                raise RuntimeError(f"Failed to screen top5 pool: {exc}") from exc

        combined: dict[str, ScreeningItem] = {}
        for item in [*first_board.items, *weak_to_strong.items]:
            scored = self._with_recommendation_score(item)
            existing = combined.get(scored.symbol)
            if existing is None or scored.totalScore > existing.totalScore:
                combined[scored.symbol] = scored
        top5 = sorted(combined.values(), key=lambda item: item.totalScore, reverse=True)[:5]
        source = ",".join(
            sorted(
                set(first_board.market_summary.source.split(","))
                | set(weak_to_strong.market_summary.source.split(","))
            )
        )
        notes = list(dict.fromkeys([*first_board.market_summary.notes, *weak_to_strong.market_summary.notes]))
        summary = MarketSummary(
            tradeDate=first_board.trade_date,
            limitUpCount=max(
                first_board.market_summary.limitUpCount,
                weak_to_strong.market_summary.limitUpCount,
            ),
            firstBoardCount=len(first_board.items),
            weakToStrongCount=len(weak_to_strong.items),
            source=source,
            notes=notes,
        )
        return ScreeningResponse(
            trade_date=first_board.trade_date,
            market_summary=summary,
            items=top5,
            error=None,
        )

    def build_market_signal(
        self,
        trade_date: str | None,
        use_demo_on_failure: bool,
        force_refresh: bool = False,
    ) -> MarketSignalResponse:
        normalized_date = self._normalize_date(trade_date)
        today = datetime.now(CN_TZ).strftime("%Y-%m-%d")
        if normalized_date > today:
            return MarketSignalResponse(
                trade_date=normalized_date,
                weekday=self._weekday_label(normalized_date),
                marketOverview="请求交易日尚未到达，暂无可用收盘数据。",
                turnoverOverview="请求交易日尚未到达，暂无可用沪深京成交额收盘数据。",
                regime="YELLOW",
                regimeLabel="黄灯",
                positionAdvice="请求日期为未来交易日，建议等待收盘后再查询。",
                indicators=[],
                notes=["未来交易日不返回历史缓存回填结果。"],
                error=None,
            )
        try:
            # Core signal data paths run in parallel to avoid serial blocking on force refresh.
            with ThreadPoolExecutor(max_workers=2) as executor:
                dataset_future = executor.submit(
                    self.data_service.get_market_dataset,
                    trade_date,
                    force_refresh,
                )
                limit_down_future = executor.submit(
                    self.data_service.get_limit_down_pool,
                    trade_date,
                    force_refresh,
                )
                dataset = dataset_future.result()
                limit_down_pool = limit_down_future.result()

            # Respect force_refresh to avoid serving stale same-day index snapshots
            # captured before market close.
            market_snapshot = self.data_service.get_market_overview(
                trade_date,
                force_refresh=force_refresh,
            )
            if not market_snapshot.has_valid_close:
                return MarketSignalResponse(
                    trade_date=normalized_date,
                    weekday=self._weekday_label(normalized_date),
                    marketOverview=market_snapshot.market_overview,
                    turnoverOverview=market_snapshot.turnover_overview,
                    regime="YELLOW",
                    regimeLabel="黄灯",
                    positionAdvice="当日未收盘，建议仅观察，不执行收盘后策略。",
                    indicators=[],
                    notes=list(market_snapshot.notes),
                    error=None,
                )

            limit_up_count = int(len(dataset.limit_up_pool.index))
            highest_board_row = self._highest_board_row(dataset.limit_up_pool)
            highest_board = int(self._to_float(highest_board_row.get("连板数")))
            highest_board_name = str(highest_board_row.get("名称", "--")).strip() or "--"
            promotion_rate, promotion_desc = self._promotion_rate(dataset)
            limit_down_count = int(len(limit_down_pool.index))
            has_limit_down_wave = limit_down_count > limit_up_count if limit_up_count > 0 else limit_down_count > 0

            regime = self._market_regime(
                limit_up_count=limit_up_count,
                highest_board=highest_board,
                promotion_rate=promotion_rate,
                has_limit_down_wave=has_limit_down_wave,
            )
            weekday = self._weekday_label(dataset.trade_date)
            indicators = [
                MarketSignalIndicator(
                    name="涨停家数",
                    todayValue=f"{limit_up_count}家（不含ST/退市）",
                    standard=">60（绿灯）/ 40-60（黄灯）/ <40（红灯）",
                    status=self._limit_up_status(limit_up_count),
                ),
                MarketSignalIndicator(
                    name="最高连板",
                    todayValue=f"{highest_board}板（{highest_board_name}）" if highest_board > 0 else "--",
                    standard="≥5（绿灯）/ ≥4（黄灯）",
                    status=self._highest_board_status(highest_board),
                ),
                MarketSignalIndicator(
                    name="连板晋级率",
                    todayValue=promotion_desc,
                    standard=">25%（绿灯）/ ≤25%（黄灯）",
                    status=self._promotion_status(promotion_rate),
                ),
                MarketSignalIndicator(
                    name="跌停潮",
                    todayValue=f"{limit_down_count}只跌停，{'跌停家数已超过涨停家数' if has_limit_down_wave else '未超过涨停家数'}",
                    standard="跌停家数不高于涨停家数",
                    status="红灯" if has_limit_down_wave else "绿灯",
                ),
            ]
            notes = list(market_snapshot.notes)
            if dataset.board_snapshot.empty:
                notes.append("板块快照暂不可用，板块排名采用涨停家数排序。")
            return MarketSignalResponse(
                trade_date=dataset.trade_date,
                weekday=weekday,
                marketOverview=market_snapshot.market_overview,
                turnoverOverview=market_snapshot.turnover_overview,
                regime=regime,
                regimeLabel=self._regime_label(regime),
                positionAdvice=self._position_advice(regime),
                indicators=indicators,
                notes=notes,
                error=None,
            )
        except Exception as exc:
            if use_demo_on_failure:
                normalized_date = self._normalize_date(trade_date)
                return MarketSignalResponse(
                    trade_date=normalized_date,
                    weekday=self._weekday_label(normalized_date),
                    marketOverview="指数行情数据暂不可用，已切换为情绪指标降级展示。",
                    turnoverOverview="成交额暂不可用。",
                    regime="YELLOW",
                    regimeLabel="黄灯",
                    positionAdvice="黄灯 + 一进二：仓位上限 40%，强制分仓两只各 20%。",
                    indicators=[],
                    notes=["Akshare unavailable, using bundled fallback market signal."],
                    error=None,
                )
            raise RuntimeError(f"Failed to build market signal: {exc}") from exc

    def _build_first_board_items(
        self,
        dataset: MarketDataset,
        force_refresh: bool = False,
    ) -> ScreeningBuildResult:
        if dataset.limit_up_pool.empty:
            return ScreeningBuildResult(items=[], notes=[])
        context = self._build_candidate_context(dataset)
        frame = dataset.limit_up_pool.copy()
        if "连板数" not in frame.columns:
            return ScreeningBuildResult(items=[], notes=[])
        frame = frame[frame["连板数"].fillna(0).astype(int) == 1]
        history_filter_map, history_fetch_failed_symbols = self._prefetch_history_filters(
            frame=frame,
            trade_date=dataset.trade_date,
            force_refresh=force_refresh,
        )
        items: list[ScreeningItem] = []
        skipped_history_count = 0
        for _, row in frame.iterrows():
            item, history_filter_skipped = self._screen_first_board_row(
                row,
                dataset.trade_date,
                context,
                force_refresh=force_refresh,
                history_filter_map=history_filter_map,
                history_fetch_failed_symbols=history_fetch_failed_symbols,
            )
            if history_filter_skipped:
                skipped_history_count += 1
            if item is not None:
                items.append(item)
        notes: list[str] = []
        if skipped_history_count > 0:
            notes.append(f"{skipped_history_count} 只个股历史行情不可用，已跳过历史过滤条件。")
        return ScreeningBuildResult(items=items, notes=notes)

    def _build_weak_to_strong_items(self, dataset: MarketDataset) -> ScreeningBuildResult:
        if dataset.limit_up_pool.empty:
            return ScreeningBuildResult(items=[], notes=[])
        context = self._build_candidate_context(dataset)
        frame = dataset.limit_up_pool.copy()
        if "连板数" not in frame.columns:
            return ScreeningBuildResult(items=[], notes=[])
        frame = frame[(frame["连板数"].fillna(0).astype(int) >= 2) & (frame["连板数"].fillna(0).astype(int) < 5)]
        items: list[ScreeningItem] = []
        for _, row in frame.iterrows():
            item = self._screen_weak_to_strong_row(row, context)
            if item is not None:
                items.append(item)
        return ScreeningBuildResult(items=items, notes=[])

    def _screen_first_board_row(
        self,
        row: pd.Series,
        trade_date: str,
        context: CandidateContext,
        force_refresh: bool = False,
        history_filter_map: dict[str, bool] | None = None,
        history_fetch_failed_symbols: set[str] | None = None,
    ) -> tuple[ScreeningItem | None, bool]:
        name = str(row.get("名称", "")).strip()
        symbol = str(row.get("代码", "")).strip()
        if not name or not symbol:
            return None, False
        if "ST" in name or symbol.startswith(("300", "688", "8", "4")):
            return None, False
        float_market_cap_yi = self._to_yi(row.get("流通市值"))
        if float_market_cap_yi < 20 or float_market_cap_yi > 200:
            return None, False
        history_filter_skipped = False
        if history_fetch_failed_symbols is not None and symbol in history_fetch_failed_symbols:
            history_filter_skipped = True
        elif history_filter_map is not None:
            if not history_filter_map.get(symbol, False):
                return None, False
        else:
            try:
                history = self.data_service.get_stock_history(
                    symbol=symbol,
                    trade_date=trade_date,
                    force_refresh=force_refresh,
                    allow_live_fetch=force_refresh,
                )
                if history.empty:
                    history_filter_skipped = True
                elif not self._passes_history_filters(history):
                    return None, False
            except Exception:
                history_filter_skipped = True

        turnover = self._to_float(row.get("换手率"))
        seal_funds = self._to_float(row.get("封板资金"))
        board_name = self._board_name(row)
        board_count = context.board_counts.get(board_name, 0)
        board_rank = context.board_ranks.get(board_name, 0)
        seal_time = self._format_time(row.get("首次封板时间"))
        latest_price = self._to_float(row.get("最新价"))
        if latest_price < MIN_CANDIDATE_PRICE or latest_price > MAX_CANDIDATE_PRICE:
            return None, history_filter_skipped
        seal_order_lots = self._format_seal_order_lots(seal_funds, latest_price)
        open_board_count = int(self._to_float(row.get("炸板次数")))

        score = 0.0
        score += self._score_first_limit_time(seal_time)
        score += self._score_turnover(turnover)
        score += self._score_seal_amount(self._to_yi(seal_funds))
        score += self._score_board_synergy(board_count)

        if score < 21:
            return None, history_filter_skipped

        reason = f"首板评分 {round(score, 1)} 分，{board_name} 板块涨停 {board_count} 家，板块排名第 {board_rank}。"

        return (
            ScreeningItem(
                stockName=name,
                symbol=symbol,
                floatMarketCap=f"{float_market_cap_yi:.2f}亿",
                boardName=board_name,
                boardRank=board_rank,
                boardLimitUpCount=board_count,
                turnoverRate=f"{turnover:.2f}%",
                sealTime=seal_time,
                sealOrderLots=seal_order_lots,
                openBoardCount=open_board_count,
                totalScore=round(score, 2),
                isLimitUp=True,
                strategyTag="first_board_to_second",
                recommendReason=reason,
            ),
            history_filter_skipped,
        )

    def _prefetch_history_filters(
        self,
        frame: pd.DataFrame,
        trade_date: str,
        force_refresh: bool,
    ) -> tuple[dict[str, bool], set[str]]:
        symbols = {
            str(value).strip()
            for value in frame.get("代码", pd.Series(dtype=object)).tolist()
            if str(value).strip()
        }
        if not symbols:
            return {}, set()

        max_workers = min(8, max(2, (os.cpu_count() or 4)))
        history_filter_map: dict[str, bool] = {}
        failed_symbols: set[str] = set()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    self._load_history_filter_passed,
                    symbol,
                    trade_date,
                    force_refresh,
                ): symbol
                for symbol in symbols
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                try:
                    history_filter_map[symbol] = future.result()
                except Exception:
                    failed_symbols.add(symbol)
        return history_filter_map, failed_symbols

    def _load_history_filter_passed(
        self,
        symbol: str,
        trade_date: str,
        force_refresh: bool,
    ) -> bool:
        history = self.data_service.get_stock_history(
            symbol=symbol,
            trade_date=trade_date,
            force_refresh=force_refresh,
            allow_live_fetch=force_refresh,
        )
        if history.empty:
            return True
        return self._passes_history_filters(history)

    def _screen_weak_to_strong_row(
        self,
        row: pd.Series,
        context: CandidateContext,
    ) -> ScreeningItem | None:
        name = str(row.get("名称", "")).strip()
        symbol = str(row.get("代码", "")).strip()
        if not name or not symbol:
            return None
        if "ST" in name or symbol.startswith(("300", "688", "8", "4")):
            return None
        board_name = self._board_name(row)
        board_count = context.board_counts.get(board_name, 0)
        board_rank = context.board_ranks.get(board_name, 0)
        if board_count < 1:
            return None
        float_market_cap_yi = self._to_yi(row.get("流通市值"))
        if float_market_cap_yi < 20 or float_market_cap_yi > 200:
            return None
        turnover = self._to_float(row.get("换手率"))
        if turnover < 3 or turnover > 20:
            return None
        first_time = self._format_time(row.get("首次封板时间"))
        last_time = self._format_time(row.get("最后封板时间"))
        board_break_count = int(self._to_float(row.get("炸板次数")))
        board_count_value = int(self._to_float(row.get("连板数")))
        is_weak_pattern = board_break_count >= 1 or self._is_late_board(last_time) or self._is_late_board(first_time)
        if not is_weak_pattern:
            return None
        seal_funds = self._to_float(row.get("封板资金"))
        board_strength = context.board_strength.get(board_name, 0.0)
        latest_price = self._to_float(row.get("最新价"))
        if latest_price < MIN_CANDIDATE_PRICE or latest_price > MAX_CANDIDATE_PRICE:
            return None
        is_limit_up = self._to_float(row.get("涨跌幅")) >= 9.5

        return ScreeningItem(
            stockName=name,
            symbol=symbol,
            floatMarketCap=f"{float_market_cap_yi:.2f}亿",
            boardName=board_name,
            boardRank=board_rank,
            boardLimitUpCount=board_count,
            turnoverRate=f"{turnover:.2f}%",
            sealTime=last_time,
            sealOrderLots=self._format_seal_order_lots(seal_funds, latest_price),
            openBoardCount=board_break_count,
            totalScore=None,
            isLimitUp=is_limit_up,
            strategyTag="weak_to_strong_2nd",
            recommendReason=f"{board_count_value} 板弱转强候选，板块强度 {board_strength:.2f}，炸板次数 {board_break_count}。",
        )

    def _build_candidate_context(self, dataset: MarketDataset) -> CandidateContext:
        board_counts: dict[str, int] = {}
        if not dataset.limit_up_pool.empty and "所属行业" in dataset.limit_up_pool.columns:
            board_counts = (
                dataset.limit_up_pool["所属行业"]
                .fillna("未知板块")
                .astype(str)
                .value_counts()
                .to_dict()
            )
        board_ranks: dict[str, int] = {}
        for index, (board_name, _) in enumerate(
            sorted(board_counts.items(), key=lambda item: (-item[1], item[0])),
            start=1,
        ):
            board_ranks[board_name] = index
        board_strength: dict[str, float] = {}
        if not dataset.board_snapshot.empty and "板块名称" in dataset.board_snapshot.columns:
            for _, row in dataset.board_snapshot.iterrows():
                board_strength[str(row.get("板块名称", "未知板块"))] = self._to_float(row.get("涨跌幅"))
        board_drivers: dict[str, str] = {}
        if not dataset.board_snapshot.empty and "板块名称" in dataset.board_snapshot.columns:
            for _, row in dataset.board_snapshot.iterrows():
                board_name = str(row.get("板块名称", "未知板块"))
                driver_name = str(row.get("领涨股票") or board_name)
                board_drivers[board_name] = driver_name
        return CandidateContext(
            board_counts=board_counts,
            board_ranks=board_ranks,
            board_strength=board_strength,
            board_drivers=board_drivers,
        )

    def _market_summary(
        self,
        dataset: MarketDataset,
        first_board_count: int,
        weak_to_strong_count: int,
        extra_notes: list[str] | None = None,
    ) -> MarketSummary:
        notes: list[str] = []
        if "cache" in dataset.source:
            notes.append("Part of the response came from local cache.")
        if dataset.limit_up_pool.empty:
            notes.append("Live limit-up pool was empty.")
        if extra_notes:
            notes.extend(extra_notes)
        return MarketSummary(
            tradeDate=dataset.trade_date,
            limitUpCount=int(len(dataset.limit_up_pool.index)),
            firstBoardCount=first_board_count,
            weakToStrongCount=weak_to_strong_count,
            source=dataset.source,
            notes=notes,
        )

    @staticmethod
    def _passes_history_filters(history: pd.DataFrame) -> bool:
        if history.empty:
            return False
        pct_change = pd.to_numeric(history.get("涨跌幅"), errors="coerce").fillna(0)
        if pct_change.empty:
            return False
        recent_limit_up = bool((pct_change.tail(60) >= 9.5).any())
        if not recent_limit_up:
            return False
        recent_streak = (pct_change.tail(120) >= 9.5).astype(int)
        max_streak = 0
        current_streak = 0
        for value in recent_streak:
            if value == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak < 4

    @staticmethod
    def _to_float(value: object) -> float:
        if value is None:
            return 0.0
        if isinstance(value, str):
            cleaned = value.replace("%", "").replace(",", "").strip()
            if not cleaned:
                return 0.0
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _to_yi(cls, value: object) -> float:
        numeric = cls._to_float(value)
        if numeric <= 0:
            return 0.0
        if numeric > 100000:
            return numeric / 100000000
        return numeric

    @staticmethod
    def _board_name(row: pd.Series) -> str:
        return str(row.get("所属行业") or row.get("所属行业名称") or "未知板块")

    @staticmethod
    def _format_time(value: object) -> str:
        numeric = str(value).split(".")[0].strip()
        if numeric in {"", "nan", "None"}:
            return "--"
        digits = "".join(ch for ch in numeric if ch.isdigit())
        if len(digits) == 6:
            return f"{digits[0:2]}:{digits[2:4]}:{digits[4:6]}"
        return numeric

    @staticmethod
    def _is_late_board(time_value: str) -> bool:
        if time_value == "--":
            return False
        return time_value >= "14:30:00"

    @staticmethod
    def _score_first_limit_time(seal_time: str) -> float:
        if seal_time == "--":
            return 0.0
        if seal_time <= "10:00:00":
            return 9.0
        if seal_time <= "10:30:00":
            return 6.0
        if seal_time <= "11:30:00":
            return 3.0
        return 0.0

    @staticmethod
    def _score_turnover(turnover: float) -> float:
        if 5 <= turnover <= 15:
            return 6.0
        if 3 <= turnover < 5 or 15 < turnover <= 20:
            return 4.0
        return 0.0

    @staticmethod
    def _score_seal_amount(seal_amount_yi: float) -> float:
        if seal_amount_yi >= 1:
            return 6.0
        if seal_amount_yi >= 0.5:
            return 4.0
        if seal_amount_yi >= 0.2:
            return 2.0
        return 0.0

    @staticmethod
    def _score_board_synergy(board_count: int) -> float:
        if board_count >= 3:
            return 6.0
        if board_count == 2:
            return 4.0
        if board_count == 1:
            return 1.0
        return 0.0

    @staticmethod
    def _normalize_date(trade_date: str | None) -> str:
        if not trade_date:
            return datetime.now(CN_TZ).strftime("%Y-%m-%d")
        if "-" in trade_date:
            return trade_date
        return f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

    def _screening_trade_date_guard(self, trade_date: str | None) -> ScreeningResponse | None:
        normalized_date = self._normalize_date(trade_date)
        now = datetime.now(CN_TZ)
        today = now.strftime("%Y-%m-%d")
        if normalized_date > today:
            return self._empty_screening_response(
                normalized_date,
                "请求交易日尚未到达，暂无可用收盘数据。",
                "未来交易日不返回历史缓存回填结果。",
            )
        if normalized_date == today and now.hour < 15:
            return self._empty_screening_response(
                normalized_date,
                "当日尚未收盘，暂无可用收盘数据。",
                "交易日未收盘，已停止使用昨日缓存/历史数据回填。",
            )
        return None

    @staticmethod
    def _empty_screening_response(trade_date: str, title_note: str, detail_note: str) -> ScreeningResponse:
        return ScreeningResponse(
            trade_date=trade_date,
            market_summary=MarketSummary(
                tradeDate=trade_date,
                limitUpCount=0,
                firstBoardCount=0,
                weakToStrongCount=0,
                source="guard",
                notes=[title_note, detail_note],
            ),
            items=[],
            error=None,
        )

    @staticmethod
    def _with_recommendation_score(item: ScreeningItem) -> ScreeningItem:
        board_bonus = min(item.boardLimitUpCount * 0.8, 6.0)
        strategy_bonus = 1.5 if item.strategyTag == "first_board_to_second" else 2.5
        base_score = item.totalScore or 0.0
        score = round(base_score + board_bonus + strategy_bonus, 2)
        return item.model_copy(
            update={
                "totalScore": score,
                "recommendReason": f"{item.recommendReason} 综合推荐分 {score}。",
            }
        )

    @staticmethod
    def _should_use_demo(dataset: MarketDataset, items: list[ScreeningItem]) -> bool:
        return dataset.limit_up_pool.empty and not items

    @staticmethod
    def _limit_up_driver(row: pd.Series, context: CandidateContext) -> str:
        for key in ("涨停统计", "涨停原因类别", "题材", "所属行业"):
            value = str(row.get(key, "")).strip()
            if value and value not in {"nan", "None"}:
                return value
        board_name = ScreenerService._board_name(row)
        return context.board_drivers.get(board_name, board_name)

    @staticmethod
    def _format_seal_order_lots(seal_funds: float, latest_price: float) -> str:
        if seal_funds <= 0 or latest_price <= 0:
            return "--"
        lots = seal_funds / latest_price / 100
        if lots >= 10000:
            return f"{lots / 10000:.2f}万手"
        return f"{lots:.0f}手"

    @staticmethod
    def _highest_board_row(limit_up_pool: pd.DataFrame) -> pd.Series:
        if limit_up_pool.empty or "连板数" not in limit_up_pool.columns:
            return pd.Series(dtype=object)
        frame = limit_up_pool.copy()
        frame["连板数"] = pd.to_numeric(frame["连板数"], errors="coerce").fillna(0)
        frame = frame.sort_values(["连板数", "封板资金"], ascending=[False, False])
        return frame.iloc[0] if not frame.empty else pd.Series(dtype=object)

    @staticmethod
    def _promotion_rate(dataset: MarketDataset) -> tuple[float, str]:
        previous = dataset.previous_limit_up_pool.copy()
        if previous.empty:
            return 0.0, "暂无昨日连板样本"
        if "昨日连板数" not in previous.columns:
            return 0.0, "昨日连板数据缺失"
        previous["昨日连板数"] = pd.to_numeric(previous["昨日连板数"], errors="coerce").fillna(0)
        previous_multiboard = previous[previous["昨日连板数"] >= 2]
        previous_count = int(len(previous_multiboard.index))
        if previous_count == 0:
            return 0.0, "昨日无连板股"
        today = dataset.limit_up_pool.copy()
        if today.empty or "连板数" not in today.columns:
            return 0.0, f"0%（昨日{previous_count}只连板，今日0只晋级）"
        today["连板数"] = pd.to_numeric(today["连板数"], errors="coerce").fillna(0)
        merged = today.merge(
            previous_multiboard[["代码", "昨日连板数"]],
            on="代码",
            how="inner",
        )
        promoted = merged[merged["连板数"] >= merged["昨日连板数"] + 1]
        promoted_count = int(len(promoted.index))
        rate = promoted_count / previous_count if previous_count else 0.0
        return rate, f"{rate:.0%}（昨日{previous_count}只连板，今日{promoted_count}只晋级）"

    @staticmethod
    def _market_regime(
        limit_up_count: int,
        highest_board: int,
        promotion_rate: float,
        has_limit_down_wave: bool,
    ) -> str:
        if limit_up_count < 40 or highest_board < 4 or has_limit_down_wave:
            return "RED"
        if limit_up_count > 60 and highest_board >= 5 and promotion_rate > 0.25:
            return "GREEN"
        return "YELLOW"

    @staticmethod
    def _regime_label(regime: str) -> str:
        return {"GREEN": "绿灯", "YELLOW": "黄灯", "RED": "红灯"}.get(regime, regime)

    def _position_advice(self, regime: str) -> str:
        if regime == "GREEN":
            return "绿灯 + 一进二：仓位上限 100%，可满仓总龙头或分仓两只。"
        if regime == "YELLOW":
            return "黄灯 + 一进二：仓位上限 40%，强制分仓两只各 20%。"
        return "红灯：不开新仓，仅允许 0-10% 观察仓。"

    @staticmethod
    def _limit_up_status(limit_up_count: int) -> str:
        if limit_up_count > 60:
            return "绿灯"
        if 40 <= limit_up_count <= 60:
            return "黄灯"
        return "红灯"

    @staticmethod
    def _highest_board_status(highest_board: int) -> str:
        if highest_board >= 5:
            return "绿灯"
        if highest_board >= 4:
            return "黄灯"
        return "红灯"

    @staticmethod
    def _promotion_status(promotion_rate: float) -> str:
        return "绿灯" if promotion_rate > 0.25 else "黄灯"

    @staticmethod
    def _weekday_label(trade_date: str) -> str:
        weekday_map = {
            0: "星期一",
            1: "星期二",
            2: "星期三",
            3: "星期四",
            4: "星期五",
            5: "星期六",
            6: "星期日",
        }
        return weekday_map[datetime.strptime(trade_date, "%Y-%m-%d").weekday()]
