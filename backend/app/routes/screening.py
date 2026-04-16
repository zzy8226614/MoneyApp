from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.schemas import MarketSignalResponse, ScreeningRequest, ScreeningResponse
from ..services.screener_service import ScreenerService

router = APIRouter(prefix="/screen", tags=["screening"])
service = ScreenerService()


@router.post("/first-board", response_model=ScreeningResponse)
def screen_first_board(request: ScreeningRequest) -> ScreeningResponse:
    try:
        return service.screen_first_board(
            trade_date=request.trade_date,
            use_demo_on_failure=request.use_demo_on_failure,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/weak-to-strong", response_model=ScreeningResponse)
def screen_weak_to_strong(request: ScreeningRequest) -> ScreeningResponse:
    try:
        return service.screen_weak_to_strong(
            trade_date=request.trade_date,
            use_demo_on_failure=request.use_demo_on_failure,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/top5", response_model=ScreeningResponse)
def screen_top5(request: ScreeningRequest) -> ScreeningResponse:
    try:
        return service.screen_top5(
            trade_date=request.trade_date,
            use_demo_on_failure=request.use_demo_on_failure,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/market-signal", response_model=MarketSignalResponse)
def market_signal(request: ScreeningRequest) -> MarketSignalResponse:
    try:
        return service.build_market_signal(
            trade_date=request.trade_date,
            use_demo_on_failure=request.use_demo_on_failure,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
