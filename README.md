# stock selector

基于插件流水线的 **A 股周 K 选股**：静态规则筛选 → **技术面 / 基本面 / AI** → **新闻搜索** → **LLM（推荐 Gemini 2.5 Flash）评星与打星理由** → **企业微信推送**。

## 流程说明（与你的使用方式对齐）

1. **选股**：按 `config.yaml` 中成交额、偏离、均线等规则得到当日候选池。  
2. **基本面**：ROE、PE、PB、营收增长等（AkShare 等数据源，失败时可能缺失）。  
3. **技术面**：MACD、KDJ、RSI 等，由技术分析插件写入，**LLM 插件固定排在后面**，保证能读到上述结果。  
4. **新闻**：东方财富 / 新浪 / 同花顺 / 雪球等免费源轮询；可选 `TAVILY_API_KEY` 等提高成功率。  
5. **LLM**：对新闻可做 JSON 结构化解读（Gemini 或 DeepSeek）；**打星理由**侧重「凭什么给这个星级」，**不在微信里展示长篇综合推理段落**（内部仍保留简要 `llm_recommendation_reason` 字段，供扩展用）。  
6. **评星**：LLM 侧为 **1～5 星**；**全市场五星最多 2 只**（按当日排序保留前 2，其余降为四星并改写理由前缀）。**AI 插件五星**同样最多 2 只（见 `selector.py` 原有逻辑）。  
7. **企业微信**：每条标的包含 **技术 / 基本面 / 消息面摘要、新闻摘要、打星理由**；五星票的 **打星理由** 允许更长篇幅（约 900 字内），以写清依据。

## 功能特性

- 多数据源轮换（东方财富、同花顺、长桥等）  
- **AI 分析插件**：技术指标情绪与星级（五星限 2）  
- **LLM 分析插件（增强版）**：多维度打分 + **充分打星理由**（五星分项说明技术、基本面、新闻/LLM 解读、政策、市场、宏观、AI 信号等）  
- 新闻搜索与关键词库（含政策/宏观关键词，见 `news_analyzer`）  
- 企业微信推送（`wecom.py`）  
- **GitHub Actions**：`ci.yml` 做安装/编译/导入自检；`screener.yml` 手动运行选股（需配置 Secrets）

## 配置要点

### 复制配置模板

仓库中 **不包含** `config.yaml`（已在 `.gitignore`），请复制：

```bash
cp config.yaml.template config.yaml
# 再按需编辑
```

### 使用 Gemini 2.5 Flash（推荐）

在 `config.yaml` 的 `llm_analysis` 下写 **扁平** 字段即可（也支持嵌套 `llm:`）：

```yaml
plugins:
  llm_analysis:
    enabled: true
    model: "gemini-2.5-flash"
    api_key: ""   # 或使用环境变量 GEMINI_API_KEY
```

或使用环境变量：

```bash
export GEMINI_API_KEY="你的Key"
export LLM_MODEL="gemini-2.5-flash"
python main.py
```

模型名须与 [Google AI 模型 ID](https://ai.google.dev/gemini-api/docs/models) 一致（**不要**使用带空格的展示名）。

### 企业微信

```yaml
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
```

## GitHub Actions Secrets

| Secret | 说明 |
|--------|------|
| `GEMINI_API_KEY` | 使用 Gemini 时必填 |
| `LLM_MODEL` | 如 `gemini-2.5-flash` |
| `DEEPSEEK_API_KEY` | 使用 DeepSeek 时 |
| `TAVILY_API_KEY` | 可选，增强新闻搜索 |
| `WECOM_WEBHOOK_URL` | 推送通知 |
| `TUSHARE_TOKEN` / `JQ_*` / `MAIRUI_TOKEN` | 数据源，按你实际使用的接口配置 |

未提交 `config.yaml` 时，程序使用 `load_config` 内置默认插件列表；**密钥以 Secrets / 环境变量为准**。

## 安装与运行

```bash
pip install -r requirements.txt
python main.py --config config.yaml
```

桌面 UI 使用 `run_ui.py`（依赖 PyQt6）；**服务器 / Actions 只需 `main.py`**。

## 静态分析与技能（code-analyzer）

若使用 **code-analyzer** 技能：其中提到的 `.claude/tools/.../analyzer.mjs` **本仓库未内置**。  
质量门禁以 **`.github/workflows/ci.yml`** 为主：`pip install` + `compileall` + 关键模块 import。

## 注意事项

1. **API Key** 勿写入仓库；用环境变量或 GitHub Secrets。  
2. **LLM 调用计费**：按各云厂商规则。  
3. **不构成投资建议**：输出仅供研究参考。

## 许可证

Copyright (c) 2026 stock selector. All rights reserved.
