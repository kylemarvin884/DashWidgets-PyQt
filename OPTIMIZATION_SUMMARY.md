# 优化总结（2026-08-28）

本轮围绕功能、性能、稳定性、资源占用与插件系统做了一次全面优化。
测试基线：`uv run pytest` → **86 passed**（优化前 17 个用例中 1 个失败）。

## 第十五轮：汇率货币对自定义 + 自定义设置页面 API（2026-08-29）

- **汇率组件每行货币对可自定义**：选项 schema 新增 `currency_pair` 类型（一行 = 基准货币 + 目标货币两个下拉），汇率组件的 5 行各自可选任意两种货币组合；`ExchangeService` 改为 EUR 中转（一次请求取 EUR→20 种货币，任意对 A/B 汇率 = EUR→B ÷ EUR→A，`cross_rate()` 静态换算），配置变化时组件重建行并刷新。
- **自定义设置页面 API**：`widget_options.register_settings_page(widget_id, page_id, title, factory, icon)` — 组件/插件可在组件设置窗口注册**多个**自定义页面（page_id 去重、工厂延迟调用、可注销）；`WidgetBase.register_settings_page()` 提供组件侧便捷入口；设置窗口把注册的页面追加为独立导航页。

## 第十四轮：组件布局/样式打磨（2026-08-29）

逐一审查六个组件的渲染截图后修正：

- **番茄钟**：设置齿轮原来独占一整行（浪费约 26px 高度），并入底部信息行（统计居中 + 齿轮固定右下角）。
- **日历**：7 列原来按内容自然宽度分布，周末列被挤压；改为 `setColumnStretch` 均匀拉伸填满卡片宽，列间距统一。
- **系统监控**：进度条起点是固定 60px、右侧留 72px，标签/数值/条三者错位；重写 paintEvent 为两行规范布局——第一行标签（左）+ 百分比（右）对齐，第二行进度条占满统一边距（14px）的整行宽。
- **待办**：行距 2px、输入框贴边太挤；行距 6px、外边距 16px、输入框 padding 6px 10px。
- **音乐**：外边距 14→16、行距 8→12，信息与按钮行的呼吸感。

## 第十三轮：组件设置升级为 FluentWindow 窗口（2026-08-29）

- **从模态 QDialog 升级为 `FluentWindow`**（qfluentwidgets 官方推荐的多页面窗口形态）：左侧导航栏分区切换（外观 / 信息显示 / 快捷方式，无对应分区的组件自动隐藏该项），窗口自带云母材质与 Fluent 标题栏；导航栏底部放置「恢复默认」。
- 分区子界面为透明背景 ScrollArea（`_SettingsPage`），云母透出；模态 `exec()` 改为独立 `show()`，设置时可实时观察桌面组件的变化。
- 两个调用点（widgets_view 与桌面组件右键菜单）同步迁移；测试导入更新，85 passed。

## 第十二轮：组件设置对话框重写为原生 SettingCard（2026-08-29）

- **推倒重写**：原来 569 行手写行布局（`标签: + 控件 + addStretch`）、"显示秒数"用是/否下拉、时钟/通用两套重复代码、无恢复默认。现在整体换为 qfluentwidgets 原生 **SettingCard 卡片**（图标 + 标题/描述 + 右侧控件），与主窗口设置页同一视觉语言：滑杆用 `RangeSettingCard`、布尔项用 `SwitchSettingCard`（原生开关替代是/否下拉）、多选项用 `OptionsSettingCard`、颜色用自绘 `_ColorSettingCard`（色块点击弹 QColorDialog）。
- **实现要点**：qfluentwidgets 的卡片需要 ConfigItem 驱动，为每张卡片创建独立临时 ConfigItem（RangeConfigItem/OptionsConfigItem/ConfigItem），`valueChanged/checkedChanged` 桥接到单键即时保存与组件推送；时钟透明度卡片（百分比）与 0-1 存储值之间的换算收敛在一处。
- **分区**：「外观」/「信息显示」/「快捷方式」三区，底部新增 **恢复默认** 按钮与「完成」。
- **存储语义优化**：只在用户实际改动某项时写入该键（旧版打开对话框就写入全部键），未改动的键由组件默认值兜底。
- 修复滑杆 268px 最小宽导致的卡片溢出。

## 第十一轮：字体统一（主页标题与全库 44 处手写字体）（2026-08-29）

- **问题**：主页标题等用的 `QFont("Segoe UI Variable Display")` 在多数机器上不存在（`exactMatch()==False`），Qt 会静默替换成不可控的默认字体；而 qfluentwidgets 原生标签走 `qconfig.fontFamilies`（Segoe UI → Microsoft YaHei），两套字体栈并存导致主页字重、字形与周围标签不一致。
- **修复**：`display_font/subtitle_font` 改为复用 qfluentwidgets 的字体栈（`qconfig.get(qconfig.fontFamilies)` + `setPixelSize`，与其 `getFont()` 同源）；新增 `widget_font(px, weight)`，批量替换 18 个组件文件里全部 44 处 `QFont("Segoe UI Variable", pt, ...)` 手写字体（pt→px 按 4/3 换算保持视觉大小）。
- 验证：display/widget 字体 families 与 `BodyLabel().font().families()` 完全一致。

## 第十轮：云母真正打通（main.py 全局 QSS 是最后一块挡板）（2026-08-29）

- **根因**：`main.py` 里还残留一整块应用级 Claude QSS——`QWidget { background-color: #faf9f5 }` 强制所有控件不透明米白，此前在 `app/` 目录搜索所以漏掉。删除该 QSS 块与「强制浅色主题」逻辑（主题交还 qfluentwidgets 默认 Auto）。
- 逐像素验证：完整启动路径下窗口从 `#faf9f5 alpha=255`（不透明）变为 `#ffffff alpha=127`（半透明，Mica 材质透出），并保持稳定。
- 字体：随包的 HarmonyOS Sans SC 仍作为应用默认字体（中文渲染），Fluent 控件各自的 font-family 不受影响。

## 第九轮：云母效果、通知与字体（2026-08-29）

- **云母（Mica）打通**：qfluentwidgets `FluentWindow` 本就默认启用 Mica（窗口背景 alpha=0），但页面级不透明 QSS 挡住了它——小组件管理页整页刷成卡片色、分组页等亦有类似问题。全部改为透明背景，Mica 材质得以透出（浅色下半透明灰、卡片浮层；深色趋近实色 #202020，符合 Win11 行为）。
- **通知（Toast）对齐 Fluent 通知卡**：圆角 12→8px；背景改半透明层叠色（浅色近白 94%/深色 44,44,44 92%）+ 1px 描边；标题/正文从 10pt/9pt bold 改为 Body Strong 14px / Body 12px（Segoe UI Variable Text）；info/success/warning/error 图标色从 Material 色改为 WinUI SystemFillColor（accent/success/caution/critical）；进出场动画 280→150ms 统一 OutCubic。
- **字体收敛**：字体辅助函数提升为 `Win11Style.display_font()/subtitle_font()` 全局共享；分组页标题 24px bold + Tailwind 灰硬编码 → Display 28 + 主题 token；残留 9pt/10pt/11px 微型字号统一为 12px Caption；源码中不再有 Georgia/衬线残留。

## 第八轮：主页排版对齐 Fluent 2 + 动效（2026-08-29）

- **主页字阶对齐 Fluent Type Ramp**：页面标题 36px 衬线 → Display 28px Regular（Segoe UI Variable Display）；分区标题（已启用的组件/使用排行）22px 衬线 → Subtitle 20px Semibold；表头/徽章统一 Caption 12px。
- **主页排版节奏**：页面边距 40px、分区间距 24px、卡片间距 8px（Fluent 8px 节奏）；统计卡片改头部「图标+标签」行 + Display 数值的卡片模式（28px Regular，原衬线 28px），高度 72→84。
- **去品牌化硬编码色**：排行榜前三名金银铜（#FFD700 等）→ 前三名用主题强调色、其余次要色（Fluent 无金属色概念）；统计卡三色图标统一主题强调色。
- **动效（Fluent 标准参数）**：
  - 主页首次切入：分区 150ms 淡入 + 24px 上移（OutCubic），40ms 阶梯延迟依次入场；
  - 桌面组件显示：150ms 窗口透明度淡入（OutCubic），尊重外观设置的目标透明度；
  - 排行进度条数值变化：250ms OutCubic 缓动。
- 动画宿主均为父控件（随父销毁），淡入幂等防重入。

## 第七轮：Fluent 2 菜单与组件样式对齐（2026-08-29）

- **统一 WinUI MenuFlyout 规格菜单**（`Win11Style.menu_qss()`，托盘菜单与桌面组件右键菜单共用）：8px 外圆角、1px 卡片描边、条目 14px Segoe UI Variable Text + 4px 选中圆角、subtle 悬停叠层、1px 分隔线、图标左缘 8px 内边距。
- **托盘菜单**：从无样式原生 QMenu 换为 Fluent 规格，并按信息架构重排（显示窗口/设置 → 小组件操作 → 主题 → 退出）；托盘菜单长驻，主题切换时自动重刷样式。
- **组件右键菜单**：内联 QSS 收敛到共享 `menu_qss()`（每次右键重建，自动跟随主题）。
- **组件标题统一为 Fluent Caption Semibold**（12px 次要色）：系统监控/RSS/文档查看器的手写标题样式收敛到 `Win11Style.widget_title()`；设置页分区标题从衬线 18px 改为 Fluent Body Strong（14px Semibold，`label_title`）。

## 第六轮：回归 Fluent 原生设计语言（2026-08-29）

- **主窗口**：删除约 260 行覆盖 qfluentwidgets 的自定义 QSS（奶油画布/珊瑚红/衬线标题/自定义导航与按钮），视觉完全交还原生 Fluent 主题，浅色/深色随系统自动切换。
- **`Win11Style` 色板换成 WinUI 3 官方 token**（键名不变，自动传播到全部桌面组件、右键菜单与设置/计时/番茄钟/倒数日对话框）：浅色 `#f9f9f9` 底 + `#ffffff` 卡片 + 系统蓝 `#0078d4`；深色 `#202020` 底 + `#2b2b2b` 卡片 + `#4cc2ff` 强调；语义色对齐 SystemFillColor（success/danger/caution）。标题字体从 Georgia 衬线改为 Segoe UI Variable Display。
- **桌面组件卡片圆角 16px → 8px**（Fluent 卡片标准）；组件内文字色从奶油调 rgba 改为中性 Fluent 文本色。
- 散落的硬编码语义色（主页"启用中"徽章/圆点、电池环、计时器到时红）改从主题 token 取值，随浅深色自动切换。

## 第五轮：右键菜单统一（2026-08-29 凌晨）

- **修复部分组件右键菜单黑底**：图片/文档查看器原来在组件内部自建 `QMenu(self)`，继承了组件窗口沿层级传播的 `background: transparent` 样式且自身无样式表 → 渲染成黑色。
- **统一右键菜单**：`WidgetBase` 新增 `get_context_menu_actions()` 协议，组件以 `(icon, label, callback)` 元组贡献专属动作，由 `DesktopWidgetWindow` 的统一菜单渲染（自带主题样式）——一个菜单同时包含组件动作与「组件设置 / 窗口层级 / 鼠标穿透 / 关闭」系统项。
- 文档查看器的 QTextEdit 内建右键菜单（同样会黑底）已禁用，全选/复制改为组件动作贡献；图片/文档的更换/清除动作迁移到新协议。
- 菜单构建提取为 `_build_context_menu()` 便于测试；新增 6 个用例覆盖动作合并、条件显隐、不透明背景与「组件不得自建 contextMenuEvent」的回归约束。

## 第四轮：组件「信息显示」自定义（2026-08-28 夜）

- **声明式组件选项**：新增 `app/widgets/widget_options.py` — 每个组件可声明「信息显示」选项（bool/choice/int），设置对话框自动渲染成开关/下拉/数字控件，值保存在 `custom_settings` 并实时推送给运行中的组件。右键菜单「外观设置」更名为「组件设置」。
- **已接入的组件**：时钟（日期行）、系统监控（CPU/内存/磁盘/频率各行独立开关）、网络监控（累计流量）、天气（湿度/风速明细行，组件新增该行显示）、音乐（歌手）、电池（剩余时间）、RSS（显示条数 + 来源）、汇率（USD/EUR/GBP/JPY/HKD 各币种独立开关）。
- RSS 改设置时用最近一次抓取的数据直接重建条目行，无需重新联网；汇率/系统监控/网络监控的行改为容器化，支持独立隐藏。
- 修复 `run_in_background` 的边界问题：组件在后台任务完成前被销毁时，emit 已删除的信号对象会抛 RuntimeError，现安全忽略。
- 新增 `tests/test_widget_options.py`（11 个用例）：schema 合法性/默认值一致性、各组件选项消费（显隐切换、RSS 条数重建）、设置对话框渲染/收集/回填。

## 第三轮：监控组件线程化与绘制优化（2026-08-28 深夜）

- **psutil 全部移出 UI 线程**：新增 `SystemStatsService`（`app/services/system_stats_service.py`）— 单个后台线程统一采样系统（CPU/内存/磁盘，2s）与网络（1.5s）指标，经 Qt 信号推送；引用计数启停，所有订阅组件关闭后线程结束。系统监控/网络监控组件改为订阅该服务（原来各自在 UI 线程上跑 psutil 定时器，机械盘上的 `disk_usage` 会卡 UI）。
- **paint 事件分配缓存**：`_StatBar`（3 个 QFont/次）、`SpeedIndicator`（3 个 QFont + 2 个 QPainterPath/次）、番茄钟 `TimerRing`（QFont/次）改为构造时创建一次复用。
- **调试窗口定时器仅可见时运行**：日志页 200ms 轮询与工具页 2s 性能采样原来在应用启动即常转（调试窗口默认隐藏），现在 showEvent 启动、hideEvent 停止；日志页的「自动刷新」勾选状态跨显隐保留。

## 第二轮：组件体验与 UI 修复（2026-08-28 晚）

- **外观设置对话框黑底修复**：对话框以桌面组件窗口为父窗口，继承了组件窗口的 `background: transparent` QSS（样式表沿父子链传播）且无透明属性配合，导致背景渲染为黑色。现在对话框自带主题感知样式表（浅色奶油/深色海军蓝），主题切换时自动重应用；顺带修复了非时钟组件透明度回显错误（把 0-1 小数当百分数读）。
- **时钟拖动修复**：无边框时钟窗口整体背景 alpha=0，Windows 分层窗口对全透明像素做鼠标穿透命中，导致只有文字笔画能抓住。现在绘制一层 alpha=1 的隐形底色（肉眼不可见）保证整个窗口区域可拖拽；同时修正了子组件事件转发的坐标系换算（原来把子组件局部坐标当窗口坐标用），拖拽状态机重构为 `_begin_drag/_update_drag/_end_drag`，悬停默认手形光标、拖拽中闭合手形。
- **时钟设计升级**：新增日期行（如「8月28日 周五」），外观设置中新增「显示秒数」开关，默认窗口尺寸 170×88 适配两行布局。

## 性能与占用

### 主页刷新（原 1Hz 全量重建）
- 原实现每秒销毁并重建统计卡片/芯片/排行行，且每秒调用 3 次 `get_all_widgets()`（每次都遍历插件注册表）。
- 现改为 **事件驱动**：`widgets_changed` / `widget_shown` / `widget_closed` 信号触发全量刷新；30 秒慢速 tick 只原地更新数值文本（进行中会话的实时时长）。
- 排行行支持原地更新（`_RankRow.update_data`），组件集合不变时不重建任何控件；进度条改为真实得分占比（原为按名次伪造的假数据）。

### 网络请求全部移出 UI 线程
- 新增通用后台任务工具 `app/utils/async_fetch.py`（QThreadPool + Qt 信号自动跨线程排队）。
- **天气**：构造函数与 30 分钟定时器中的阻塞 `get_weather()` 改为工作线程执行；获取失败时 UI 显示「获取失败」而不是静默吞掉；无缓存且失败时服务层抛出异常由组件兜底。
- **天气服务请求去重**：`_fetch_lock` 串行化并发请求（双检缓存），多个天气组件同时刷新只发一次真实请求。
- **天气城市缓存**：`get_location` 的响应里本就带 city/country，现在直接缓存，砍掉了每次刷新都发起的第二个 IP 定位请求（城市信息也随缓存文件持久化）。
- **RSS**：首次运行不再同步抓取默认订阅源（原来会阻塞启动）；组件内通过工作线程刷新并交错合并各源条目，点击条目可打开原文。
- **汇率**：原来整块是硬编码假数据；新建 `ExchangeService`（frankfurter.app，免费无 Key，CNY 基准），1 小时缓存 + 离线回退旧缓存，组件在工作线程获取。

### 媒体控制服务（音乐组件）
- 原来 `MusicWidget` 每秒在 **UI 线程** 调 `refresh()`（winrt 新建事件循环 / COM 枚举 / EnumWindows），同时还有一个 3 秒轮询线程做同样的事。
- 现在：状态只由单一轮询线程探测，经 Qt 信号 `media_signals.state_changed` 自动排队回 UI 线程；组件的 1 秒 UI 定时器删除。
- `start_polling` 引用计数去重：重复创建组件不再多开线程；`stop_polling` 所有监听者退出后才真正停止（原来一个组件关闭会把所有人的轮询停掉）。
- winrt 的 asyncio 事件循环按线程缓存复用（原来每次探测新建+销毁）；封面缩略图内容不变时不再重复写盘。
- 修复：`previous_track` 方法名不匹配导致「上一曲」按钮实际是坏的。

### 定时器与重绘
- 计时器组件：100ms tick + 每次累减 100ms（有累积漂移）→ 250ms tick + `QElapsedTimer` 单调时钟计算剩余时间（零漂移）；样式表只在完成状态变化时重设。
- 秒表：50ms → 100ms。
- 笔记组件：原来每敲一个键就写一次 `note.txt` → 600ms 防抖，关闭前补写。

### 内存
- 图片组件：加载时经 `QImageReader` 解码降采样，最长边限制 2560px（6000×4000 照片约 96MB → 约 17MB 常驻）。
- 隐藏桌面组件时对窗口 `deleteLater()`，窗口与子组件（含 widget 自建定时器）及时释放。

## 稳定性

- **使用统计接通**：`UsageTracker.start_session/end_session` 原来从未被调用（主页排行的核心数据源是空的）。现在桌面组件显示/隐藏/关闭时自动记录，退出应用前 `end_all_sessions()` 落盘；进行中会话有实时时长/分数（`get_live_*`）。
- **RSS 配置兼容**：旧版 `rss_feeds.json` 的列表格式导致加载崩溃，现在两种格式都能读。
- 隐藏组件窗口泄漏：`close()` 后补 `deleteLater()`。

## 插件系统

- **`fire_trigger` 修复**：原来以类方法方式调用实例方法 `EventBus.emit`，必然 AttributeError 且被吞掉。
- **热重载**：`PluginManager.reload_plugin()` — 卸载 → 清理 `sys.modules` 模块缓存（按路径 stem，修复了原来按插件 id 清理的 mismatch）→ 清理 `__pycache__`（同尺寸源码修改会命中陈旧字节码）→ 重新执行插件代码。调试窗口「重载插件」、`.dw` 覆盖升级后均走真热重载。
- **权限落地**：
  - 「始终允许」持久化到 `config/plugin_permissions.json`，跨启动不重复弹窗；卸载时撤销。
  - `api.has_permission()` 依据已批准列表真实判断（原来是恒 `True` 的摆设）；`api.request_permission()` 运行时弹窗申请。
- **`min_host_version` 强制校验**：宿主版本过低时拒绝加载并在插件页显示原因。
- **钩子真实触发**：宿主现在会在应用启动/退出、组件显示/隐藏/移除时广播对应 `HookType`（原来 `emit_hook` 无任何宿主调用点，整个钩子系统是死代码）。
- **禁用语义**：禁用插件时其钩子/触发器/动作自动从共享注册表摘除，重新启用时恢复；卸载同样摘除。
- **卸载健壮性**：加载失败的插件（无运行时条目）现在也能从磁盘卸载；卸载同时清理权限授权。
- **`.dw` 版本感知升级**：拒绝降级安装；升级时保留插件数据目录的 `config.json`（原来直接 rmtree 丢数据）。

## 新增组件

- **电池**（`battery`）：psutil 读取，环形电量指示（低电量红 / 充电黄带闪电 / 正常绿），30 秒轮询，台式机自动停轮询。
- **倒数日**（`countdown`）：目标日期 + 名称，点击弹出设置对话框，配置随组件持久化。

内置组件现为 **18 个**（`app/widgets/registry.py`），新组件经 `WidgetModel._merge_new_widgets` 自动出现在组件页。

## 代码清理

- 删除互相引用但无外部引用的死代码（共 1323 行）：`glass_base.py`、`glass_surface.py`、`draggable_widget_card.py`、`widget_custom_layout.py`、`widget_layout_model.py`、`placeholder_view.py`。
- 新增 `.gitignore`，移除误提交的 51 个 `__pycache__` .pyc 文件。

## 测试

- 修复过时的天气测试（断言 emoji 图标 vs 现实现的 FluentIcon 名）。
- 新增 `tests/test_plugin_manager.py`：拓扑排序、版本解析、加载生命周期、热重载、卸载（含未加载插件）、权限持久化/拒绝/运行时检查、min_host_version、fire_trigger 事件。
- 新增 `tests/test_dw_package_service.py`：打包/读取元数据、`__pycache__` 排除、全新安装、升级/降级判定、配置保留、缺文件/路径穿越拒绝。
- `pyproject.toml` 增加 `[tool.pytest.ini_options]`。

## 运行测试

```bash
uv run pytest          # Windows GUI 环境建议加 QT_QPA_PLATFORM=offscreen
```
