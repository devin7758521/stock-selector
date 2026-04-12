# JusticePlutus

基于 AI 和 LLM 的 A 股周K线选股系统，集成多维度分析和五星评级功能。

## 功能特性

- **多数据源集成**：支持多个数据源轮换，确保数据可靠性
- **AI 分析**：基于技术指标的情绪分析
- **LLM 分析**：集成 Deepseek reasoner 和 Gemini 2.5 Flash 模型
- **新闻搜索**：集成东方财富、新浪财经、同花顺、雪球等免费财经新闻源
- **五星评级系统**：基于情绪分和技术指标的综合评级
- **股票列表分析**：批量分析股票列表，生成详细报告
- **技术指标分析**：计算 MACD、KDJ、RSI 等技术指标
- **基本面分析**：获取 ROE、PE、PB、EPS 等财务数据并计算基本面评分
- **插件化架构**：核心功能与扩展功能分离，易于维护和扩展
- **东方财富集成**：支持从东方财富导入自选股和持仓股进行分析

## 项目结构

```
driverplus/
├── main.py              # 主脚本
├── config.yaml          # 配置文件
├── test_llm_features.py # LLM 分析功能测试
├── screener/            # 核心模块
│   ├── core/            # 核心功能
│   │   ├── selector.py  # 选股器
│   │   └── plugin.py    # 插件管理器
│   ├── datasources.py   # 数据源
│   ├── filter.py        # 筛选逻辑
│   ├── calendar.py      # 交易日历
│   ├── wecom.py         # 企业微信推送
│   ├── utils.py         # 工具函数
│   └── plugins/         # 插件
│       ├── llm_analysis/        # LLM 分析插件
│       │   ├── plugin.py        # 插件入口
│       │   ├── analyzer.py      # 分析器
│       │   └── search_service.py # 新闻搜索服务
│       └── stock_list_analysis/ # 股票列表分析插件
│           ├── plugin.py        # 插件入口
│           └── __init__.py      # 初始化文件
└── README.md            # 说明文档
```

## 配置说明

### 基本配置

在 `config.yaml` 文件中配置以下参数：

```yaml
# driverplus 配置文件

# 数据源配置
datasources:
  tushare_token: ""  # Tushare API Token
  joinquant_username: ""  # JoinQuant 用户名
  joinquant_password: ""  # JoinQuant 密码
  mairui_token: ""  # 迈瑞 API Token

# 选股配置
screener:
  price_min: 3  # 最低价格
  price_max: 70  # 最高价格
  min_listed_days: 730  # 最小上市天数
  weekly_ma: 25  # 周均线
  vol_ma_short: 5  # 短期成交量均线
  vol_ma_long: 60  # 长期成交量均线
  vol_deviation_min: -0.03  # 成交量偏差最小值
  vol_deviation_max: 0.07  # 成交量偏差最大值
  min_daily_amount: 300000000  # 最低日成交额
  spot_prefilter_amount: 200000000  # 预筛选成交额
  weekly_mode: "realtime"  # 周K模式：realtime 或 completed

# 请求配置
request:
  max_workers: 8  # 最大工作线程数
  delay_min: 0.2  # 最小延迟
  delay_max: 0.5  # 最大延迟
  max_retries: 3  # 最大重试次数
  retry_backoff: 2  # 重试退避系数

# 企业微信配置
wecom:
  webhook_url: ""  # 企业微信 Webhook URL

# 东方财富配置
eastmoney:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: ""  # 不推荐直接在配置文件中存储
  
  # 分析设置
  analysis:
    watchlist: true  # 是否分析自选股
    portfolio: true   # 是否分析持仓股
    export_format: "csv"  # 导出格式: csv 或 json
    generate_report: true  # 是否生成分析报告

# 同花顺配置
tenjqka:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: ""  # 不推荐直接在配置文件中存储

# 长桥配置
longbridge:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: ""  # 不推荐直接在配置文件中存储

# 插件配置
plugins:
  ai_analysis:
    enabled: true  # 是否启用 AI 分析
  llm_analysis:
    enabled: true  # 是否启用 LLM 分析
  stock_list_analysis:
    enabled: true  # 是否启用股票列表分析
  technical_analysis:
    enabled: true  # 是否启用技术指标分析
  fundamental_analysis:
    enabled: true  # 是否启用基本面分析
```

### 企业微信推送配置

系统支持企业微信机器人推送，可在启动时和选股完成时发送通知。

#### 配置步骤

1. 在企业微信群聊中添加机器人，获取 Webhook URL
2. 在 `config.yaml` 中配置：

```yaml
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
```

#### 推送消息格式

**启动通知**：
```
🚀 JusticePlutus 选股系统启动

启动时间: 2026-04-12 09:00:00
系统状态: 开始选股...

请稍候，选股完成后将推送结果。
```

**结果通知**：
```
📊 选股播报 2026-04-12，共 10 只

昊华科技（600378）
凯盛科技（600552）
...
```

详细配置说明请参考 [WECOM_CONFIG.md](WECOM_CONFIG.md)

### 东方财富、同花顺、长桥集成配置

系统支持从东方财富、同花顺、长桥导入自选股和持仓股进行分析。

#### 配置步骤

1. **获取Cookie**：
   - **东方财富**：登录 https://www.eastmoney.com/，在浏览器开发者工具中获取Cookie
   - **同花顺**：登录 https://www.10jqka.com.cn/，在浏览器开发者工具中获取Cookie
   - **长桥**：登录 https://www.longbridgeapp.com/，在浏览器开发者工具中获取Cookie

2. **设置Cookie**（推荐通过环境变量）：

```bash
# Windows
set EASTMONEY_COOKIE=your_eastmoney_cookie_here
set TENJQKA_COOKIE=your_tenjqka_cookie_here
set LONGBRIDGE_COOKIE=your_longbridge_cookie_here

# Linux/Mac
export EASTMONEY_COOKIE=your_eastmoney_cookie_here
export TENJQKA_COOKIE=your_tenjqka_cookie_here
export LONGBRIDGE_COOKIE=your_longbridge_cookie_here
```

3. **GitHub Actions**：
   - 在仓库设置 → Secrets and variables → Actions
   - 添加 EASTMONEY_COOKIE、TENJQKA_COOKIE、LONGBRIDGE_COOKIE 密钥

#### 使用方法

```bash
# 分析券商自选股和持仓股
python analyze_eastmoney.py
```

详细配置说明请参考 [EASTMONEY_CONFIG.md](EASTMONEY_CONFIG.md)

### GitHub Secrets 配置

在 GitHub 仓库的 Settings > Secrets and variables > Actions 中添加以下 Secrets：

| Secret 名称 | 描述 | 示例值 |
|------------|------|--------|
| `TUSHARE_TOKEN` | Tushare API Token | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `JOINQUANT_USERNAME` | JoinQuant 用户名 | `your_username` |
| `JOINQUANT_PASSWORD` | JoinQuant 密码 | `your_password` |
| `MAIRUI_TOKEN` | 迈瑞 API Token | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook URL | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `LITELLM_API_KEY` | LiteLLM API Key | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `DEEPSEEK_API_KEY` | Deepseek API Key | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `GEMINI_API_KEY` | Gemini API Key | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |

## 环境变量配置

### LLM 模型配置

在运行前设置以下环境变量：

```bash
# LiteLLM 模型配置
# 支持以下模型：
# - deepseek/deepseek-reasoner-v1.5
# - gemini/gemini-2.5-flash
export LITELLM_MODEL="deepseek/deepseek-reasoner-v1.5"

# Deepseek API Key
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# Gemini API Key
export GEMINI_API_KEY="your_gemini_api_key"
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行方式

### 本地运行

```bash
python main.py
# 或指定配置文件
python main.py --config config.yaml
```

### GitHub Actions 运行

在 `.github/workflows` 目录下创建工作流文件，例如 `stock-screener.yml`：

```yaml
name: Stock Screener

on:
  schedule:
    - cron: '30 15 * * 1-5'  # 每个交易日下午 3:30 运行
  workflow_dispatch:  # 手动触发

jobs:
  screen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run stock screener
        run: python main.py
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
          JOINQUANT_USERNAME: ${{ secrets.JOINQUANT_USERNAME }}
          JOINQUANT_PASSWORD: ${{ secrets.JOINQUANT_PASSWORD }}
          MAIRUI_TOKEN: ${{ secrets.MAIRUI_TOKEN }}
          WECOM_WEBHOOK_URL: ${{ secrets.WECOM_WEBHOOK_URL }}
          LITELLM_MODEL: ${{ secrets.LITELLM_MODEL }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

## 插件使用

### LLM 分析插件

LLM 分析插件会对筛选出的股票进行情绪分析和五星评级，基于：
- 技术指标分析
- 新闻情绪分析
- 趋势预测
- 操作建议

### 股票列表分析插件

股票列表分析插件支持批量分析股票列表，生成详细的分析报告，包括：
- 股票基本信息
- 技术指标分析
- 情绪分析
- 五星评级
- 操作建议

## 注意事项

1. **数据安全**：请不要在代码中硬编码 API Key，使用环境变量或 GitHub Secrets
2. **API 调用限制**：注意各数据源的 API 调用限制，避免频繁调用导致被封禁
3. **网络环境**：确保网络环境能够正常访问各数据源和 LLM 服务
4. **风险提示**：本系统仅供学习参考，不构成投资建议

## 许可证

Copyright (c) 2026 driverplus. All rights reserved.
