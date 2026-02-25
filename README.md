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
- **圆角窗口** - 现代化的圆角设计配合阴影效果
- **透明背景** - 桌面融合的视觉体验

### 🖱️ 交互体验
- **自由拖拽** - 无边框窗口，任意位置移动
- **灵活调整** - 拖拽右下角调整组件大小
- **智能吸附** - 屏幕边缘和组件间自动对齐
- **系统托盘** - 最小化到托盘，不占用任务栏

### ⚙️ 高级功能
- **鼠标穿透** - 启用后点击穿透到下层窗口
- **层级控制** - 组件可置顶或置底显示
- **一键解除** - 托盘菜单快速解除所有穿透
- **自动保存** - 位置、大小、配置自动持久化

---

## 🧩 组件介绍

| 组件 | 描述 | 功能 |
|------|------|------|
| 🕐 **时钟** | 时间日期显示 | 实时时钟，简洁美观 |
| 📊 **系统监控** | 硬件状态监测 | CPU、内存使用率实时显示 |
| ⏱️ **计时器** | 时间管理工具 | 正计时/倒计时功能 |
| 📝 **笔记** | 快速记录工具 | 桌面便签，自动保存 |
| 🖼️ **图片** | 自定义图片展示 | 支持裁剪适配，拖拽调整 |
| 🌐 **网页** | 嵌入式浏览器 | 显示任意网页，支持导航控制 |

---

## 🚀 安装使用

### 方式一：直接运行（开发者模式）

```bash
# 克隆项目
git clone https://github.com/yourusername/DashWidgets.git
cd DashWidgets/DashWidgets-PyQt

# 安装依赖
pip install PyQt6 PyQt6-WebEngine loguru psutil

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
  - 置顶/置底显示
  - 关闭组件

### 快捷操作
- **双击托盘图标**: 打开管理器
- **托盘右键菜单**: 
  - 打开管理器
  - 切换主题
  - 解除所有鼠标穿透
  - 退出程序

---

## 🔧 开发

### 技术栈
- **GUI 框架**: PyQt6
- **网页引擎**: QtWebEngine (可选)
- **日志系统**: Loguru
- **系统监控**: psutil
- **打包工具**: PyInstaller

### 项目结构
```
DashWidgets-PyQt/
├── main.py              # 主程序入口
├── pyproject.toml       # 项目配置
├── assets/              # 资源文件
│   ├── fonts/           # 字体文件
│   ├── icons/           # 图标文件
│   └── images/          # 图片文件
└── config/              # 配置文件
    └── config.json      # 用户配置
```

### 核心类
- `BaseWidget` - 组件基类，提供拖拽、缩放、吸附等功能
- `WidgetManager` - 主窗口，管理所有组件
- `ThemeColors` - 主题颜色管理
- `WidgetConfig` - 配置持久化

---

## 📋 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.10+ (开发模式)
- **内存**: 建议 4GB 以上

---

## 📄 许可证

本项目采用 [EPL-2.0](LICENSE) 许可证。

---

## 🙏 致谢

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- [Loguru](https://github.com/Delgan/loguru) - 日志库
- [Fluent Design System](https://fluent2.microsoft.design/) - 设计灵感

---

<div align="center">

**Made with ❤️ by Kyle from Little Tree Studio**

</div>
