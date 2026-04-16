from __future__ import annotations

from ..models.schemas import MarketSummary, ScreeningItem, ScreeningResponse


def build_demo_first_board(trade_date: str) -> ScreeningResponse:
    return ScreeningResponse(
        trade_date=trade_date,
        market_summary=MarketSummary(
            tradeDate=trade_date,
            limitUpCount=46,
            firstBoardCount=3,
            weakToStrongCount=0,
            source="demo",
            notes=["Akshare unavailable, using bundled demo data."],
        ),
        items=[
            ScreeningItem(
                stockName="华芯科技",
                symbol="002111",
                floatMarketCap="86.40亿",
                turnoverRate="11.23%",
                sealTime="09:47:12",
                sealAmountOrLots="1.26亿封单资金",
                limitUpDriver="半导体国产替代",
                boardName="半导体",
                boardLimitUpCount=4,
                totalScore=25.0,
                strategyTag="first_board_to_second",
                recommendReason="封板时间早、换手适中、板块联动强。",
            ),
            ScreeningItem(
                stockName="云启通信",
                symbol="002567",
                floatMarketCap="54.18亿",
                turnoverRate="8.45%",
                sealTime="10:02:31",
                sealAmountOrLots="0.93亿封单资金",
                limitUpDriver="算力网络扩容",
                boardName="通信设备",
                boardLimitUpCount=3,
                totalScore=23.0,
                strategyTag="first_board_to_second",
                recommendReason="首板质量合格，板块热度靠前。",
            ),
            ScreeningItem(
                stockName="智造机器人",
                symbol="001298",
                floatMarketCap="42.90亿",
                turnoverRate="13.08%",
                sealTime="09:58:05",
                sealAmountOrLots="0.88亿封单资金",
                limitUpDriver="工业机器人",
                boardName="自动化设备",
                boardLimitUpCount=2,
                totalScore=22.0,
                strategyTag="first_board_to_second",
                recommendReason="换手区间优秀，题材具备扩散性。",
            ),
        ],
    )


def build_demo_weak_to_strong(trade_date: str) -> ScreeningResponse:
    return ScreeningResponse(
        trade_date=trade_date,
        market_summary=MarketSummary(
            tradeDate=trade_date,
            limitUpCount=46,
            firstBoardCount=0,
            weakToStrongCount=3,
            source="demo",
            notes=["Akshare unavailable, using bundled demo data."],
        ),
        items=[
            ScreeningItem(
                stockName="东数互联",
                symbol="603199",
                floatMarketCap="73.55亿",
                turnoverRate="10.15%",
                sealTime="14:36:50",
                sealAmountOrLots="1.11亿封单资金",
                limitUpDriver="算力服务器",
                boardName="算力",
                boardLimitUpCount=5,
                totalScore=27.0,
                strategyTag="weak_to_strong_2nd",
                recommendReason="2板弱转强，尾盘回封且板块强度最高。",
            ),
            ScreeningItem(
                stockName="新能储控",
                symbol="002845",
                floatMarketCap="61.32亿",
                turnoverRate="9.83%",
                sealTime="14:42:13",
                sealAmountOrLots="0.79亿封单资金",
                limitUpDriver="储能逆变器",
                boardName="储能",
                boardLimitUpCount=4,
                totalScore=24.5,
                strategyTag="weak_to_strong_2nd",
                recommendReason="3板内弱转强，换手健康，板块承接稳定。",
            ),
            ScreeningItem(
                stockName="天工智驾",
                symbol="600388",
                floatMarketCap="98.05亿",
                turnoverRate="12.01%",
                sealTime="14:51:22",
                sealAmountOrLots="0.68亿封单资金",
                limitUpDriver="智能驾驶",
                boardName="智能驾驶",
                boardLimitUpCount=3,
                totalScore=22.5,
                strategyTag="weak_to_strong_2nd",
                recommendReason="烂板回封转强，但板块强度略弱于前两名。",
            ),
        ],
    )
