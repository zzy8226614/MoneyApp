from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.sample_data import build_demo_first_board, build_demo_weak_to_strong
from ..models.schemas import MarketSummary, ScreeningItem, ScreeningResponse
from .akshare_service import AkshareDataService, MarketDataset


@dataclass
class CandidateContext:
    board_counts: dict[str, int]
    board_strength: dict[str, float]
    board_drivers: dict[str, str]


@dataclass
class ScreeningBuildResult:
    items: list[ScreeningItem]
    notes: list[str]


class ScreenerService:
    def __init__(self, data_service: AkshareDataService | None = None) -> None:
        self.data_service = data_service or AkshareDataService()

    def screen_first_board(self, trade_date: str | None, use_demo_on_failure: bool) -> ScreeningResponse:
        try:
            dataset = self.data_service.get_market_dataset(trade_date)
            first_board_result = self._build_first_board_items(dataset)
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

    def screen_weak_to_strong(self, trade_date: str | None, use_demo_on_failure: bool) -> ScreeningResponse:
        try:
            dataset = self.data_service.get_market_dataset(trade_date)
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
                items=sorted(items, key=lambda item: item.totalScore, reverse=True),
                error=None,
            )
        except Exception as exc:
            if use_demo_on_failure:
                return build_demo_weak_to_strong(self._normalize_date(trade_date))
            raise RuntimeError(f"Failed to screen weak-to-strong pool: {exc}") from exc

    def screen_top5(self, trade_date: str | None, use_demo_on_failure: bool) -> ScreeningResponse:
        try:
            dataset = self.data_service.get_market_dataset(trade_date)
            first_board_result = self._build_first_board_items(dataset)
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
                    items=sorted(weak_to_strong_items, key=lambda item: item.totalScore, reverse=True),
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

    def _build_first_board_items(self, dataset: MarketDataset) -> ScreeningBuildResult:
        if dataset.limit_up_pool.empty:
            return ScreeningBuildResult(items=[], notes=[])
        context = self._build_candidate_context(dataset)
        frame = dataset.limit_up_pool.copy()
        if "连板数" not in frame.columns:
            return ScreeningBuildResult(items=[], notes=[])
        frame = frame[frame["连板数"].fillna(0).astype(int) == 1]
        items: list[ScreeningItem] = []
        history_filter_skipped_count = 0
        for _, row in frame.iterrows():
            item, history_filter_skipped = self._screen_first_board_row(row, dataset.trade_date, context)
            if item is not None:
                items.append(item)
            if history_filter_skipped:
                history_filter_skipped_count += 1
        notes: list[str] = []
        if history_filter_skipped_count > 0:
            notes.append(
                f"Historical daily data was unavailable for {history_filter_skipped_count} candidates; "
                "the 250-day trend filter was skipped for those stocks."
            )
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
        try:
            history = self.data_service.get_stock_history(symbol=symbol, trade_date=trade_date)
            if not self._passes_history_filters(history):
                return None, False
        except Exception:
            history_filter_skipped = True

        turnover = self._to_float(row.get("换手率"))
        seal_amount_yi = self._to_yi(row.get("封板资金"))
        board_name = self._board_name(row)
        board_count = context.board_counts.get(board_name, 0)
        seal_time = self._format_time(row.get("首次封板时间"))
        limit_up_driver = self._limit_up_driver(row, context)

        score = 0.0
        score += self._score_first_limit_time(seal_time)
        score += self._score_turnover(turnover)
        score += self._score_seal_amount(seal_amount_yi)
        score += self._score_board_synergy(board_count)

        if score < 21:
            return None, history_filter_skipped

        reason = f"首板评分 {round(score, 1)} 分，驱动 {limit_up_driver}，{board_name} 板块涨停 {board_count} 家。"
        if history_filter_skipped:
            reason += " 历史日线不可用，已跳过250日趋势过滤。"

        return (
            ScreeningItem(
                stockName=name,
                symbol=symbol,
                floatMarketCap=f"{float_market_cap_yi:.2f}亿",
                turnoverRate=f"{turnover:.2f}%",
                sealTime=seal_time,
                sealAmountOrLots=f"{seal_amount_yi:.2f}亿封单资金",
                limitUpDriver=limit_up_driver,
                boardName=board_name,
                boardLimitUpCount=board_count,
                totalScore=round(score, 2),
                strategyTag="first_board_to_second",
                recommendReason=reason,
            ),
            history_filter_skipped,
        )

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
        if board_count < 2:
            return None
        float_market_cap_yi = self._to_yi(row.get("流通市值"))
        if float_market_cap_yi < 20 or float_market_cap_yi > 200:
            return None
        turnover = self._to_float(row.get("换手率"))
        if turnover < 5 or turnover > 15:
            return None
        first_time = self._format_time(row.get("首次封板时间"))
        last_time = self._format_time(row.get("最后封板时间"))
        board_break_count = int(self._to_float(row.get("炸板次数")))
        board_count_value = int(self._to_float(row.get("连板数")))
        is_weak_pattern = board_break_count >= 1 or self._is_late_board(last_time) or self._is_late_board(first_time)
        if not is_weak_pattern:
            return None
        seal_amount_yi = self._to_yi(row.get("封板资金"))
        board_strength = context.board_strength.get(board_name, 0.0)
        limit_up_driver = self._limit_up_driver(row, context)
        score = 0.0
        score += 8.0 if board_break_count >= 1 else 4.0
        score += 7.0 if board_count >= 5 else 5.0 if board_count >= 3 else 2.0
        score += 6.0 if 5 <= turnover <= 12 else 4.0
        score += 5.0 if self._is_late_board(last_time) else 2.0
        score += 3.0 if board_strength > 0 else 1.0

        return ScreeningItem(
            stockName=name,
            symbol=symbol,
            floatMarketCap=f"{float_market_cap_yi:.2f}亿",
            turnoverRate=f"{turnover:.2f}%",
            sealTime=last_time,
            sealAmountOrLots=f"{seal_amount_yi:.2f}亿封单资金",
            limitUpDriver=limit_up_driver,
            boardName=board_name,
            boardLimitUpCount=board_count,
            totalScore=round(score + board_count_value, 2),
            strategyTag="weak_to_strong_2nd",
            recommendReason=f"{board_count_value} 板弱转强候选，驱动 {limit_up_driver}，板块强度 {board_strength:.2f}，炸板次数 {board_break_count}。",
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
        if history.empty or "收盘" not in history.columns:
            return False
        closes = pd.to_numeric(history["收盘"], errors="coerce").dropna()
        if len(closes) < 250:
            return False
        ma250 = closes.tail(250).mean()
        current_close = closes.iloc[-1]
        if current_close <= ma250:
            return False
        pct_change = pd.to_numeric(history.get("涨跌幅"), errors="coerce").fillna(0)
        return bool((pct_change.tail(60) >= 9.5).any())

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
            return pd.Timestamp.now().strftime("%Y-%m-%d")
        if "-" in trade_date:
            return trade_date
        return f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

    @staticmethod
    def _with_recommendation_score(item: ScreeningItem) -> ScreeningItem:
        board_bonus = min(item.boardLimitUpCount * 0.8, 6.0)
        strategy_bonus = 1.5 if item.strategyTag == "first_board_to_second" else 2.5
        score = round(item.totalScore + board_bonus + strategy_bonus, 2)
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
