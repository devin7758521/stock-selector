# stock selector

基于插件流水线的 **A 股周 K 选股**：静态规则筛选 → **技术面 / 基本面 / 消息面 / 政策面 / 市场环境** → **LLM 五维度分析** → **三类新闻汇总（个股/市场/宏观）** → **LLM 综合推理+成交量权重** → **企业微信推送**。

## 流程说明

```
Step 0: 启动通知
Step 1: 获取全市场股票（约5000只）
Step 2: 实时行情快照
Step 3: 静态过滤 → 候选池
Step 4: 并发处理
        ├── 技术面分析 (MACD/KDJ/RSI) 权重 20%
        ├── 基本面分析 (ROE/PE/营收)  权重 15%
        ├── 消息面分析 (个股/市场/宏观) 权重 30%
        ├── 政策面分析 (行业政策)      权重 15%
        └── 市场环境分析 (大盘/板块)   权重 20%
            ↓ LLM综合评分
            weighted_score = LLM×70% + AI×30%
            ↓ 星级 (0-5星)
            ↓ 缺数据时权重自动重分配
Step 5: 按星级+加权分排序
Step 5.5: LLM综合推理（对所有股票）
          inference_score = 加权分×85% + 推理质量分×10% + 成交量权重×5%
Step 6: 推送企业微信
```

## 核心特性

- **五维度 LLM 分析**：技术面、基本面、消息面、政策面、市场环境
- **三类新闻汇总**：个股新闻(7天/5条) + 市场新闻(3天/10条) + 宏观新闻(3天/5条)
- **动态权重分配**：某维度无数据时，权重自动重新分配，不拉低总分
- **推理评分优化**：成交量大的股票获得轻微加分（最高+5分）
- **多数据源轮询**：东方财富、同花顺、长桥、AkShare 等
- **多模型支持**：Gemini 2.5 Flash（主）+ DeepSeek Reasoner（备）
- **企业微信推送**：支持自定义推送模板

## 配置说明

### 配置文件

配置文件 `config.yaml` 不包含在仓库中（已在 `.gitignore`）。复制示例配置：

### LLM 模型配置

```yaml
plugins:
  llm_analysis:
    enabled: true
    primary_model: "gemini-2.5-flash"      # 主模型
    fallback_model: "deepseek-reasoner"    # 备用模型
    api_key: ""                            # 留空使用环境变量
```

### 企业微信

```yaml
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `GEMINI_API_KEY` | Gemini API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `TAVILY_API_KEY` | 新闻搜索（可选） |
| `WECOM_WEBHOOK_URL` | 推送通知 |
| `TUSHARE_TOKEN` | Tushare 数据源 |

## 安装与运行

```bash
pip install -r requirements.txt
python main.py
```

桌面 UI：`python run_ui.py`（需 PyQt6）

## GitHub Actions

| Workflow | 说明 |
|----------|------|
| `ci.yml` | 语法检查、依赖验证、导入测试 |
| `screener.yml` | 手动运行选股（需配置 Secrets） |

## 注意事项

1. **API Key** 勿写入仓库，使用环境变量或 GitHub Secrets
2. **不构成投资建议**：输出仅供研究参考
3. **数据完整性**：某维度数据缺失时，系统会自动调整权重分配

## 许可证

Copyright (c) 2026 stock selector. All rights reserved.
