# DashWidgets

<div align="center">

**Windows 桌面小组件管理器**

基于 PyQt6 开发的现代化桌面小组件系统

[功能特性](#-功能特性) • [安装使用](#-安装使用) • [组件介绍](#-组件介绍) • [开发](#-开发)

</div>

---

## 📖 简介

DashWidgets 是一款受 Windows 11 小组件面板启发的桌面小组件管理器。它允许用户在桌面上放置各种实用小组件，提升工作效率和桌面美观度。

---

## ✨ 功能特性

### 🎨 界面设计
- **Fluent Design** - 采用 Windows 11 设计语言
- **双主题支持** - 浅色/深色主题一键切换
- **多种配色** - 蓝、绿、紫、橙、红、青 6 种配色方案
- **圆角窗口** - 现代化的圆角设计配合阴影效果
- **透明背景** - 桌面融合的视觉体验
- **开关动画** - 平滑的淡入淡出效果

### 🖱️ 交互体验
- **自由拖拽** - 无边框窗口，任意位置移动
- **灵活调整** - 拖拽右下角调整组件大小
- **智能吸附** - 屏幕边缘和组件间自动对齐
- **系统托盘** - 最小化到托盘，不占用任务栏
- **全局热键** - Win+Shift+D 快速显示/隐藏所有组件

### ⚙️ 高级功能
- **鼠标穿透** - 启用后点击穿透到下层窗口
- **层级控制** - 组件可置顶显示或仅在桌面显示
- **一键解除** - 托盘菜单快速解除所有穿透
- **自动保存** - 位置、大小、配置自动持久化
- **配置导入导出** - 轻松备份和恢复配置

---

## 🧩 组件介绍

|| 组件 | 描述 | 功能 |
||------|------|------|
|| 🕐 **时钟** | 时间日期显示 | 实时时钟，右键切换秒数显示 |
|| 📊 **系统监控** | 硬件状态监测 | CPU、内存使用率实时显示 |
|| ⏱️ **计时器** | 正计时工具 | 秒表功能，精确计时 |
|| ⏰ **倒计时** | 倒计时工具 | 设置时间倒计时，结束音效弹窗提醒 |
|| 📝 **笔记** | 快速记录工具 | 桌面便签，自动保存 |
|| 🎵 **音乐** | 媒体控制 | 控制系统媒体播放，显示当前曲目 |
|| 🌤️ **天气** | 天气信息 | 实时天气，湿度风速，异步加载 |
|| ✅ **待办** | 任务管理 | 待办清单，支持添加删除标记完成 |
|| 🌍 **世界时钟** | 多时区显示 | 全球主要城市时间，时差显示 |
|| 📡 **网络监控** | 网络状态 | 实时网速、磁盘使用率显示 |
|| 🖼️ **图片** | 自定义图片展示 | 支持裁剪适配，滤镜效果（灰度/复古/反色） |
|| 🌐 **网页** | 嵌入式浏览器 | 显示任意网页，支持导航控制 |

---

## 🚀 安装使用

### 方式一：直接运行（开发者模式）

```bash
# 克隆项目
git clone https://github.com/yourusername/DashWidgets.git
cd DashWidgets/DashWidgets-PyQt

# 安装依赖 (推荐使用 uv)
uv sync

# 或使用 pip
pip install PyQt6 PyQt6-WebEngine loguru psutil pycaw

# 运行
python main.py
```

### 方式二：打包版本

1. 下载 `dist/DashWidgets` 文件夹
2. 双击运行 `DashWidgets.exe`

### 打包命令

```bash
pyinstaller --name "DashWidgets" --windowed --onedir \
  --icon "assets/images/logo.ico" \
  --add-data "assets;assets" \
  --add-data "config;config" \
  --hidden-import "PyQt6.QtWebEngineWidgets" \
  --collect-all "PyQt6" \
  main.py
```

---

## 📖 使用指南

### 添加组件
1. 点击系统托盘图标，选择"打开管理器"
2. 在管理器中选择"小组件"页面
3. 点击想要添加的组件卡片

### 组件操作
- **移动**: 拖拽组件标题栏
- **调整大小**: 拖拽右下角三角形手柄
- **右键菜单**: 
  - 鼠标穿透
  - 置顶显示（显示在所有窗口上方）
  - 置底显示（仅在桌面显示，其他窗口可覆盖）
  - 关闭组件

### 组件专属功能
- **时钟**: 右键菜单切换秒数显示
- **图片**: 右键菜单选择图片、应用滤镜效果
- **倒计时**: 结束时播放系统提示音并弹出通知
- **天气**: 自动异步获取天气，不阻塞界面

### 快捷操作
- **双击托盘图标**: 打开管理器
- **Win+Shift+D**: 全局热键，显示/隐藏所有组件
- **托盘右键菜单**: 
  - 打开管理器
  - 切换主题（浅色/深色）
  - 切换配色方案
  - 解除所有鼠标穿透
  - 退出程序

---

## 🔧 开发

### 技术栈
- **GUI 框架**: PyQt6
- **网页引擎**: QtWebEngine (可选)
- **日志系统**: Loguru
- **系统监控**: psutil
- **音频控制**: pycaw
- **打包工具**: PyInstaller

### 项目结构
```
DashWidgets-PyQt/
├── main.py              # 主程序入口（单文件应用）
├── pyproject.toml       # 项目配置
├── assets/              # 资源文件
│   ├── fonts/           # 字体文件
│   ├── icons/           # 图标文件 (SVG)
│   └── images/          # 图片文件
└── config/              # 配置文件
    └── config.json      # 用户配置
```

### 核心类
- `ThemeColors` - 主题颜色管理，支持多配色方案
- `WidgetConfig` - 配置持久化管理
- `BaseWidget` - 组件基类，提供拖拽、缩放、吸附、层级控制等功能
- `WidgetManager` - 主窗口，管理所有组件
- 各功能组件类（ClockWidget, WeatherWidget, MusicWidget 等）

---

## 📋 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.10+ (开发模式)
- **内存**: 建议 4GB 以上

---

## 📄 许可证

本项目采用 [GPL-3.0](LICENSE) 许可证。

---

## 🙏 致谢

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- [Loguru](https://github.com/Delgan/loguru) - 日志库
- [psutil](https://github.com/giampaolo/psutil) - 系统监控
- [wttr.in](https://wttr.in/) - 天气 API
- [Fluent Design System](https://fluent2.microsoft.design/) - 设计灵感

---

<div align="center">

**Made with ❤️ by Little Tree Studio**

</div>
