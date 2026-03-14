# AGENTS.md — 啄玛 (PeckTeX) 开发守则

> 本文档专供 AI 智能体阅读，定义项目架构、规范和关键约定，指引 AI 准确修改代码。

## 基本指令

- **回答语言**：始终使用中文，无论用户用什么语言提问
- **修改原则**：架构融合优先，禁止临时补丁；改动前先读懂上下文；Final Check 逐行模拟执行
- **环境约束**：不运行代码、不修改 conda 环境、不安装包

## 项目背景

**啄玛 (PeckTeX)** 是一款基于 Python 与 PySide6 开发的轻量级桌面应用。
软件通过调用视觉语言大模型（VLM）API，提取图片中包含的数学公式、化学方程式、手写推导过程以及表格图表等内容，识别并转换为 LaTeX 等标记语言代码。
核心流程：截图/粘贴/文件导入 -> VLM API 识别 -> 结果流式输出 -> HTML/KaTeX 预览。功能涵盖自动化识别、连续识别、多轮 AI 对话修正及完善的记录管理。
版本 v1.0，作者 RiverDu，依赖：`PySide6>=6.5.0`、`openai>=1.1.0`、`httpx>=0.24.0`。

## 模块结构与依赖

基于 PySide6 构建，左右分栏架构。依赖关系简述：

```text
theme.py -> gui_components.py -> gui.py <- settings.py / api_client.py / screenshot.py / renderer.py
main.py -> gui.py + theme.py
```

| 文件 | 职责说明 |
|------|------|
| `main.py` | 程序入口；执行 Qt 初始化并加载主样式。 |
| `src/gui.py` | 主窗口 `PeckTeXMainWindow`；包含业务逻辑，管理 `APIWorker`/`TestWorker` 线程。 |
| `src/gui_components.py` | GUI 组件库，如配置面板、图像目标区、结果展示区、历史面板、防滚动下拉框、日志折叠面板等。 |
| `src/theme.py` | 全局主题颜色字典及 CSS 样式表管理。**组件区禁止硬编码颜色**。 |
| `src/api_client.py` | OpenAI 协议客户端，处理流式生成、图片 Base64 编码以及多轮对话记录管理。 |
| `src/renderer.py` | 负责将 LaTeX/MathML 包装为 HTML 并调用 KaTeX 渲染及系统浏览器预览。 |
| `src/settings.py` | JSON 配置的读写、合并与结构校验。 |
| `src/screenshot.py` | 截屏功能，处理多显示器 DPI 以及鼠标遮罩框选逻辑。 |

## 代码风格与开发约束

### 命名规范
- **类**：`PascalCase`；**函数/变量**：`snake_case`；**常量**：`UPPER_SNAKE_CASE`；**私有方法/属性**：`_前缀`
- 强制使用完整的类型注解（Type Hints）。
- 缩进使用 4 空格。宽容处理行宽（100-120 字符）。
- 导包顺序：标准库 -> 第三方库 -> 本地模块。

### 注释与容错
- 关键模块与类/函数必须使用中文 docstring；复杂逻辑添加行内注释；命名自解释，避免冗余。
- 使用 `APIError(Exception)` 隔离网络异常（捕获 APITimeoutError/APIConnectionError/APIStatusError）。错误存入 `last_error` 供 UI 显示并记入日志，禁止使用原生的 `print` 强行输出。

## Qt/PySide6 核心模式

- **Signal 与 Slot**：Signal 在类级别定义，必须使用方法引用连接（如 `worker.chunk_signal.connect(self._on_chunk)`）。
- **线程管理**：耗时 I/O（如 API 请求）强制放置在 `QThread` (Worker) 中。必须实现 `abort()` 方法；在 `closeEvent` 中执行 abort -> wait(200) -> terminate 进行安全清理并终止。
- **Widget 样式**：通过 `setStyleSheet` 应用 CSS；样式代码必须在 `theme.py` 中统一定义。

## 核心业务模式

### 配置管理
配置通过 `SettingsManager` 读写工作目录下的 `config.json`；提供 `DEFAULT_CONFIG` 进行格式及字段缺失（`_ensure_required_keys`）校验。
主界面对设置的修改操作应保留在 `self.draft`（深拷贝临时字典）中，仅在用户触发“保存”时持久化到磁盘并重载。

### API 客户端
采用复用机制缓存客户端 `_cached_client`（键值 `key:url:timeout`）。
流式响应采用 `yield` 迭代器；内置 `block_list` 在流数据中实时滤除特殊标记。
使用双段超时控制 `httpx.Timeout(total, connect=5.0)`；提供 `interrupt()` 用于打断长时阻塞任务。向大模型发送后，图片的 Base64 会从对话历史截断剔除，替换为 `[图片已上传]` 以节约 Token 和系统请求资源。

### KaTeX 渲染
将文本流交至 `renderer.py` 时，自动尝试检测及补全定界符（`$$`/`\[`/`\(`/`\begin{` 等）；针对多个 `$$...$$` 提供竖排分块等处理。在系统环境生成临时 HTML。
临时网页文件路径注册至全局 `_temp_files`，并在主程序退出时主动清理系统空间。

### 配置文件结构 (config.json)

核心预设均映射在 `config.json`：

```json
{
    "auto_recognize": false, "auto_copy": false,
    "continuous_recognition": false, "continuous_chat": false, "text_recognition": false,
    "language": "zh_CN", "theme": "light", "image_sort": "time",
    "api_timeout": 30.0, "max_history": 100, "max_log": 500,
    "shortcuts": { "screenshot": "Alt+S", "paste": "Ctrl+V", "recognize": "Alt+Return" },
    "default": { "platform": "", "model": "", "function": "" },
    "platforms": { "<平台名>": { "api_url": "", "api_key": "", "models": [] } },
    "system_prompt": "...",
    "functions": { "<功能名>": "<提示词>" }
}
```

#### 关键布尔开关：
- `auto_recognize`: 若为 true，导入新图像(截图、粘贴等)时自动发起请求。
- `auto_copy`: 若为 true，识别成功后自动写入系统剪贴板。
- `continuous_recognition`: 勾选后，自动循环遍历识别内置图片文件夹中的图片列表。
- `text_recognition`: 文本识别模式，跳过发送图像本身，直接转发识别结果区的文本和提示词要求给 AI 进行校对提取任务。
- `continuous_chat`: 保持多轮对话。开启后点击识别不清除历史上下文。

#### 系统参数：
- `image_sort`: 本地文件读取排序方式： `"time"` (按修改时间) 或 `"name"` (按文件名)。仅支持 JSON 直接配置。
- `api_timeout`, `max_history` (1-1000 限额), `max_log` (100-10000 限额) 限定阈值。
