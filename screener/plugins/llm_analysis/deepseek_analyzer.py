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

DEFAULT_DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


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
    investment_suggestion: str
    confidence: str
    success: bool
    error_message: Optional[str] = None


SYSTEM_PROMPT = """你是A股投资研究专家，擅长从新闻信息中提取投资机会和风险。

【分析框架 - 一步一步推理】

Step 1: 新闻情绪判断
- 识别新闻是利好、利空还是中性
- 给情绪强度打分（0-100，50为中性）

Step 2: 多维度影响分析
从以下5个维度分析（每个维度都要给出判断）：
1. 消息面：新闻事件本身对股价的直接影响
2. 政策面：国内政策（央行、证监会、国务院等）对行业/公司的影响
3. 宏观面：经济数据、GDP、CPI等对大盘的影响
4. 国际面：华尔街、美联储、白宫、中美关系等外部因素
5. 资金面：北向资金、主力资金流向、机构持仓变化

Step 3: 维度共振/矛盾判断
- 哪些维度形成共振（多个维度同一方向）？
- 哪些维度存在矛盾（多个维度方向相反）？
- 最重要的驱动因素是什么？

Step 4: 最终结论
综合以上推理，给出：
- sentiment_score: 0-100的情绪评分
- sentiment_reason: 情绪判断的理由（包含推理链条）
- key_events: 关键事件列表（最多3个）
- policy_impact: 政策影响分析
- macro_impact: 宏观影响分析
- investment_suggestion: 投资建议
- confidence: 置信度（高/中/低）

【重要约束】
- 不要编造新闻中不存在的信息
- 如果某维度信息不足，明确标注"信息不足"
- 投资建议要与其他分析结论一致，不能矛盾
- 输出必须是有效JSON格式

请开始分析。"""

SYNTHESIS_SYSTEM_PROMPT = """你是A股研究助理。根据用户给出的多维度要点（技术面、消息面、政策面、市场环境及可选的AI插件结论），用中文写一段可直接给投资者看的综合推理。

硬性要求：
- 总字数约 80～220 字，分段可有可无，语气专业克制。
- 不要编造材料中未出现的具体数字、新闻或政策名称。
- 若某维度明显信息不足，要明确写出「信息不足」，不要臆测。
- 结尾用一句话呼应用户给出的「操作建议标签」（如持有/观望/买入等），但不要与前面推理矛盾。"""

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
                 gemini_model_2: Optional[str] = None,
                 deepseek_api_url: Optional[str] = None,
                 gemini_api_url: Optional[str] = None):
        """
        初始化 LLM 新闻分析器

        Args:
            api_key: 主模型 API 密钥
            model: 主模型名称，如 deepseek-chat、gemini-2.5-flash 等
            fallback_model: 备用模型名称，如 deepseek-reasoner 等
            deepseek_api_key: DeepSeek 专用 API Key（用于 fallback）
            gemini_api_key_2: 第二个 Gemini API Key（降级备选）
            gemini_model_2: 第二个 Gemini 模型名称
            deepseek_api_url: DeepSeek API URL
            gemini_api_url: Gemini API URL
        """
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.model_name = model
        self.deepseek_api_url = deepseek_api_url or DEFAULT_DEEPSEEK_API_URL
        self.gemini_api_url = gemini_api_url or DEFAULT_GEMINI_API_URL
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
                              "model": self.fallback_model if self.fallback_model and "deepseek" not in self.model.lower() else "deepseek-chat"})
        elif self.deepseek_api_key and "deepseek" not in self.model.lower():
            providers.append({"name": "deepseek", "api_key": self.deepseek_api_key,
                              "model": self.fallback_model or "deepseek-chat"})
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

    def _synthesize_deepseek(self, user_prompt: str, max_tokens: int) -> Optional[str]:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}",
        }
        model = self.fallback_model if self.fallback_model else self.model_name
        if model in ("deepseek", "local", ""):
            model = "deepseek-chat"
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
            self.deepseek_api_url, headers=headers, json=payload, timeout=45
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
        base = self.gemini_api_url
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
            model = "deepseek-chat"
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
            model = "deepseek-chat"

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

        response = requests.post(self.deepseek_api_url, headers=headers, json=payload, timeout=30)

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

        url = f"{self.gemini_api_url}/{model}:generateContent?key={api_key}"

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
        """从字典构建 LLMAnalysisResult"""
        return LLMAnalysisResult(
            sentiment_score=data.get("sentiment_score", 50),
            sentiment_reason=data.get("sentiment_reason", ""),
            key_events=data.get("key_events", []),
            policy_impact=data.get("policy_impact", ""),
            macro_impact=data.get("macro_impact", ""),
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