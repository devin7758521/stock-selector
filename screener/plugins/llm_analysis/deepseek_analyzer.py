# -*- coding: utf-8 -*-
"""
LLM 新闻分析服务

支持 DeepSeek 和 Gemini 两大LLM进行新闻分析和推理。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger("stock_selector.llm.analyzer")

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


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


SYSTEM_PROMPT = """你是一位专业的A股投资分析师，擅长从新闻中提取有价值的信息并进行投资分析。

分析维度：
1. 新闻情绪判断（利好/利空/中性）及理由
2. 关键事件识别（对股价有影响的事件）
3. 政策影响分析（国内政策对该股票/行业的影响）
4. 宏观影响分析（全球经济形势对该股票的影响）
5. 国际局势影响（华尔街、白宫、美联储、特朗普等美国因素对A股的影响）
6. 投资建议（综合以上因素给出建议）

特别关注：
- 华尔街动态：美股三大指数涨跌、做空/做多情绪、对冲基金动向
- 白宫与国会：美国政府政策变动、制裁关税、科技战相关
- 美联储决策：加息降息、通胀就业数据、缩表扩表
- 地缘政治：俄乌冲突、中东局势、中美关系对A股的影响
- 避险情绪：VIX恐慌指数、黄金美元走势、资金流向

输出格式要求：
- sentiment_score: 0-100的情绪评分，50为中性
- sentiment_reason: 情绪判断的详细理由
- key_events: 关键事件列表（最多3个）
- policy_impact: 政策影响分析（1-2句话）
- macro_impact: 宏观影响分析（1-2句话）
- investment_suggestion: 投资建议（1句话）
- confidence: 置信度（高/中/低）

请用JSON格式输出。"""

SYNTHESIS_SYSTEM_PROMPT = """你是A股研究助理。根据用户给出的多维度要点（技术面、基本面、消息面、政策面、市场环境及可选的AI插件结论），用中文写一段可直接给投资者看的综合推理。

硬性要求：
- 总字数约 80～220 字，分段可有可无，语气专业克制。
- 不要编造材料中未出现的具体数字、新闻或政策名称。
- 若某维度明显信息不足，要明确写出「信息不足」，不要臆测。
- 结尾用一句话呼应用户给出的「操作建议标签」（如持有/观望/买入等），但不要与前面推理矛盾。"""


class LLMNewsAnalyzer:
    """
    LLM 新闻分析器

    支持 DeepSeek 和 Gemini 两大LLM进行新闻分析。
    """

    def __init__(self, api_key: str, model: str = "deepseek"):
        """
        初始化 LLM 新闻分析器

        Args:
            api_key: API 密钥
            model: 模型名称，如 deepseek-chat、gemini-1.5-flash、gemini-2.0-flash 等
        """
        self.api_key = api_key
        self.model = model
        self.model_name = model

    def analyze(self, news_context: str, stock_name: str,
                code: str, industry: Optional[str] = None) -> LLMAnalysisResult:
        """
        分析新闻内容

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

        try:
            if "gemini" in self.model.lower():
                return self._analyze_with_gemini(news_context, stock_name, code, industry)
            else:
                return self._analyze_with_deepseek(news_context, stock_name, code, industry)
        except Exception as e:
            logger.error(f"LLM 分析异常: {e}", exc_info=True)
            return LLMAnalysisResult(
                sentiment_score=50,
                sentiment_reason=f"分析异常: {str(e)}",
                key_events=[],
                policy_impact="分析异常",
                macro_impact="分析异常",
                investment_suggestion="观望",
                confidence="低",
                success=False,
                error_message=str(e)
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
                return self._synthesize_gemini(user_prompt, max_tokens)
            return self._synthesize_deepseek(user_prompt, max_tokens)
        except Exception as e:
            logger.warning(f"LLM 综合推理异常: {e}", exc_info=True)
            return None

    def _synthesize_deepseek(self, user_prompt: str, max_tokens: int) -> Optional[str]:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        model = self.model_name
        if model in ("deepseek", "local", ""):
            model = "deepseek-chat"
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

    def _synthesize_gemini(self, user_prompt: str, max_tokens: int) -> Optional[str]:
        import requests

        url = f"{GEMINI_API_URL}/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYNTHESIS_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": max_tokens,
            },
        }
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )
        if response.status_code != 200:
            logger.error(
                f"Gemini 综合推理 API 失败: {response.status_code} - {response.text[:500]}"
            )
            return None
        content = (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        text = (content or "").strip()
        return text if text else None

    def _analyze_with_deepseek(self, news_context: str, stock_name: str,
                               code: str, industry: Optional[str]) -> LLMAnalysisResult:
        """使用 DeepSeek 分析"""
        import requests

        industry_context = f"，所属行业：{industry}" if industry else ""

        user_prompt = f"""分析以下关于 {stock_name}（{code}）{industry_context} 的新闻：

{news_context}

请进行深度分析并输出JSON格式结果。"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }

        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"DeepSeek API 请求失败: {response.status_code} - {response.text}")
            return LLMAnalysisResult(
                sentiment_score=50,
                sentiment_reason="API请求失败",
                key_events=[],
                policy_impact="无法分析",
                macro_impact="无法分析",
                investment_suggestion="观望",
                confidence="低",
                success=False,
                error_message=f"API错误: {response.status_code}"
            )

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        logger.info(f"DeepSeek 分析成功: {stock_name} ({code})")

        return self._parse_response(content)

    def _analyze_with_gemini(self, news_context: str, stock_name: str,
                             code: str, industry: Optional[str]) -> LLMAnalysisResult:
        """使用 Gemini 分析"""
        import requests

        industry_context = f"，所属行业：{industry}" if industry else ""

        user_prompt = f"""分析以下关于 {stock_name}（{code}）{industry_context} 的新闻：

{news_context}

请进行深度分析并输出JSON格式结果。"""

        url = f"{GEMINI_API_URL}/{self.model_name}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{
                    "text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            logger.error(f"Gemini API 请求失败: {response.status_code} - {response.text}")
            return LLMAnalysisResult(
                sentiment_score=50,
                sentiment_reason="API请求失败",
                key_events=[],
                policy_impact="无法分析",
                macro_impact="无法分析",
                investment_suggestion="观望",
                confidence="低",
                success=False,
                error_message=f"API错误: {response.status_code}"
            )

        result = response.json()
        content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        logger.info(f"Gemini 分析成功: {stock_name} ({code})")

        return self._parse_response(content)

    def _parse_response(self, content: str) -> LLMAnalysisResult:
        """解析 LLM 返回的内容"""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)

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
            else:
                return self._fallback_parse(content)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败，尝试备用解析: {e}")
            return self._fallback_parse(content)

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