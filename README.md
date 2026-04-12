# stock selector

基于 AI 和 LLM 的 A 股周K线选股系统，集成多维度分析和五星评级功能。

## 功能特性

- **多数据源集成**：支持东方财富、同花顺、长桥等多个数据源轮换，确保数据可靠性
- **AI 分析**：基于技术指标的情绪分析
- **LLM 分析**：集成 DeepSeek reasoner 和 Gemini 2.5 Flash 模型，支持真正的新闻理解和推理
- **新闻搜索**：集成东方财富、新浪财经、同花顺、雪球、全球财经（WSJ/Reuters/Bloomberg）等
- **全球宏观分析**：支持华尔街、白宫、美联储、特朗普等国际财经动态分析
- **五星评级系统**：基于情绪分和技术指标的综合评级
- **股票列表分析**：批量分析股票列表，生成详细报告
- **技术指标分析**：计算 MACD、KDJ、RSI 等技术指标
- **基本面分析**：获取 ROE、PE、PB、EPS 等财务数据并计算基本面评分
- **插件化架构**：核心功能与扩展功能分离，易于维护和扩展
- **东方财富集成**：支持从东方财富导入自选股和持仓股进行分析

## 核心能力

### 1. DeepSeek LLM 深度推理

使用 DeepSeek API 进行真正的新闻理解和推理分析：
- **新闻情绪判断**：理解新闻上下文，判断利好/利空/中性
- **关键事件识别**：识别对股价有影响的核心事件
- **政策影响分析**：分析国内政策对股票/行业的影响
- **宏观影响分析**：分析全球经济形势对A股的影响
- **国际局势影响**：分析华尔街、白宫、美联储等美国因素对A股的影响

### 2. 全球财经关键词库

内置超过 200 个全球财经关键词，覆盖：
- **美国因素**：特朗普、拜登、白宫、美联储、财政部、商务部、国会、关税、科技战、VIX恐慌指数
- **欧洲因素**：德国、法国、英国、欧盟委员会、欧洲央行、欧元区、英镑、普京、俄罗斯、北约
- **中东因素**：以色列、巴勒斯坦、伊朗、沙特、OPEC+
- **亚太因素**：印度莫迪、韩国三星、日本央行、澳大利亚铁矿石
- **全球机构**：G7、G20、联合国、世贸组织、世卫组织
- **金融术语**：黑天鹅、灰犀牛、尾部风险、避险情绪、流动性危机

## 项目结构

```
stock selector/
├── main.py                      # 主脚本
├── config.yaml                  # 配置文件
├── analyze_eastmoney.py        # 东方财富分析脚本
├── run_ui.py                    # UI启动脚本
├── screener/                    # 核心模块
│   ├── core/                    # 核心功能
│   │   ├── selector.py          # 选股器
│   │   └── plugin.py            # 插件管理器
│   ├── plugins/                  # 插件系统
│   │   ├── llm_analysis/        # LLM分析插件
│   │   │   ├── analyzer_enhanced.py  # 增强分析器
│   │   │   ├── deepseek_analyzer.py    # DeepSeek分析器
│   │   │   ├── search_service.py       # 新闻搜索服务
│   │   │   └── analyzers/              # 多维度分析器
│   │   │       ├── news_analyzer.py    # 消息面分析
│   │   │       ├── technical_analyzer.py  # 技术面分析
│   │   │       ├── fundamental_analyzer.py  # 基本面分析
│   │   │       ├── policy_analyzer.py   # 政策面分析
│   │   │       └── market_analyzer.py   # 市场环境分析
│   │   └── ...                    # 其他插件
│   └── wecom.py                  # 企业微信推送
├── ui/                          # UI模块
└── .github/workflows/            # GitHub Actions
```

## 配置说明

### LLM 模型配置

系统支持多种 LLM 模型，可在环境变量中配置：

```bash
# DeepSeek API（推荐用于新闻推理）
export DEEPSEEK_API_KEY="your_deepseek_api_key"
export LLM_MODEL="deepseek"

# Gemini API（可选）
export GEMINI_API_KEY="your_gemini_api_key"
```

### 新闻搜索服务

系统集成多个新闻源，支持全球财经新闻搜索：

1. **免费中文源**：东方财富、新浪财经、同花顺、雪球
2. **全球财经源**：华尔街日报、路透社、彭博、CNBC
3. **搜索引擎**：Bocha、Tavily、Brave Search、SerpAPI（需API Key）

### 企业微信推送

```yaml
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
```

## GitHub Secrets 配置

在 GitHub 仓库的 Settings > Secrets and variables > Actions 中添加以下 Secrets：

### 必需配置

| Secret 名称 | 描述 | 示例值 |
|------------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（用于新闻深度推理） | `sk-xxxxxxxxxxxxxxxxxxxxxxxx` |
| `LLM_MODEL` | LLM 模型类型 | `deepseek` 或 `gemini` |
| `WECOM_WEBHOOK_URL` | 企业微信 Webhook URL | `https://qyapi.weixin.qq.com/...` |

### 可选配置

| Secret 名称 | 描述 | 示例值 |
|------------|------|--------|
| `GEMINI_API_KEY` | Gemini API Key（可选） | `AIza...` |
| `BOCHA_API_KEY` | Bocha 搜索 API Key（可选） | `xxxxxxxx` |
| `TAVILY_API_KEY` | Tavily 搜索 API Key（可选） | `xxxxxxxx` |
| `TUSHARE_TOKEN` | Tushare API Token（可选） | `xxxxxxxx` |

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行方式

### 本地运行

```bash
# 使用 DeepSeek 进行分析
export DEEPSEEK_API_KEY="your_key"
export LLM_MODEL="deepseek"
python main.py

# 使用 Gemini 进行分析
export GEMINI_API_KEY="your_key"
export LLM_MODEL="gemini"
python main.py
```

### GitHub Actions

系统会自动在每个交易日下午 3:30 运行，也可以手动触发：

```yaml
env:
  DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
  LLM_MODEL: ${{ secrets.LLM_MODEL }}
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  WECOM_WEBHOOK_URL: ${{ secrets.WECOM_WEBHOOK_URL }}
```

## 分析输出示例

```
【LLM深度分析报告】

股票: 昊华科技 (600378)

【综合评级】⭐⭐⭐⭐ (4星) - 加权总分: 72.5

【打星理由】
四星评级，值得关注；
加权总分72.5分（LLM:70.2×50% + AI:75×30% + 技术:75×20%）；
LLM深度推理：新闻整体呈现利好情绪。
核心利好因素包括：
1) 公司发布业绩预增公告（净利润同比增长15%-25%），显示基本面稳健向好
2) 与大型企业签订战略合作协议，有利于未来技术研发和市场拓展
3) 公司主动回购股份，彰显管理层对未来发展的信心
关键事件：昊华科技发布2024年度业绩预增公告，预计净利润同比增长15%-25%
政策动向：工信部发布新能源行业扶持政策（税收优惠和补贴）
宏观信息：美联储维持利率不变，为A股提供相对稳定的外部金融环境

【操作建议】买入（置信度: 高）
【趋势预测】震荡上行
```

## 注意事项

1. **API Key 安全**：请不要在代码中硬编码 API Key，使用环境变量或 GitHub Secrets
2. **LLM 调用成本**：DeepSeek API 按 token 计费，请合理控制调用频率
3. **网络环境**：确保网络环境能够正常访问各数据源和 LLM 服务
4. **风险提示**：本系统仅供学习参考，不构成投资建议

## 许可证

Copyright (c) 2026 stock selector. All rights reserved.
