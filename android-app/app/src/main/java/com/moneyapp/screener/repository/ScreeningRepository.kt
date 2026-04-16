package com.moneyapp.screener.repository

import com.moneyapp.screener.model.ScreeningRequest
import com.moneyapp.screener.model.ScreeningResponse
import com.moneyapp.screener.network.ScreeningApi

class ScreeningRepository {
    suspend fun loadFirstBoard(baseUrl: String, tradeDate: String): ScreeningResponse {
        return api(baseUrl).screenFirstBoard(ScreeningRequest(tradeDate = tradeDate.ifBlank { null }))
    }

    suspend fun loadWeakToStrong(baseUrl: String, tradeDate: String): ScreeningResponse {
        return api(baseUrl).screenWeakToStrong(ScreeningRequest(tradeDate = tradeDate.ifBlank { null }))
    }

    suspend fun loadTop5(baseUrl: String, tradeDate: String): ScreeningResponse {
        return api(baseUrl).screenTop5(ScreeningRequest(tradeDate = tradeDate.ifBlank { null }))
    }

    private fun api(baseUrl: String): ScreeningApi = ScreeningApi.create(baseUrl)
}
