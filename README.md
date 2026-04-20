# MoneyAPP Screener

`MoneyAPP` 现在包含两个可协作的子系统：

1. `backend/`：基于 `FastAPI + Akshare` 的选股后端。
2. `android-app/`：基于 `Kotlin + Jetpack Compose` 的 Android APK 前端。

当前仓库还新增了双端演进的基础骨架：

3. `windows-mfc/`：Windows 10 原生宿主骨架。
4. `web/desktop-shell/`：供 WebView2 承载的桌面前端壳层。
5. `docs/`：接口契约、版本治理、兼容性与回归清单。

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
  - `所属板块`
  - `板块排名`
  - `总分`
  - `封单时间`
  - `封单手数`
  - `开板次数`
  - `换手率`
  - `板块涨停数`

### 2. 弱转强选股

- 按按钮触发后调用后端 `POST /screen/weak-to-strong`
- 筛选 `>=2板 且 <5板` 的弱转强候选
- 排除创业板 `300`、科创板、北交所与 `ST`
- 返回更精简的展示字段：
  - `股票名称`
  - `流通市值`
  - `所属板块`
  - `板块排名`
  - `是否涨停`
  - `开板次数`
  - `换手率`
  - `板块涨停数`

### 3. Top5 推荐

- 按按钮触发后调用后端 `POST /screen/top5`
- 从一进二和弱转强候选中合并计算
- 按 `板块强弱 + 个股评分 + 连板位置 + 换手质量` 输出 Top5

### 4. 情绪信号

- 按按钮触发后调用后端 `POST /screen/market-signal`
- 展示：
  - `当前日期`
  - `大盘表现`
  - `成交额`
  - `情绪判定`
  - `仓位建议`
  - 指标表：`涨停家数 / 最高连板 / 连板晋级率 / 跌停潮`
- “是否达标”统一只显示：`红灯 / 黄灯 / 绿灯`

## 当前实现说明

- 后端优先尝试实时调用 `Akshare`
- 若本地网络或上游接口异常，则会优先使用本地缓存
- 若缓存也不存在，则会回退到内置 demo 数据，保证 APK 可以完整走通交互链路
- `api/v1` 路由新增服务端响应缓存（按交易日缓存 market-signal / first-board / weak-to-strong / top5）
- 同一交易日非强刷请求可直接命中服务端缓存，进入“极速模式”（毫秒到秒级返回）
- `force_refresh=true` 时会绕过服务端响应缓存，优先拉取实时数据

这意味着：

- 在网络通畅时，你看到的是实时筛选结果
- 在网络不通或 `Akshare` 波动时，你仍然能看到完整软件效果，不会出现空白页或闪退
- App 端对 `情绪信号`、`一进二选股`、`弱转强选股`、`Top5 推荐` 启用 `2` 小时成功结果缓存
- 同一按钮在 `2` 小时内再次点击会优先直接展示缓存；结果页点击 `刷新` 才会强制重新请求后端

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
- `http://127.0.0.1:8000/api/v1/health`

## API Versioning

- 旧版 Android 兼容路径继续保留：`/health`、`/screen/*`
- 新版多客户端路径：`/api/v1/health`、`/api/v1/screen/*`
- `/api/v1/*` 返回统一 envelope，便于 Windows/MFC 端做日志、诊断和错误处理

相关文档：

- `docs/api/legacy-contract.md`
- `docs/api/versioning.md`
- `docs/architecture/client-compatibility.md`
- `docs/release/version-policy.md`
- `docs/testing/android-regression-checklist.md`
- `docs/windows/desktop-shell-architecture.md`
- `docs/windows/run-host.md`

## 后端测试

```powershell
& "d:\New_Project\AI_Project\MoneyAPP\.venv\Scripts\python.exe" -m pytest backend\tests
```

## 腾讯云 CVM 部署

当前后端已经按 `Ubuntu 22.04 + 公网 IP + HTTP` 方案验证通过，可直接部署到腾讯云 CVM。

### 与旧部署文档相比的关键变更（请优先关注）

- 旧版侧重“仅 Akshare 原始调用 + 本地数据缓存”；新版额外引入了 `api/v1` 层的**服务端响应缓存**，用于多端联调提速。
- 旧版只要求服务可启动；新版建议首次部署后执行一次**接口预热**，把当日响应缓存准备好，避免首个用户请求等待较长时间。
- 旧版桌面端依赖 `http://IP:8000/desktop-shell/` 页面；新版桌面壳默认由本地 `file://` 加载，服务器侧重点改为 `api/v1` 接口可用性。
- 强制刷新（`force_refresh=true`）在新版会绕过服务端响应缓存；日常联调建议默认请求，只有需要拉最新实时数据时再点“刷新”。

### 服务器环境

- 系统：`Ubuntu 22.04`
- Python：`3.10.x`
- 运行方式：`uvicorn`
- 进程托管：`systemd`
- 当前公网访问方式：`http://公网IP:8000/`

### 安装基础依赖

在腾讯云服务器上执行：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

创建虚拟环境：

```bash
python3 -m venv ~/moneyapp-venv
source ~/moneyapp-venv/bin/activate
```

### 拉取代码并安装依赖

首次部署：

```bash
cd ~
git clone https://github.com/zzy8226614/MoneyApp.git
cd ~/MoneyApp
source ~/moneyapp-venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 临时启动后端

```bash
cd ~/MoneyApp
source ~/moneyapp-venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 健康检查

服务器本机检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/health
```

若正常，返回：

```json
{"status":"ok"}
```

浏览器公网检查：

```text
http://公网IP:8000/health
http://公网IP:8000/api/v1/health
```

### 首次部署后的接口预热（推荐）

> 目的：提前生成当日服务端响应缓存，避免首个客户端请求等待较长时间。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/screen/market-signal -H "Content-Type: application/json" -d '{"trade_date":null,"use_demo_on_failure":true,"force_refresh":false}'
curl -X POST http://127.0.0.1:8000/api/v1/screen/first-board   -H "Content-Type: application/json" -d '{"trade_date":null,"use_demo_on_failure":true,"force_refresh":false}'
curl -X POST http://127.0.0.1:8000/api/v1/screen/weak-to-strong -H "Content-Type: application/json" -d '{"trade_date":null,"use_demo_on_failure":true,"force_refresh":false}'
curl -X POST http://127.0.0.1:8000/api/v1/screen/top5          -H "Content-Type: application/json" -d '{"trade_date":null,"use_demo_on_failure":true,"force_refresh":false}'
```

### 腾讯云安全组

至少放通以下入站规则：

- `TCP 22`：SSH 登录
- `TCP 8000`：当前阶段临时对外访问 FastAPI 后端

### systemd 常驻服务

服务文件：

```ini
[Unit]
Description=MoneyAPP FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/MoneyApp
Environment="PATH=/home/ubuntu/moneyapp-venv/bin"
ExecStart=/home/ubuntu/moneyapp-venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

创建与启用：

```bash
sudo nano /etc/systemd/system/moneyapp.service
sudo systemctl daemon-reload
sudo systemctl enable moneyapp
sudo systemctl start moneyapp
```

### 日常运维命令

```bash
sudo systemctl status moneyapp
sudo systemctl restart moneyapp
sudo systemctl stop moneyapp
sudo journalctl -u moneyapp -f
```

### 更新服务器代码

后续 GitHub 有新代码时，在服务器上执行：

```bash
cd ~/MoneyApp
git pull origin main
source ~/moneyapp-venv/bin/activate
pip install -r backend/requirements.txt
sudo systemctl restart moneyapp
```

如需在服务更新后立即恢复“极速模式”，可重复执行一次上面的“接口预热”步骤。

### 生产部署建议（Nginx + HTTPS + systemd）

> 目标：避免直接暴露 `8000` 端口，统一通过 `443` 提供服务，并具备可观测、可续签、可滚动升级能力。

#### 推荐拓扑

- `uvicorn` 仅监听本机：`127.0.0.1:8000`
- `Nginx` 对外监听：`80/443`
- `Nginx` 反向代理到 `127.0.0.1:8000`
- TLS 证书：`Let's Encrypt (certbot)`

#### 1) 调整 systemd（仅本机监听）

将 `moneyapp.service` 的启动参数改为：

```ini
ExecStart=/home/ubuntu/moneyapp-venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

重载并重启：

```bash
sudo systemctl daemon-reload
sudo systemctl restart moneyapp
sudo systemctl status moneyapp
```

#### 2) 安装 Nginx 与证书工具

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

#### 3) 配置 Nginx 反向代理

创建站点配置（示例域名：`api.example.com`）：

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

启用配置并检查：

```bash
sudo nano /etc/nginx/sites-available/moneyapp
sudo ln -s /etc/nginx/sites-available/moneyapp /etc/nginx/sites-enabled/moneyapp
sudo nginx -t
sudo systemctl reload nginx
```

#### 4) 签发 HTTPS 证书

```bash
sudo certbot --nginx -d api.example.com
```

签发完成后会自动写入 `443` 配置。验证：

```bash
curl https://api.example.com/api/v1/health
```

#### 5) 安全组与防火墙建议

- 放通：`TCP 22`、`TCP 80`、`TCP 443`
- 关闭公网 `8000` 入站（仅本机回环访问）
- 若启用 `ufw`：

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
```

#### 6) 证书续签与巡检

Let's Encrypt 自动续签通常由 systemd timer 托管，建议加一次演练：

```bash
sudo certbot renew --dry-run
```

建议日常巡检：

```bash
sudo systemctl status moneyapp
sudo systemctl status nginx
sudo journalctl -u moneyapp -n 100 --no-pager
curl -sS https://api.example.com/api/v1/health
```

#### 7) 客户端地址建议

- Android / Windows 桌面端统一填：
  - `https://api.example.com/`
- 若仍使用公网 IP + HTTP（临时阶段）：
  - `http://公网IP:8000/`

### 手机 App 联调

- 首页后端地址改成：`http://公网IP:8000/`（默认值可改为你自己的服务器地址，例如 `http://183.62.173.178:8000/`）
- 先点 `情绪信号`
- 再点 `一进二选股`、`弱转强选股`、`Top5 推荐`
- 若页面显示旧结果，优先在结果页点击 `刷新`，避免命中 `2` 小时客户端缓存

## Android APK 运行

当前仓库已经提供可直接构建并安装到 Android 手机的工程目录：`android-app/`

### 导入方式

1. 打开 Android Studio
2. 选择 `Open`
3. 打开 `d:\New_Project\AI_Project\MoneyAPP\android-app`
4. 等待 Gradle 同步完成

### APK 页面结构

- 首页：
  - `情绪信号`
  - `一进二选股`
  - `弱转强选股`
  - `Top5 推荐`
- 结果页：
  - 支持返回
  - 支持刷新
  - 支持错误提示
  - 支持空状态展示
  - 结果卡片已按手机屏幕做紧凑布局优化

### 后端地址说明

首页支持填写后端地址：

- 当前默认填写：`http://183.62.173.178:8000/`
- 真机调试时，请改成你电脑在局域网中的 IP，例如：`http://192.168.1.10:8000/`

### 已产出 APK

- 调试包：`android-app/app/build/outputs/apk/debug/app-debug.apk`
- 可安装发布包：`android-app/app/build/outputs/apk/release/app-release.apk`

`app-release.apk` 当前已使用独立发布证书签名，不再复用 `Android Debug` 证书，可作为当前机器上的正式侧载安装包继续迭代。

### 手机安装步骤

1. 将 `app-release.apk` 发送到 Android 手机。
2. 在手机上允许“安装未知应用”。
3. 点击 `app-release.apk` 完成安装。
4. 启动你电脑上的后端服务，并确保手机与电脑处于同一局域网。
5. 打开 APP，在首页将后端地址改成电脑局域网 IP，例如 `http://192.168.1.10:8000/`。
6. 先点击 `情绪信号` 验证指数与成交额返回。
7. 再点击 `一进二选股`、`弱转强选股`、`Top5 推荐` 验证三条链路。
8. 若要强制获取最新数据，请在结果页点击 `刷新`。

### 交易日说明

- 默认自动填写当天日期（`yyyy-MM-dd`）
- 也可手动输入：
  - `YYYY-MM-DD`
  - `YYYYMMDD`

## 已验证内容

- `FastAPI` 服务可正常启动
- `/health` 可正常返回
- `/screen/market-signal`、`/screen/first-board`、`/screen/weak-to-strong`、`/screen/top5` 路由已实现
- `pytest` 最小接口测试已通过
- `assembleDebug` 已成功，已生成 `app-debug.apk`
- `assembleRelease` 已成功，已生成正式签名的 `app-release.apk`
- Android `compileDebugKotlin` 已通过
- `apksigner verify --print-certs` 已通过，`release` 包签名主体不再是 `Android Debug`
- 手机重新安装最新 APK 后，已验证情绪信号、一进二、弱转强、Top5 的联调链路恢复正常

## 当前限制

- 当前 `Akshare` 在本机上存在偶发断连，因此后端实现里加入了缓存与 demo 降级
- 若手机未连接到电脑后端所在局域网，或首页后端地址未改成电脑 IP，请求会失败
- `弱转强` 在某些交易日返回空结果，可能代表当日确实无符合规则标的，不一定是接口异常
- 当前发布证书已在本机生成并用于持续打包；若后续迁移电脑或长期分发，需要妥善备份 `keystore`

## Windows Desktop EXE

当前仓库已经可以生成一个可在 Win10 上运行的桌面端 exe：

```powershell
.\windows-mfc\build-winforms.bat
```

产物路径：

```text
windows-mfc\build-winforms\MoneyAppDesktop.exe
```

运行前请先启动后端，并确认以下地址可访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/v1/health`

> 说明：新版桌面端壳页面默认从本地 `web/desktop-shell/index.html`（`file://`）加载，不再要求服务器必须暴露 `/desktop-shell/` 静态页面。

桌面端目前已具备与 Android 对齐的四个入口：

- `情绪信号`
- `一进二选股`
- `弱转强选股`
- `Top5 推荐`

并带有桌面增强能力：

- 请求耗时
- 缓存命中状态
- 数据来源/降级状态
- 请求历史
- 宿主日志
