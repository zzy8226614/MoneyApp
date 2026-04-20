# Windows Desktop Host

本目录现在同时包含两条 Windows 宿主路线：

1. `WebView2 + MFC` 宿主源码：用于未来较新的原生宿主实现。
2. `WinForms + WebBrowser` 可编译宿主：用于当前机器直接产出可运行 exe。

## Current Responsibilities

- 初始化 WebView2
- 承载 `web/desktop-shell/` 页面
- 管理配置、菜单、日志和调试入口
- 向前端壳层提供宿主消息桥
- 将后端地址保存到本机配置文件
- 接收桌面壳层的请求日志与配置同步消息
- 在前端发起请求时回发 `host.request.received`，用于桌面端诊断面板

## Build Requirements

- 路线 A：`WebView2 + MFC`
  - Visual Studio 2022（含 MFC 工具集）
  - CMake 3.25+
  - WebView2 SDK

- 路线 B：`WinForms`
  - .NET Framework 自带 `csc.exe`
  - 无需额外安装 WebView2 SDK
  - 当前机器已验证可产出 exe

### 路线 A 需要先设置环境变量

```powershell
$env:WEBVIEW2_SDK_PATH="C:\path\to\Microsoft.Web.WebView2.<version>"
```

## Configure And Build

### 路线 A：WebView2 + MFC

```powershell
cmake -S windows-mfc -B windows-mfc/build -A x64
cmake --build windows-mfc/build --config Debug
```

### 路线 B：WinForms（当前可直接出 exe）

```powershell
.\windows-mfc\build-winforms.bat
```

输出文件：

```text
windows-mfc\build-winforms\MoneyAppDesktop.exe
```

## Runtime Notes

- WinForms 宿主会加载：`http://127.0.0.1:8000/desktop-shell/`
- 默认后端地址为 `http://127.0.0.1:8000/`
- 宿主配置保存在 `%LOCALAPPDATA%\MoneyAPPDesktop\host-config.json`
- 桌面壳层按钮会直接调用 `/api/v1/screen/*`
- 在当前机器上，`MoneyAppDesktop.exe` 已成功构建

## Source Files

- `CMakeLists.txt`
- `build-winforms.bat`
- `winforms-host/MoneyAppDesktopWinForms.cs`
- `src/MoneyAppDesktop.cpp`
- `src/MainFrame.h`
- `src/MainFrame.cpp`
- `src/WebViewHost.h`
- `src/WebViewHost.cpp`
- `src/HostConfigStore.h`
- `src/HostConfigStore.cpp`
- `src/AppHostBridge.h`
- `src/AppHostBridge.cpp`
- `src/HostMessageTypes.h`
- `legacy-src/MoneyAppDesktopLegacy.cpp`
