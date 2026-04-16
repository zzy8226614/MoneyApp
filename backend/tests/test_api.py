from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.akshare_service import MarketDataset
from backend.app.services.screener_service import ScreenerService

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_first_board_demo_response() -> None:
    response = client.post("/screen/first-board", json={"use_demo_on_failure": True})
    body = response.json()
    assert response.status_code == 200
    assert "trade_date" in body
    assert "market_summary" in body
    assert "items" in body


def test_weak_to_strong_demo_response() -> None:
    response = client.post("/screen/weak-to-strong", json={"use_demo_on_failure": True})
    body = response.json()
    assert response.status_code == 200
    assert isinstance(body["items"], list)


def test_top5_demo_response() -> None:
    response = client.post("/screen/top5", json={"use_demo_on_failure": True})
    body = response.json()
    assert response.status_code == 200
    assert len(body["items"]) <= 5


class EmptyDataService:
    def get_market_dataset(self, trade_date: str | None = None) -> MarketDataset:
        return MarketDataset(
            trade_date="2026-04-15",
            source="empty",
            limit_up_pool=pd.DataFrame(),
            previous_limit_up_pool=pd.DataFrame(),
            board_snapshot=pd.DataFrame(),
        )


def test_empty_dataset_uses_demo_when_enabled() -> None:
    service = ScreenerService(data_service=EmptyDataService())
    response = service.screen_first_board("20260415", use_demo_on_failure=True)
    assert response.market_summary.source == "demo"
    assert len(response.items) > 0


class HistoryUnavailableDataService:
    def get_market_dataset(self, trade_date: str | None = None) -> MarketDataset:
        limit_up_pool = pd.DataFrame(
            [
                {
                    "名称": "实时首板A",
                    "代码": "002111",
                    "连板数": 1,
                    "流通市值": 86.4,
                    "换手率": 11.23,
                    "封板资金": 1.26,
                    "所属行业": "半导体",
                    "首次封板时间": "094712",
                    "涨停原因类别": "半导体国产替代",
                }
            ]
        )
        return MarketDataset(
            trade_date="2026-04-15",
            source="live",
            limit_up_pool=limit_up_pool,
            previous_limit_up_pool=pd.DataFrame(),
            board_snapshot=pd.DataFrame(),
        )

    def get_stock_history(self, symbol: str, trade_date: str | None = None) -> pd.DataFrame:
        raise ConnectionError("historical data unavailable")


def test_first_board_skips_history_filter_when_history_unavailable() -> None:
    service = ScreenerService(data_service=HistoryUnavailableDataService())
    response = service.screen_first_board("20260415", use_demo_on_failure=True)
    assert response.market_summary.source == "live"
    assert len(response.items) == 1
    assert any("250-day trend filter was skipped" in note for note in response.market_summary.notes)
    assert "历史日线不可用" in response.items[0].recommendReason
