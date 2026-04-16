# MoneyAPP Screener

`MoneyAPP` 现在包含两个可协作的子系统：

1. `backend/`：基于 `FastAPI + Akshare` 的选股后端。
2. `android-app/`：基于 `Kotlin + Jetpack Compose` 的 Android APK 前端。

## 已实现功能

### 1. 一进二选股

- 按按钮触发后调用后端 `POST /screen/first-board`
- 执行路径：
  - 通过 `Akshare` 获取当日涨停池、历史日线与板块数据
  - 按一进二硬性条件过滤
  - 按评分机制排序
  - 返回并展示以下字段：
    - `股票名称`
    - `流通市值`
    - `换手率`
    - `封单时间`
    - `收盘封单数`
    - `涨停驱动`
    - `所属板块`
    - `板块涨停数`
    - `总分`

### 2. 弱转强选股

- 按按钮触发后调用后端 `POST /screen/weak-to-strong`
- 筛选 `>=2板 且 <5板` 的弱转强候选
- 返回与一进二一致风格的展示字段

### 3. Top5 推荐

- 按按钮触发后调用后端 `POST /screen/top5`
- 从一进二和弱转强候选中合并计算
- 按 `板块强弱 + 个股评分 + 连板位置 + 换手质量` 输出 Top5

## 当前实现说明

- 后端优先尝试实时调用 `Akshare`
- 若本地网络或上游接口异常，则会优先使用本地缓存
- 若缓存也不存在，则会回退到内置 demo 数据，保证 APK 可以完整走通交互链路

这意味着：

- 在网络通畅时，你看到的是实时筛选结果
- 在网络不通或 `Akshare` 波动时，你仍然能看到完整软件效果，不会出现空白页或闪退

## 后端运行

### 方式 1：直接运行

```powershell
& "d:\New_Project\AI_Project\MoneyAPP\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 方式 2：使用脚本

```powershell
.\backend\run_server.ps1
```

启动后可访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## 后端测试

```powershell
& "d:\New_Project\AI_Project\MoneyAPP\.venv\Scripts\python.exe" -m pytest backend\tests
```

## Android APK 运行

当前仓库已经提供可直接构建并安装到 Android 手机的工程目录：`android-app/`

### 导入方式

1. 打开 Android Studio
2. 选择 `Open`
3. 打开 `d:\New_Project\AI_Project\MoneyAPP\android-app`
4. 等待 Gradle 同步完成

### APK 页面结构

- 首页：
  - `一进二选股`
  - `弱转强选股`
  - `Top5 推荐`
- 结果页：
  - 支持返回
  - 支持刷新
  - 支持错误提示
  - 支持空状态展示

### 后端地址说明

首页支持填写后端地址：

- Android 模拟器默认填写：`http://10.0.2.2:8000/`
- 真机调试时，请改成你电脑在局域网中的 IP，例如：`http://192.168.1.10:8000/`

### 已产出 APK

- 调试包：`android-app/app/build/outputs/apk/debug/app-debug.apk`
- 可安装发布包：`android-app/app/build/outputs/apk/release/app-release.apk`

`app-release.apk` 当前使用本机 `debug.keystore` 进行签名，适合侧载安装到 Android 手机进行功能验证；如需正式对外分发或上架，再替换为专用发布签名。

### 手机安装步骤

1. 将 `app-release.apk` 发送到 Android 手机。
2. 在手机上允许“安装未知应用”。
3. 点击 `app-release.apk` 完成安装。
4. 启动你电脑上的后端服务，并确保手机与电脑处于同一局域网。
5. 打开 APP，在首页将后端地址改成电脑局域网 IP，例如 `http://192.168.1.10:8000/`。
6. 点击 `一进二选股`、`弱转强选股`、`Top5 推荐` 验证三条链路。

### 交易日说明

- 可留空，默认使用今天
- 也可手动输入：
  - `YYYY-MM-DD`
  - `YYYYMMDD`

## 已验证内容

- `FastAPI` 服务可正常启动
- `/health` 可正常返回
- `/screen/first-board`、`/screen/weak-to-strong`、`/screen/top5` 路由已实现
- `pytest` 最小接口测试已通过
- `assembleDebug` 已成功，已生成 `app-debug.apk`
- `assembleRelease` 将生成已签名 `app-release.apk`，可用于 Android 真机安装

## 当前限制

- 当前 `Akshare` 在本机上存在偶发断连，因此后端实现里加入了缓存与 demo 降级
- 若手机未连接到电脑后端所在局域网，或首页后端地址未改成电脑 IP，请求会失败
- 当前发布包签名为调试签名，适合测试安装，不适合作为正式商用发布签名
