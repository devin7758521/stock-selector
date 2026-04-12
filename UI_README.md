# JusticePlutus UI 使用说明

## 概述

JusticePlutus UI 是一个基于 PyQt6 的桌面应用程序，提供图形化界面来运行A股周K线选股系统。

## 功能特性

- **图形化界面**：专业的暗色主题设计
- **实时选股**：后台线程执行选股，不阻塞UI
- **结果展示**：表格显示选股结果，支持点击查看详情
- **多维度分析**：
  - 技术指标分析（MACD、KDJ、RSI）
  - 基本面分析（ROE、PE、PB、EPS）
  - LLM智能分析（情绪分、评级、操作建议）

## 运行方式

### 方式1：直接运行Python脚本

```bash
# 安装依赖
pip install -r requirements.txt

# 运行UI
python run_ui.py
```

### 方式2：打包成EXE文件

```bash
# 运行打包脚本
python build_exe.py

# 生成的EXE文件位置
dist/JusticePlutus.exe
```

## UI界面说明

### 主界面布局

```
┌─────────────────────────────────────────────────────────┐
│  工具栏: [开始选股] [停止]           统计: 共筛选 0 只股票  │
├─────────────────────────────────────────────────────────┤
│  进度条                                                  │
├───────────────────────────┬─────────────────────────────┤
│  选股结果表格              │  详细分析                    │
│  ┌─────┬─────┬─────┐     │  ┌─────────────────────┐   │
│  │代码 │名称 │价格 │...  │  │ 技术指标分析         │   │
│  ├─────┼─────┼─────┤     │  │  MACD: 0.5          │   │
│  │...  │...  │...  │     │  │  KDJ: (60,55,71)    │   │
│  └─────┴─────┴─────┘     │  └─────────────────────┘   │
│                           │  ┌─────────────────────┐   │
│                           │  │ 基本面分析           │   │
│                           │  │  ROE: 15.2%         │   │
│                           │  │  PE: 6.5            │   │
│                           │  └─────────────────────┘   │
│                           │  ┌─────────────────────┐   │
│                           │  │ LLM智能分析          │   │
│                           │  │  情绪分: 85         │   │
│                           │  │  评级: ⭐⭐⭐⭐⭐      │   │
│                           │  └─────────────────────┘   │
└───────────────────────────┴─────────────────────────────┘
│  状态栏: 就绪                                            │
└─────────────────────────────────────────────────────────┘
```

### 操作流程

1. **开始选股**：点击"🚀 开始选股"按钮
2. **查看进度**：进度条显示当前处理进度
3. **查看结果**：选股完成后，结果会显示在左侧表格
4. **查看详情**：点击表格中的股票，右侧面板显示详细分析
5. **停止选股**：选股过程中可点击"⏹ 停止"按钮中断

## 技术架构

### MVC架构

遵循严格的MVC分离原则：

- **Model（模型）**：`screener.core.StockSelector` - 选股业务逻辑
- **View（视图）**：`ui.main_window.MainWindow` - UI界面
- **Controller（控制器）**：`ui.controller.StockScreenerController` - 协调Model和View

### Signal/Slot机制

UI和业务逻辑通过Qt的signal/slot机制通信，确保解耦：

```python
# UI发送信号
start_screening_requested = pyqtSignal()

# Controller连接信号
view.start_screening_requested.connect(controller.start_screening)

# Controller发送信号
results_updated = pyqtSignal(list)

# UI连接信号
controller.results_updated.connect(view.update_results)
```

### 后台线程

耗时操作在后台线程执行，避免阻塞UI：

```python
class ScreeningWorker(QThread):
    progress_updated = pyqtSignal(int, int)
    screening_finished = pyqtSignal(list)
    
    def run(self):
        # 在后台执行选股
        results = self._selector.run()
        self.screening_finished.emit(results)
```

## 打包说明

### PyInstaller配置

使用 `justiceplutus.spec` 文件配置打包：

- **单文件模式**：所有依赖打包到一个EXE文件
- **无控制台**：`console=False` 隐藏命令行窗口
- **包含资源**：QSS样式表、配置文件等

### 打包步骤

```bash
# 1. 安装PyInstaller
pip install pyinstaller

# 2. 运行打包脚本
python build_exe.py

# 3. 查看生成的EXE
# dist/JusticePlutus.exe
```

### 打包注意事项

1. **文件大小**：打包后的EXE文件较大（约100MB+），包含Python运行时和所有依赖
2. **启动速度**：首次启动较慢，需要解压临时文件
3. **杀毒软件**：可能被误报为病毒，需要添加信任
4. **路径问题**：EXE运行时的工作目录可能与源码不同，注意相对路径

## 自定义样式

### 修改主题

编辑 `ui/styles/dark_theme.qss` 文件可以自定义UI样式：

```css
/* 修改按钮颜色 */
QPushButton {
    background-color: #3c3f41;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 8px 16px;
    color: #e0e0e0;
}

/* 修改表格样式 */
QTableWidget {
    background-color: #2b2b2b;
    alternate-background-color: #323232;
    gridline-color: #404040;
}
```

### 添加图标

在 `justiceplutus.spec` 文件中指定图标：

```python
exe = EXE(
    ...
    icon='path/to/icon.ico',  # 添加图标文件路径
)
```

## 常见问题

### Q: UI无法启动？

A: 检查是否安装了所有依赖：
```bash
pip install -r requirements.txt
```

### Q: 选股过程中UI卡住？

A: 不应该发生，选股在后台线程执行。如果卡住，请检查：
- 是否有其他线程阻塞
- 是否有死循环

### Q: 打包后的EXE无法运行？

A: 检查：
- 是否缺少依赖库（在spec文件的hiddenimports中添加）
- 是否缺少资源文件（在spec文件的datas中添加）
- 查看错误日志：在命令行中运行EXE查看错误信息

### Q: 如何修改选股参数？

A: 编辑 `config.yaml` 文件，修改选股参数：
```yaml
screener:
  price_min: 3
  price_max: 70
  min_listed_days: 730
  ...
```

## 开发说明

### 添加新功能

1. **添加新插件**：在 `screener/plugins/` 目录下创建新插件
2. **更新UI**：在 `ui/main_window.py` 中添加新的UI组件
3. **连接信号**：在 `ui/controller.py` 中连接新的signal/slot

### 测试

```bash
# 测试UI
python test_ui.py

# 测试插件
python test_plugins.py

# 测试选股
python main.py
```

## 许可证

Copyright (c) 2026 JusticePlutus. All rights reserved.
