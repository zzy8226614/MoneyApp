package com.moneyapp.screener.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.moneyapp.screener.model.MarketSignalResponse
import com.moneyapp.screener.model.ScreenDestination
import com.moneyapp.screener.model.ScreeningResponse
import com.moneyapp.screener.repository.ScreeningRepository
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class UiState(
    val baseUrl: String = "http://183.62.173.178:8000/",
    val tradeDate: String = defaultTradeDate(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val currentScreen: ScreenDestination = ScreenDestination.HOME,
    val marketSignalResponse: MarketSignalResponse? = null,
    val firstBoardResponse: ScreeningResponse? = null,
    val weakToStrongResponse: ScreeningResponse? = null,
    val top5Response: ScreeningResponse? = null,
    val boardTop10LimitUpResponse: ScreeningResponse? = null,
)

private fun defaultTradeDate(): String =
    SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

class ScreeningViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = ScreeningRepository.create(application)
    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun updateBaseUrl(value: String) {
        _uiState.update { it.copy(baseUrl = value) }
    }

    fun updateTradeDate(value: String) {
        _uiState.update { it.copy(tradeDate = value) }
    }

    fun backToHome() {
        _uiState.update { it.copy(currentScreen = ScreenDestination.HOME, errorMessage = null) }
    }

    fun loadFirstBoard() {
        load(
            destination = ScreenDestination.FIRST_BOARD,
            block = { state ->
                repository.loadFirstBoard(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = false,
                )
            },
            onSuccess = { state, response -> state.copy(firstBoardResponse = response) },
        )
    }

    fun refreshFirstBoard() {
        load(
            destination = ScreenDestination.FIRST_BOARD,
            block = { state ->
                repository.loadFirstBoard(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = true,
                )
            },
            onSuccess = { state, response -> state.copy(firstBoardResponse = response) },
        )
    }

    fun loadMarketSignal() {
        loadMarketSignalInternal(forceRefresh = false)
    }

    fun refreshMarketSignal() {
        loadMarketSignalInternal(forceRefresh = true)
    }

    fun loadWeakToStrong() {
        load(
            destination = ScreenDestination.WEAK_TO_STRONG,
            block = { state ->
                repository.loadWeakToStrong(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = false,
                )
            },
            onSuccess = { state, response -> state.copy(weakToStrongResponse = response) },
        )
    }

    fun refreshWeakToStrong() {
        load(
            destination = ScreenDestination.WEAK_TO_STRONG,
            block = { state ->
                repository.loadWeakToStrong(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = true,
                )
            },
            onSuccess = { state, response -> state.copy(weakToStrongResponse = response) },
        )
    }

    fun loadTop5() {
        load(
            destination = ScreenDestination.TOP5,
            block = { state ->
                repository.loadTop5(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = false,
                )
            },
            onSuccess = { state, response -> state.copy(top5Response = response) },
        )
    }

    fun refreshTop5() {
        load(
            destination = ScreenDestination.TOP5,
            block = { state ->
                repository.loadTop5(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = true,
                )
            },
            onSuccess = { state, response -> state.copy(top5Response = response) },
        )
    }

    fun loadBoardTop10LimitUp() {
        load(
            destination = ScreenDestination.BOARD_TOP10_LIMIT_UP,
            block = { state ->
                repository.loadBoardTop10LimitUp(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = false,
                )
            },
            onSuccess = { state, response -> state.copy(boardTop10LimitUpResponse = response) },
        )
    }

    fun refreshBoardTop10LimitUp() {
        load(
            destination = ScreenDestination.BOARD_TOP10_LIMIT_UP,
            block = { state ->
                repository.loadBoardTop10LimitUp(
                    baseUrl = state.baseUrl.trim(),
                    tradeDate = state.tradeDate.trim(),
                    forceRefresh = true,
                )
            },
            onSuccess = { state, response -> state.copy(boardTop10LimitUpResponse = response) },
        )
    }

    private fun loadMarketSignalInternal(forceRefresh: Boolean) {
        viewModelScope.launch {
            val current = _uiState.value
            _uiState.update {
                it.copy(
                    currentScreen = ScreenDestination.MARKET_SIGNAL,
                    isLoading = true,
                    errorMessage = null,
                )
            }
            runCatching {
                repository.loadMarketSignal(
                    baseUrl = current.baseUrl.trim(),
                    tradeDate = current.tradeDate.trim(),
                    forceRefresh = forceRefresh,
                )
            }.onSuccess { result ->
                    _uiState.update {
                        it.copy(
                            marketSignalResponse = result.response.withCacheNote(result.fromCache),
                            isLoading = false,
                            errorMessage = result.response.error,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = error.message ?: "请求失败，请检查后端服务地址。",
                        )
                    }
                }
        }
    }

    private fun load(
        destination: ScreenDestination,
        block: suspend (UiState) -> ScreeningRepository.LoadResult<ScreeningResponse>,
        onSuccess: (UiState, ScreeningResponse) -> UiState,
    ) {
        viewModelScope.launch {
            val current = _uiState.value
            _uiState.update {
                it.copy(
                    currentScreen = destination,
                    isLoading = true,
                    errorMessage = null,
                )
            }
            runCatching { block(current) }
                .onSuccess { result ->
                    _uiState.update {
                        onSuccess(it, result.response.withCacheNote(result.fromCache)).copy(
                            isLoading = false,
                            errorMessage = result.response.error,
                        )
                    }
                }
                .onFailure { error ->
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            errorMessage = error.message ?: "请求失败，请检查后端服务地址。",
                        )
                    }
                }
        }
    }
}

private fun MarketSignalResponse.withCacheNote(fromCache: Boolean): MarketSignalResponse {
    if (!fromCache) return this
    val cacheNote = "显示缓存数据（2小时内）。"
    return copy(notes = listOf(cacheNote) + notes.filterNot { it == cacheNote })
}

private fun ScreeningResponse.withCacheNote(fromCache: Boolean): ScreeningResponse {
    if (!fromCache) return this
    val cacheNote = "显示缓存数据（2小时内）。"
    return copy(
        marketSummary = marketSummary.copy(
            notes = listOf(cacheNote) + marketSummary.notes.filterNot { it == cacheNote },
        ),
    )
}
