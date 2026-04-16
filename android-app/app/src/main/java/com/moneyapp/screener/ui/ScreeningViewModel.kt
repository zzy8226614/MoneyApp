package com.moneyapp.screener.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.moneyapp.screener.model.ScreenDestination
import com.moneyapp.screener.model.ScreeningResponse
import com.moneyapp.screener.repository.ScreeningRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class UiState(
    val baseUrl: String = "http://10.0.2.2:8000/",
    val tradeDate: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val currentScreen: ScreenDestination = ScreenDestination.HOME,
    val firstBoardResponse: ScreeningResponse? = null,
    val weakToStrongResponse: ScreeningResponse? = null,
    val top5Response: ScreeningResponse? = null,
)

class ScreeningViewModel(
    private val repository: ScreeningRepository = ScreeningRepository(),
) : ViewModel() {
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
                repository.loadFirstBoard(state.baseUrl.trim(), state.tradeDate.trim())
            },
            onSuccess = { state, response -> state.copy(firstBoardResponse = response) },
        )
    }

    fun loadWeakToStrong() {
        load(
            destination = ScreenDestination.WEAK_TO_STRONG,
            block = { state ->
                repository.loadWeakToStrong(state.baseUrl.trim(), state.tradeDate.trim())
            },
            onSuccess = { state, response -> state.copy(weakToStrongResponse = response) },
        )
    }

    fun loadTop5() {
        load(
            destination = ScreenDestination.TOP5,
            block = { state ->
                repository.loadTop5(state.baseUrl.trim(), state.tradeDate.trim())
            },
            onSuccess = { state, response -> state.copy(top5Response = response) },
        )
    }

    private fun load(
        destination: ScreenDestination,
        block: suspend (UiState) -> ScreeningResponse,
        onSuccess: (UiState, ScreeningResponse) -> UiState,
    ) {
        viewModelScope.launch {
            val current = _uiState.value
            _uiState.update {
                it.copy(
                    isLoading = true,
                    errorMessage = null,
                )
            }
            runCatching { block(current) }
                .onSuccess { response ->
                    _uiState.update {
                        onSuccess(it, response).copy(
                            currentScreen = destination,
                            isLoading = false,
                            errorMessage = response.error,
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
