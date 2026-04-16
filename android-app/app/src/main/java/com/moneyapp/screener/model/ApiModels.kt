package com.moneyapp.screener.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ScreeningRequest(
    @SerialName("trade_date") val tradeDate: String? = null,
    @SerialName("use_demo_on_failure") val useDemoOnFailure: Boolean = true,
)

@Serializable
data class MarketSummary(
    val tradeDate: String,
    val limitUpCount: Int,
    val firstBoardCount: Int,
    val weakToStrongCount: Int,
    val source: String,
    val notes: List<String> = emptyList(),
)

@Serializable
data class ScreeningItem(
    val stockName: String,
    val symbol: String,
    val floatMarketCap: String,
    val turnoverRate: String,
    val sealTime: String,
    val sealAmountOrLots: String,
    val limitUpDriver: String,
    val boardName: String,
    val boardLimitUpCount: Int,
    val totalScore: Double,
    val strategyTag: String,
    val recommendReason: String,
)

@Serializable
data class ScreeningResponse(
    @SerialName("trade_date") val tradeDate: String,
    @SerialName("market_summary") val marketSummary: MarketSummary,
    val items: List<ScreeningItem> = emptyList(),
    val error: String? = null,
)

enum class ScreenDestination {
    HOME,
    FIRST_BOARD,
    WEAK_TO_STRONG,
    TOP5,
}
