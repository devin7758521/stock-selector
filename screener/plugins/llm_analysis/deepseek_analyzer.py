# -*- coding: utf-8 -*-
"""
LLM 新闻分析服务

支持 DeepSeek 和 Gemini 两大LLM进行新闻分析和推理。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
import json
import os
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger("stock_selector.llm.analyzer")

_gemini_lock = threading.Lock()
_gemini_last_call = 0.0
_gemini_consecutive_429 = 0
_GEMINI_MIN_INTERVAL = 4.0
_GEMINI_MAX_INTERVAL = 30.0
_GEMINI_429_THRESHOLD = 3

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_rate_limit_wait():
    """Gemini 请求前等待，确保不超过频率限制"""
    global _gemini_last_call, _gemini_consecutive_429
    with _gemini_lock:
        if _gemini_consecutive_429 >= _GEMINI_429_THRESHOLD:
            logger.warning(f"Gemini 连续{_gemini_consecutive_429}次429，后续请求直接跳过使用DeepSeek")
            return False
        elapsed = time.time() - _gemini_last_call
        interval = min(_GEMINI_MIN_INTERVAL * (1 + _gemini_consecutive_429 * 0.5), _GEMINI_MAX_INTERVAL)
        if elapsed < interval:
            wait = interval - elapsed
            logger.debug(f"Gemini 限速等待 {wait:.1f}s")
            time.sleep(wait)
        _gemini_last_call = time.time()
        return True


def _gemini_record_429():
    """记录 Gemini 429 错误"""
    global _gemini_consecutive_429
    with _gemini_lock:
        _gemini_consecutive_429 += 1
        logger.warning(f"Gemini 429累计: {_gemini_consecutive_429}次")


def _gemini_record_success():
    """记录 Gemini 成功调用，重置429计数"""
    global _gemini_consecutive_429
    with _gemini_lock:
        _gemini_consecutive_429 = 0


@dataclass
class LLMAnalysisResult:
    """LLM 分析结果"""
    sentiment_score: int
    sentiment_reason: str
    key_events: List[str]
    policy_impact: str
    macro_impact: str
    policy_score: int = 50
    macro_score: int = 50
    investment_suggestion: str = "观望"
    confidence: str = "中"
    success: bool = False
    error_message: Optional[str] = None


SYSTEM_PROMPT = """你是A股投资研究专家。从新闻中提取关键信息，输出JSON。

【规则】
1. 只提取新闻中明确提到的信息，禁止编造
2. 信息不足的维度标注"信息不足"
3. 忽略重复、广告、无实质内容的条目
4. 评分：0=极度利空，50=中性，100=极度利好

【输出JSON格式】
{
  "sentiment_score": 0-100,
  "sentiment_reason": "一句话总结核心逻辑（30字内）",
  "key_events": ["最多3个关键事件"],
  "policy_impact": "政策面影响（无则填'信息不足'）",
  "macro_impact": "宏观面影响（无则填'信息不足'）",
  "policy_score": 0-100,
  "macro_score": 0-100,
  "investment_suggestion": "买入/持有/减持/观望",
  "confidence": "高/中/低"
}"""

SYNTHESIS_SYSTEM_PROMPT = """你是A股研究助理。根据用户给出的多维度要点（技术面、消息面、政策面、市场环境及可选的AI插件结论），用中文写一段可直接给投资者看的综合推理。

硬性要求：
- 总字数约 80～220 字，分段可有可无，语气专业克制。
- 不要编造材料中未出现的具体数字、新闻或政策名称。
- 若某维度明显信息不足，要明确写出「信息不足」，不要臆测。
- 结尾用一句话呼应用户给出的「操作建议标签」（如持有/观望/买入等），但不要与前面推理矛盾。"""

TOP3_DEEP_SYSTEM_PROMPT = """你是A股资深投资分析师，拥有20年从业经验。请使用链式推理（Chain-of-Thought）方法，逐步展示你的完整分析过程。

【硬性要求】
1. 必须逐步推理，不能跳跃，每一步都要写出来
2. 只使用提供的材料，不得编造任何数据、新闻或政策
3. 【新闻正文】字段已包含完整新闻内容，请直接分析其中的具体事件，禁止回复"信息不足"或"未提供新闻内容"
4. 【政策面】【宏观面】字段若为空才写"信息不足"，若有内容则必须分析
5. 分析要具体，避免套话
6. 语气专业、客观、冷静，不煽动情绪"""

TOP3_DEEP_USER_PROMPT_TEMPLATE = """请对以下3只精选股票进行深度链式推理分析：

{stock1_data}

{stock2_data}

{stock3_data}

【分析要求】

═══════════════════════════════════
一、逐只深度分析（每只 300-500 字）
═══════════════════════════════════

对每只股票，按以下步骤逐步推理：

**{stock1_name}（{stock1_code}）**
1.1 技术面推理：
  - 解读 MACD/KDJ/RSI/均线 等指标的具体信号
  - 判断当前处于上升/下降/震荡的哪个阶段
  - 多空力量对比：多方理由 vs 空方理由

1.2 消息面推理：
  - 从新闻中提取最关键的 2-3 个信息点
  - 判断市场情绪偏向（恐慌/悲观/中性/乐观/狂热）
  - 消息的时效性和影响力评估

1.3 政策面推理：
  - 当前政策环境对该股/行业的影响方向
  - 政策力度：强刺激/温和支持/中性/收紧/强打压

1.4 市场环境推理：
  - 大盘环境和资金面判断
  - 板块联动效应：所属板块是否强势
  - 成交量是否配合

1.5 多空博弈综合：
  - 列出 3-5 个看多因素
  - 列出 3-5 个看空因素
  - 判断哪方占优，给出置信度

**{stock2_name}（{stock2_code}）**
（按同样步骤 2.1-2.5 分析）

**{stock3_name}（{stock3_code}）**
（按同样步骤 3.1-3.5 分析）

═══════════════════════════════════
二、横向对比分析
═══════════════════════════════════

4.1 三只股票的核心差异是什么？（行业/风格/驱动逻辑的不同）
4.2 哪只风险收益比最优？为什么？
4.3 如果只选一只，选谁？请给出有说服力的理由。

═══════════════════════════════════
三、最终排名和投资建议
═══════════════════════════════════

5.1 按投资价值排序（第1名/第2名/第3名），每只50字理由
5.2 对每只给出具体操作建议和仓位参考（激进/稳健/保守三种风格）
5.3 列出需要持续跟踪的关键信号（什么情况下应该改变判断）

═══════════════════════════════════
四、量化评分表
═══════════════════════════════════

用以下格式输出评分表（方便系统解析）：

| 排名 | 股票 | 技术面(25) | 消息面(25) | 政策面(15) | 市场环境(15) | 多空博弈(20) | 总分(100) |
|------|------|-----------|-----------|-----------|-------------|------------|----------|
|  1   | XXX  |    XX     |    XX     |    XX     |     XX      |     XX     |    XX    |
|  2   | XXX  |    XX     |    XX     |    XX     |     XX      |     XX     |    XX    |
|  3   | XXX  |    XX     |    XX     |    XX     |     XX      |     XX     |    XX    |

注意：评分表必须严格按 Markdown 表格格式输出，总分必须是各项之和。"""

DEEPSEEK_V4_PRO_URL = "https://api.deepseek.com/v1/chat/completions"
DEEP_ANALYSIS_MODEL = "deepseek-v4-pro"


NEWS_SUMMARIZE_PROMPT = """你是一个新闻聚合助手。请对以下三类新闻进行汇总，生成一段简洁的中文摘要（100-200字），供后续投资分析使用。

【新闻分类】
一、个股新闻：该股票自身的新闻、公告、业绩等
二、市场新闻：市场整体的财经新闻、资金动向等
三、宏观政策新闻：宏观经济、政策导向、国际局势等

【汇总要求】
1. 识别各类新闻的核心要点（各20-50字）
2. 标注每类新闻的情绪倾向：利好/利空/中性
3. 如果某类新闻为空或不足，明确标注"信息不足"
4. 汇总要体现三类新闻的关联性和整体情绪判断

请按以下格式输出：

【个股新闻汇总】
（汇总内容，20-50字）
情绪：利好/利空/中性

【市场新闻汇总】
（汇总内容，20-50字）
情绪：利好/利空/中性

【宏观政策新闻汇总】
（汇总内容，20-50字）
情绪：利好/利空/中性

【整体情绪判断】
（基于三类新闻的整体情绪判断，20-50字）"""


class LLMNewsAnalyzer:
    """
    LLM 新闻分析器

    支持 DeepSeek 和 Gemini 两大LLM进行新闻分析。
    借鉴 quant-feishu 的三级降级轮换机制：
    Gemini(#1) → Gemini(#2) → DeepSeek
    """

    def __init__(self, api_key: str, model: str = "deepseek",
                 fallback_model: Optional[str] = None,
                 deepseek_api_key: Optional[str] = None,
                 gemini_api_key_2: Optional[str] = None,
                 gemini_model_2: Optional[str] = None):
        """
        初始化 LLM 新闻分析器

        Args:
            api_key: 主模型 API 密钥
            model: 主模型名称，如 deepseek-v4-flash、gemini-2.5-flash 等
            fallback_model: 备用模型名称，如 deepseek-v4-flash 等
            deepseek_api_key: DeepSeek 专用 API Key（用于 fallback）
            gemini_api_key_2: 第二个 Gemini API Key（降级备选）
            gemini_model_2: 第二个 Gemini 模型名称
        """
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.model_name = model
        if deepseek_api_key and deepseek_api_key.strip():
            self.deepseek_api_key = deepseek_api_key
        else:
            self.deepseek_api_key = api_key
            if "gemini" in model.lower() and self.deepseek_api_key:
                logger.warning("DEEPSEEK_API_KEY 未设置，fallback 将使用主模型 API Key，可能导致认证失败！")

        # 第二 Gemini Key（三级降级）
        self.gemini_api_key_2 = gemini_api_key_2 or os.environ.get("GEMINI_API_KEY_2", "")
        self.gemini_model_2 = gemini_model_2 or os.environ.get("GEMINI_MODEL_2", "gemini-2.5-flash")

        # 全局轮换索引
        self._provider_idx = 0
        self._providers = self._build_providers()

    def _build_providers(self) -> list:
        """构建 AI 提供商降级链：Gemini(#1) → Gemini(#2) → DeepSeek"""
        providers = []
        if "gemini" in self.model.lower() and self.api_key:
            providers.append({"name": "gemini", "api_key": self.api_key, "model": self.model_name})
        if self.gemini_api_key_2:
            providers.append({"name": "gemini2", "api_key": self.gemini_api_key_2, "model": self.gemini_model_2})
        if self.deepseek_api_key and self.deepseek_api_key != self.api_key:
            providers.append({"name": "deepseek", "api_key": self.deepseek_api_key,
                              "model": self.fallback_model if self.fallback_model and "deepseek" not in self.model.lower() else "deepseek-v4-flash"})
        elif self.deepseek_api_key and "deepseek" not in self.model.lower():
            providers.append({"name": "deepseek", "api_key": self.deepseek_api_key,
                              "model": self.fallback_model or "deepseek-v4-flash"})
        if not providers and self.api_key:
            providers.append({"name": "deepseek" if "deepseek" in self.model.lower() else "gemini",
                              "api_key": self.api_key, "model": self.model_name})
        logger.info(f"AI Provider 降级链: {[p['name'] for p in providers]}")
        return providers

    def analyze(self, news_context: str, stock_name: str,
                code: str, industry: Optional[str] = None) -> LLMAnalysisResult:
        """
        分析新闻内容（三级降级轮换：Gemini → Gemini2 → DeepSeek）

        Args:
            news_context: 新闻上下文
            stock_name: 股票名称
            code: 股票代码
            industry: 所属行业（可选）

        Returns:
            LLMAnalysisResult 分析结果
        """
        if not news_context or not news_context.strip():
            return LLMAnalysisResult(
                sentiment_score=50,
                sentiment_reason="无新闻信息",
                key_events=[],
                policy_impact="无政策相关信息",
                macro_impact="无宏观相关信息",
                investment_suggestion="观望",
                confidence="低",
                success=False,
                error_message="无新闻内容"
            )

        # 三级降级轮换
        tried = []
        for attempt in range(len(self._providers)):
            idx = (self._provider_idx + attempt) % len(self._providers)
            p = self._providers[idx]
            if p["name"] in tried:
                continue
            tried.append(p["name"])

            try:
                if p["name"] == "gemini" or p["name"] == "gemini2":
                    result = self._analyze_with_gemini_key(
                        news_context, stock_name, code, industry,
                        api_key=p["api_key"], model=p["model"]
                    )
                else:
                    result = self._analyze_with_deepseek_key(
                        news_context, stock_name, code, industry,
                        api_key=p["api_key"], model=p["model"]
                    )

                if result.success and not result.error_message:
                    self._provider_idx = (idx + 1) % len(self._providers)
                    logger.info(f"AI 分析成功(provider={p['name']}), 下次轮换到 idx={self._provider_idx}")
                    return result

                # 429/503 等可降级错误
                err = result.error_message or ""
                if "429" in err or "503" in err or "quota" in err.lower() or "限流" in err:
                    logger.warning(f"Provider {p['name']} 失败({err})，降级到下一个")
                    continue

                # 其他错误也尝试下一个
                logger.warning(f"Provider {p['name']} 分析失败: {err}")
                continue

            except Exception as e:
                logger.warning(f"Provider {p['name']} 异常: {e}")
                continue

        # 全部失败
        logger.error(f"所有 AI Provider 分析失败 (tried: {tried})")
        return LLMAnalysisResult(
            sentiment_score=50,
            sentiment_reason=f"分析失败(tried: {tried})",
            key_events=[],
            policy_impact="分析异常",
            macro_impact="分析异常",
            investment_suggestion="观望",
            confidence="低",
            success=False,
            error_message=f"所有 Provider 失败: {tried}"
        )

    def synthesize(self, user_prompt: str, max_tokens: int = 700) -> Optional[str]:
        """
        通用文本综合（多维度推理、摘要等），返回模型原文；失败返回 None。
        """
        if not self.api_key or not str(self.api_key).strip():
            return None
        if not user_prompt or not user_prompt.strip():
            return None
        try:
            if "gemini" in self.model.lower():
                result = self._synthesize_gemini(user_prompt, max_tokens)
                if result is None:
                    logger.warning("Gemini synthesize 失败，自动切换到 DeepSeek")
                    return self._synthesize_deepseek(user_prompt, max_tokens)
                return result
            return self._synthesize_deepseek(user_prompt, max_tokens)
        except Exception as e:
            logger.warning(f"LLM 综合推理异常: {e}", exc_info=True)
            return None

    def summarize_news(self, stock_news: Optional[str], market_news: Optional[str],
                     macro_news: Optional[str]) -> Optional[str]:
        """
        汇总三类新闻（个股/市场/宏观）

        Args:
            stock_news: 个股新闻上下文
            market_news: 市场新闻上下文
            macro_news: 宏观新闻上下文

        Returns:
            汇总后的新闻摘要字符串，失败返回None
        """
        parts = []
        if stock_news:
            parts.append(f"【个股新闻】\n{stock_news}")
        if market_news:
            parts.append(f"【市场新闻】\n{market_news}")
        if macro_news:
            parts.append(f"【宏观新闻】\n{macro_news}")

        if not parts:
            return None

        user_prompt = "\n\n".join(parts)
        return self.synthesize(f"{NEWS_SUMMARIZE_PROMPT}\n\n{user_prompt}", max_tokens=800)

    def deep_analyze_top3(self, stock1: Dict[str, Any], stock2: Dict[str, Any],
                          stock3: Dict[str, Any]) -> Optional[str]:
        """
        对 Top3 股票进行深度链式推理分析，使用 DeepSeek V4 Pro。

        每只股票的数据应包含：
        - name, code
        - llm_stars, llm_weighted_score
        - llm_technical_detail, llm_news_detail, llm_policy_detail, llm_market_detail
        - news_headlines, policy_info, macro_info, llm_news_reason
        - ai_buy_signal, ai_signal_score（可选）

        Returns:
            深度分析文本，失败返回 None
        """

        def _format_stock(r: Dict[str, Any], label: str) -> str:
            stars = r.get("llm_stars", 0) or 0
            star_icon = "⭐" * stars if stars > 0 else "无星"
            ws = r.get("llm_weighted_score", r.get("weighted_score", 50))
            advice = r.get("llm_operation_advice", "N/A")

            lines = [
                f"{'='*50}",
                f"【{label}】{r.get('name', '?')}（{r.get('code', '?')}）",
                f"评级：{star_icon}  |  加权分：{ws:.1f}  |  建议：{advice}",
                "",
            ]

            # ── 技术面（详细指标） ──
            tech = r.get("llm_technical_detail") or r.get("technical_analysis_detail") or ""
            if tech and tech != "N/A":
                lines.append(f"【技术面】{tech}")
            # 补充原始技术分析数据
            ta = r.get("technical_analysis", {})
            if isinstance(ta, dict) and ta:
                macd = ta.get("macd", {})
                kdj = ta.get("kdj", {})
                rsi_val = ta.get("rsi", "")
                if macd or kdj:
                    parts = []
                    if macd:
                        parts.append(f"MACD: value={macd.get('value','?')}, histogram={macd.get('histogram','?')}")
                    if kdj:
                        parts.append(f"KDJ: K={kdj.get('k','?')}, D={kdj.get('d','?')}, J={kdj.get('j','?')}")
                    if rsi_val:
                        parts.append(f"RSI: {rsi_val}")
                    lines.append(f"  原始数据：{'；'.join(parts)}")

            # ── 新闻正文（关键！之前丢失了） ──
            news_full = r.get("llm_news_summary") or ""
            if news_full and len(news_full) > 20:
                # 限制长度避免 token 爆炸，但保留足够上下文
                news_trimmed = news_full[:2000]
                lines.append(f"【新闻正文】{news_trimmed}")

            # ── LLM 新闻分析结果 ──
            llm_reason = r.get("llm_news_reason") or ""
            if llm_reason:
                lines.append(f"【LLM新闻推理】{llm_reason}")

            headlines = r.get("news_headlines", "")
            if headlines:
                lines.append(f"【关键事件】{headlines}")

            # ── 政策面 ──
            pi = r.get("policy_info", "")
            if pi and pi not in ("信息不足", "", "N/A", "无", "政策面分析已由LLM完成"):
                lines.append(f"【政策面】{pi}")

            # ── 宏观面 ──
            mi = r.get("macro_info", "")
            if mi and mi not in ("信息不足", "", "N/A", "无"):
                lines.append(f"【宏观面】{mi}")

            # ── 市场环境 ──
            market_d = r.get("llm_market_detail") or r.get("market_environment_analysis") or ""
            if market_d and market_d != "N/A":
                lines.append(f"【市场环境】{market_d}")

            # ── AI 分析 ──
            ai_signal = r.get("ai_buy_signal", "")
            ai_score = r.get("ai_signal_score", 50)
            ai_reason = r.get("ai_rating_reason", "")
            if ai_signal and ai_signal != "N/A":
                line = f"【AI信号】{ai_signal}（评分{ai_score}）"
                if ai_reason and ai_reason != "N/A":
                    line += f"  理由：{ai_reason}"
                lines.append(line)

            # ── 综合推理（Step 5.5 的 synthesis） ──
            rec = r.get("llm_recommendation_reason") or r.get("recommendation_reason", "")
            if rec:
                lines.append(f"【综合推理(Step5.5)】{rec}")

            # ── 量能/成交额 ──
            vol_dev = r.get("vol_deviation_pct", None)
            daily_amt = r.get("daily_amount_yi", None)
            if vol_dev is not None or daily_amt is not None:
                vol_parts = []
                if vol_dev is not None:
                    vol_parts.append(f"量能偏离：{vol_dev}%")
                if daily_amt is not None:
                    vol_parts.append(f"日成交额：{daily_amt}亿")
                lines.append(f"【量能数据】{'；'.join(vol_parts)}")

            return "\n".join(lines)

        stock1_data = _format_stock(stock1, "股票A")
        stock2_data = _format_stock(stock2, "股票B")
        stock3_data = _format_stock(stock3, "股票C")

        user_prompt = TOP3_DEEP_USER_PROMPT_TEMPLATE.format(
            stock1_data=stock1_data,
            stock2_data=stock2_data,
            stock3_data=stock3_data,
            stock1_name=stock1.get("name", "?"),
            stock1_code=stock1.get("code", "?"),
            stock2_name=stock2.get("name", "?"),
            stock2_code=stock2.get("code", "?"),
            stock3_name=stock3.get("name", "?"),
            stock3_code=stock3.get("code", "?"),
        )

        # 用环境变量可切换模型
        deep_model = os.environ.get("DEEP_ANALYSIS_MODEL", DEEP_ANALYSIS_MODEL)
        logger.info(f"Top3深度分析开始，使用模型: {deep_model}")

        # 三级降级：先尝试 DeepSeek Pro
        results = []
        providers = []
        if self.deepseek_api_key:
            providers.append(("deepseek", self.deepseek_api_key, deep_model))
        if self.api_key and self.api_key != self.deepseek_api_key:
            providers.append(("deepseek", self.api_key, deep_model))
        # 最后一招：用主模型（Gemini）的 synthesize
        if self.api_key and "gemini" in self.model.lower():
            providers.append(("gemini_synth", self.api_key, self.model_name))

        for pname, pkey, pmodel in providers:
            try:
                if pname in ("deepseek",):
                    text = self._call_deepseek_raw(
                        system_prompt=TOP3_DEEP_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        api_key=pkey,
                        model=pmodel,
                        max_tokens=8192,
                        temperature=0.4,
                    )
                    if text and len(text) > 200:
                        logger.info(f"Top3深度分析成功(provider={pname}, model={pmodel}), {len(text)}字")
                        return text
                    results.append((pname, text))
                else:
                    text = self._synthesize_gemini(user_prompt, max_tokens=8192)
                    if text and len(text) > 200:
                        logger.info(f"Top3深度分析成功(provider=gemini_synth), {len(text)}字")
                        return text
                    results.append(("gemini_synth", text))
            except Exception as e:
                logger.warning(f"Top3深度分析 provider={pname} 失败: {e}")
                results.append((pname, None))

        logger.error(f"Top3深度分析全部失败: {results}")
        return None

    def _call_deepseek_raw(self, system_prompt: str, user_prompt: str,
                           api_key: str, model: str,
                           max_tokens: int = 4096,
                           temperature: float = 0.4) -> Optional[str]:
        """直接调用 DeepSeek API，不使用 synthesize 的 fallback 逻辑"""
        import requests

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        try:
            resp = requests.post(DEEPSEEK_V4_PRO_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code != 200:
                logger.error(f"DeepSeek raw API 失败: {resp.status_code} - {resp.text[:300]}")
                return None
            content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else None
        except Exception as e:
            logger.error(f"DeepSeek raw API 异常: {e}")
            return None

    def _synthesize_deepseek(self, user_prompt: str, max_tokens: int) -> Optional[str]:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}",
        }
        model = self.fallback_model if self.fallback_model else self.model_name
        if model in ("deepseek", "local", ""):
            model = "deepseek-v4-flash"
        logger.info(f"使用 DeepSeek synthesize 模型: {model}")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.35,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            DEEPSEEK_API_URL, headers=headers, json=payload, timeout=45
        )
        if response.status_code != 200:
            logger.error(
                f"DeepSeek 综合推理 API 失败: {response.status_code} - {response.text[:500]}"
            )
            return None
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        text = (content or "").strip()
        return text if text else None

    def _get_gemini_url(self) -> str:
        # 统一使用 v1beta 端点，v2beta 已废弃
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        return f"{base}/{self.model_name}:generateContent"

    def _synthesize_gemini(self, user_prompt: str, max_tokens: int) -> Optional[str]:
        if not _gemini_rate_limit_wait():
            return None

        import requests

        url = f"{self._get_gemini_url()}?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": user_prompt}
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": SYNTHESIS_SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": max_tokens,
            },
        }

        for retry in range(3):
            try:
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=45,
                )
                if response.status_code == 429:
                    _gemini_record_429()
                    wait = min(4 * (2 ** retry), 30)
                    logger.warning(f"Gemini synthesize 429，等待{wait}s后重试({retry+1}/3)")
                    time.sleep(wait)
                    continue
                if response.status_code != 200:
                    logger.error(f"Gemini 综合推理 API 失败: {response.status_code} - {response.text[:500]}")
                    return None
                _gemini_record_success()
                result = response.json()
                candidates = result.get("candidates", [])
                if not candidates:
                    return None
                candidate = candidates[0]
                if candidate.get("finishReason") == "SAFETY":
                    return None
                content = (
                    candidate.get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                text = (content or "").strip()
                return text if text else None
            except requests.exceptions.Timeout:
                logger.warning(f"Gemini synthesize 超时，重试({retry+1}/3)")
                if retry < 2:
                    time.sleep(2)
                continue
            except Exception as e:
                logger.error(f"Gemini synthesize 异常: {e}")
                break
        return None

    def _analyze_with_deepseek(self, news_context: str, stock_name: str,
                               code: str, industry: Optional[str]) -> LLMAnalysisResult:
        """使用 DeepSeek 分析（默认参数）"""
        model = self.fallback_model if self.fallback_model else self.model_name
        if model in ("deepseek", "local", ""):
            model = "deepseek-v4-flash"
        return self._analyze_with_deepseek_key(news_context, stock_name, code, industry,
                                                api_key=self.deepseek_api_key, model=model)

    def _analyze_with_deepseek_key(self, news_context: str, stock_name: str,
                                    code: str, industry: Optional[str],
                                    api_key: str, model: str) -> LLMAnalysisResult:
        """使用 DeepSeek 分析（参数化 Key/Model）"""
        import requests

        industry_context = f"，所属行业：{industry}" if industry else ""

        user_prompt = f"""分析以下关于 {stock_name}（{code}）{industry_context} 的新闻：

{news_context}

请进行深度分析并输出JSON格式结果。"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        if model in ("deepseek", "local", ""):
            model = "deepseek-v4-flash"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }

        logger.info(f"使用 DeepSeek 模型: {model}")
        if not api_key:
            return LLMAnalysisResult(
                sentiment_score=50, sentiment_reason="DeepSeek API Key 未设置",
                key_events=[], policy_impact="无", macro_impact="无",
                investment_suggestion="观望", confidence="低",
                success=False, error_message="DeepSeek API Key 未设置"
            )

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            logger.error(f"DeepSeek API 请求失败: {response.status_code} - {response.text}")
            return LLMAnalysisResult(
                sentiment_score=50, sentiment_reason="API请求失败",
                key_events=[], policy_impact="无法分析", macro_impact="无法分析",
                investment_suggestion="观望", confidence="低",
                success=False, error_message=f"API错误: {response.status_code}"
            )

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        logger.info(f"DeepSeek 分析成功: {stock_name} ({code})")
        return self._parse_response(content)

    def _analyze_with_gemini(self, news_context: str, stock_name: str,
                             code: str, industry: Optional[str]) -> LLMAnalysisResult:
        """使用 Gemini 分析（默认参数）"""
        return self._analyze_with_gemini_key(news_context, stock_name, code, industry,
                                              api_key=self.api_key, model=self.model_name)

    def _analyze_with_gemini_key(self, news_context: str, stock_name: str,
                                  code: str, industry: Optional[str],
                                  api_key: str, model: str) -> LLMAnalysisResult:
        """使用 Gemini 分析（参数化 Key/Model，支持多 Key 轮换）"""
        if not _gemini_rate_limit_wait():
            return LLMAnalysisResult(
                sentiment_score=50,
                sentiment_reason="Gemini限流，跳过",
                key_events=[],
                policy_impact="无法分析",
                macro_impact="无法分析",
                investment_suggestion="观望",
                confidence="低",
                success=False,
                error_message="Gemini 429限流"
            )

        import requests

        industry_context = f"，所属行业：{industry}" if industry else ""

        user_prompt = f"""分析以下关于 {stock_name}（{code}）{industry_context} 的新闻：

{news_context}

请进行深度分析并输出JSON格式结果。"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": user_prompt}]
            }],
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        }

        headers = {"Content-Type": "application/json"}

        for retry in range(3):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)

                if response.status_code == 429:
                    _gemini_record_429()
                    wait = min(4 * (2 ** retry), 30)
                    logger.warning(f"Gemini 429，等待{wait}s后重试({retry+1}/3)")
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    logger.error(f"Gemini API 请求失败: {response.status_code} - {response.text[:500]}")
                    return LLMAnalysisResult(
                        sentiment_score=50, sentiment_reason="API请求失败",
                        key_events=[], policy_impact="无法分析", macro_impact="无法分析",
                        investment_suggestion="观望", confidence="低",
                        success=False, error_message=f"API错误: {response.status_code}"
                    )

                _gemini_record_success()
                result = response.json()
                candidates = result.get("candidates", [])
                if not candidates:
                    return LLMAnalysisResult(
                        sentiment_score=50, sentiment_reason="Gemini 返回空结果",
                        key_events=[], policy_impact="无法分析", macro_impact="无法分析",
                        investment_suggestion="观望", confidence="低",
                        success=False, error_message="Gemini 返回空 candidates"
                    )
                candidate = candidates[0]
                if candidate.get("finishReason") == "SAFETY":
                    return LLMAnalysisResult(
                        sentiment_score=50, sentiment_reason="内容被安全过滤拦截",
                        key_events=[], policy_impact="无法分析", macro_impact="无法分析",
                        investment_suggestion="观望", confidence="低",
                        success=False, error_message="Gemini 安全过滤拦截"
                    )
                content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
                logger.info(f"Gemini 分析成功: {stock_name} ({code}) [model={model}]")
                return self._parse_response(content)

            except requests.exceptions.Timeout:
                logger.warning(f"Gemini 超时，重试({retry+1}/3)")
                if retry < 2:
                    time.sleep(2)
                continue
            except Exception as e:
                logger.error(f"Gemini 异常: {e}")
                break

        return LLMAnalysisResult(
            sentiment_score=50, sentiment_reason="Gemini重试耗尽",
            key_events=[], policy_impact="无法分析", macro_impact="无法分析",
            investment_suggestion="观望", confidence="低",
            success=False, error_message="Gemini重试耗尽"
        )

    def _parse_response(self, content: str) -> LLMAnalysisResult:
        """三级 JSON 解析（借鉴 quant-feishu）：
        1. 直接 json.loads
        2. 提取 ```json ... ``` 代码块
        3. 正则逐字段提取
        """
        # 级别1: 直接解析
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
                return self._build_result_from_dict(data)
        except json.JSONDecodeError:
            pass

        # 级别2: 提取 ```json ... ``` 代码块
        import re
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                return self._build_result_from_dict(data)
            except json.JSONDecodeError:
                pass

        # 级别3: 正则逐字段提取
        parsed = {}
        m_score = re.search(r'"sentiment_score"\s*:\s*(\d+)', content)
        if m_score:
            parsed["sentiment_score"] = int(m_score.group(1))
        m_reason = re.search(r'"sentiment_reason"\s*:\s*"(.+?)"', content, re.DOTALL)
        if m_reason:
            parsed["sentiment_reason"] = m_reason.group(1)[:200]
        m_events = re.findall(r'"key_events"\s*:\s*\[(.*?)\]', content, re.DOTALL)
        if m_events:
            items = re.findall(r'"([^"]+)"', m_events[0])
            parsed["key_events"] = items[:3]
        m_policy = re.search(r'"policy_impact"\s*:\s*"(.+?)"', content, re.DOTALL)
        if m_policy:
            parsed["policy_impact"] = m_policy.group(1)[:200]
        m_macro = re.search(r'"macro_impact"\s*:\s*"(.+?)"', content, re.DOTALL)
        if m_macro:
            parsed["macro_impact"] = m_macro.group(1)[:200]
        m_policy_score = re.search(r'"policy_score"\s*:\s*(\d+)', content)
        if m_policy_score:
            parsed["policy_score"] = int(m_policy_score.group(1))
        m_macro_score = re.search(r'"macro_score"\s*:\s*(\d+)', content)
        if m_macro_score:
            parsed["macro_score"] = int(m_macro_score.group(1))
        m_suggest = re.search(r'"investment_suggestion"\s*:\s*"(.+?)"', content, re.DOTALL)
        if m_suggest:
            parsed["investment_suggestion"] = m_suggest.group(1)[:50]
        m_conf = re.search(r'"confidence"\s*:\s*"(.+?)"', content)
        if m_conf:
            parsed["confidence"] = m_conf.group(1)

        if parsed.get("sentiment_score") is not None:
            parsed.setdefault("sentiment_reason", "推理提取成功")
            parsed.setdefault("key_events", [])
            parsed.setdefault("policy_impact", "")
            parsed.setdefault("macro_impact", "")
            parsed.setdefault("investment_suggestion", "观望")
            parsed.setdefault("confidence", "中")
            return self._build_result_from_dict(parsed)

        # 全部失败：降级到旧 fallback
        logger.warning("三级 JSON 解析均失败，使用文本 fallback")
        return self._fallback_parse(content)

    def _build_result_from_dict(self, data: dict) -> LLMAnalysisResult:
        return LLMAnalysisResult(
            sentiment_score=data.get("sentiment_score", 50),
            sentiment_reason=data.get("sentiment_reason", ""),
            key_events=data.get("key_events", []),
            policy_impact=data.get("policy_impact", ""),
            macro_impact=data.get("macro_impact", ""),
            policy_score=data.get("policy_score", 50),
            macro_score=data.get("macro_score", 50),
            investment_suggestion=data.get("investment_suggestion", "观望"),
            confidence=data.get("confidence", "中"),
            success=True
        )

    def _fallback_parse(self, content: str) -> LLMAnalysisResult:
        """备用解析方法（当 JSON 解析失败时）"""
        sentiment_score = 50
        sentiment_reason = ""
        key_events = []
        policy_impact = ""
        macro_impact = ""
        investment_suggestion = "观望"
        confidence = "中"

        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if 'sentiment_score' in line.lower() or '情绪评分' in line:
                try:
                    num = ''.join(filter(str.isdigit, line.split(':')[-1]))
                    if num:
                        sentiment_score = max(0, min(100, int(num)))
                except:
                    pass
            elif 'key_events' in line.lower() or '关键事件' in line:
                key_events.append(line)
            elif 'policy' in line.lower() or '政策' in line:
                policy_impact = line
            elif 'macro' in line.lower() or '宏观' in line:
                macro_impact = line
            elif 'suggestion' in line.lower() or '建议' in line:
                investment_suggestion = line.split('：')[-1] if '：' in line else line

        return LLMAnalysisResult(
            sentiment_score=sentiment_score,
            sentiment_reason=content[:200],
            key_events=key_events[:3],
            policy_impact=policy_impact[:100],
            macro_impact=macro_impact[:100],
            investment_suggestion=investment_suggestion,
            confidence=confidence,
            success=True
        )


DeepSeekNewsAnalyzer = LLMNewsAnalyzer