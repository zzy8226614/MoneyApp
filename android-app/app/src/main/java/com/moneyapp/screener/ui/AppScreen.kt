package com.moneyapp.screener.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.moneyapp.screener.model.ScreenDestination
import com.moneyapp.screener.model.ScreeningItem
import com.moneyapp.screener.model.ScreeningResponse

@Composable
fun MoneyAppRoot(viewModel: ScreeningViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsState()

    when (state.currentScreen) {
        ScreenDestination.HOME -> HomePage(
            state = state,
            onBaseUrlChanged = viewModel::updateBaseUrl,
            onTradeDateChanged = viewModel::updateTradeDate,
            onFirstBoardClick = viewModel::loadFirstBoard,
            onWeakToStrongClick = viewModel::loadWeakToStrong,
            onTop5Click = viewModel::loadTop5,
        )

        ScreenDestination.FIRST_BOARD -> ResultPage(
            title = "一进二结果",
            response = state.firstBoardResponse,
            isLoading = state.isLoading,
            errorMessage = state.errorMessage,
            onBack = viewModel::backToHome,
            onRefresh = viewModel::loadFirstBoard,
        )

        ScreenDestination.WEAK_TO_STRONG -> ResultPage(
            title = "弱转强结果",
            response = state.weakToStrongResponse,
            isLoading = state.isLoading,
            errorMessage = state.errorMessage,
            onBack = viewModel::backToHome,
            onRefresh = viewModel::loadWeakToStrong,
        )

        ScreenDestination.TOP5 -> ResultPage(
            title = "Top5 推荐",
            response = state.top5Response,
            isLoading = state.isLoading,
            errorMessage = state.errorMessage,
            onBack = viewModel::backToHome,
            onRefresh = viewModel::loadTop5,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomePage(
    state: UiState,
    onBaseUrlChanged: (String) -> Unit,
    onTradeDateChanged: (String) -> Unit,
    onFirstBoardClick: () -> Unit,
    onWeakToStrongClick: () -> Unit,
    onTop5Click: () -> Unit,
) {
    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(title = { Text("MoneyAPP 选股器") })
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "收盘后选股版",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            OutlinedTextField(
                value = state.baseUrl,
                onValueChange = onBaseUrlChanged,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("后端地址") },
                supportingText = { Text("模拟器默认用 http://10.0.2.2:8000/，真机请改成电脑局域网 IP。") },
                singleLine = true,
            )
            OutlinedTextField(
                value = state.tradeDate,
                onValueChange = onTradeDateChanged,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("交易日（可选）") },
                supportingText = { Text("支持 YYYY-MM-DD 或 YYYYMMDD，为空则默认今天。") },
                singleLine = true,
            )
            Button(
                onClick = onFirstBoardClick,
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isLoading,
            ) {
                Text("一进二选股")
            }
            Button(
                onClick = onWeakToStrongClick,
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isLoading,
            ) {
                Text("弱转强选股")
            }
            Button(
                onClick = onTop5Click,
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isLoading,
            ) {
                Text("Top5 推荐")
            }

            if (state.isLoading) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                ) {
                    CircularProgressIndicator()
                }
            }

            state.errorMessage?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ResultPage(
    title: String,
    response: ScreeningResponse?,
    isLoading: Boolean,
    errorMessage: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    TextButton(onClick = onBack) { Text("返回") }
                },
                actions = {
                    TextButton(onClick = onRefresh, enabled = !isLoading) { Text("刷新") }
                },
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                isLoading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }

                errorMessage != null -> {
                    Text(
                        text = errorMessage,
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(24.dp),
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                response == null -> {
                    Text(
                        text = "暂无结果",
                        modifier = Modifier.align(Alignment.Center),
                    )
                }

                response.items.isEmpty() -> {
                    EmptyState(response = response)
                }

                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        contentPadding = PaddingValues(16.dp),
                    ) {
                        item {
                            MarketSummaryCard(response = response)
                        }
                        items(response.items) { item ->
                            ScreeningItemCard(item = item)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(response: ScreeningResponse) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("当日无符合条件标的")
        Text(
            text = "交易日：${response.tradeDate}",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MarketSummaryCard(response: ScreeningResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = "交易日：${response.marketSummary.tradeDate}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text("涨停总数：${response.marketSummary.limitUpCount}")
            Text("一进二候选：${response.marketSummary.firstBoardCount}")
            Text("弱转强候选：${response.marketSummary.weakToStrongCount}")
            Text("数据来源：${response.marketSummary.source}")
            if (response.marketSummary.notes.isNotEmpty()) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    response.marketSummary.notes.forEach { note ->
                        AssistChip(
                            onClick = {},
                            label = { Text(note) },
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ScreeningItemCard(item: ScreeningItem) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "${item.stockName} (${item.symbol})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                InfoChip("流通市值", item.floatMarketCap)
                InfoChip("换手率", item.turnoverRate)
                InfoChip("封单时间", item.sealTime)
                InfoChip("收盘封单数", item.sealAmountOrLots)
                InfoChip("涨停驱动", item.limitUpDriver)
                InfoChip("所属板块", item.boardName)
                InfoChip("板块涨停数", item.boardLimitUpCount.toString())
                InfoChip("总分", item.totalScore.toString())
            }
            Text(
                text = item.recommendReason,
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = {}) {
                Text(if (item.strategyTag == "first_board_to_second") "策略：一进二" else "策略：弱转强")
            }
        }
    }
}

@Composable
private fun InfoChip(label: String, value: String) {
    Card {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}
