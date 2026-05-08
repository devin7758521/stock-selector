# -*- coding: utf-8 -*-
"""
增强版 LLM 分析器模块

功能：
1. 多维度综合分析（技术面、消息面、政策面）
2. 权重机制：LLM > AI > 技术指标
3. 国内外财经政治形势分析
4. 详细的推理过程和打星理由
5. 预留真正的LLM API接口（litellm）

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    sentiment_score: int
    trend_prediction: str
    operation_advice: str
    confidence_level: str
    analysis_summary: str
    news_summary: str
    risk_warning: str
    buy_reason: str
    model_used: str
    success: bool
    stars: int
    star_reason: str

    technical_analysis_detail: str = ""
    news_analysis_detail: str = ""
    policy_analysis_detail: str = ""
    market_environment_analysis: str = ""

    recommendation_reason: str = ""

    weighted_score: float = 0.0
    llm_weight: float = 0.5
    ai_weight: float = 0.3
    technical_weight: float = 0.0

    score_detail: Optional[Dict[str, Any]] = None

    error_message: Optional[str] = None

    news_headlines: str = ""
    policy_info: str = ""
    macro_info: str = ""
    llm_news_reason: str = ""


class EnhancedLLMAnalyzer:
    """
    增强版 LLM 分析器

    分析维度：
    1. 技术面分析（MACD、KDJ、RSI、均线等）
    2. 消息面分析（新闻、公告、市场情绪）
    3. 政策面分析（国内外财经政策、行业政策）
    4. 市场环境分析（大盘走势、板块轮动、资金流向）

    权重机制：
    - LLM综合评分：50%
    - AI分析评分：30%
    - 技术指标评分：20%

    星级：0～5 星；加权综合分（内部 0～100）低于 WEIGHTED_SCORE_ZERO_STAR_BELOW 为「无星」。
    """

    # 评分量纲 0~100，低于该加权分则为 0 星
    WEIGHTED_SCORE_ZERO_STAR_BELOW: float = 30.0

    def __init__(self, api_key: Optional[str] = None, model: str = "local", fallback_model: Optional[str] = None, deepseek_api_key: Optional[str] = None, sector_results: Optional[List] = None, gemini_api_key_2: Optional[str] = None, gemini_model_2: Optional[str] = None):
        """
        初始化分析器

        Args:
            api_key: LLM API密钥（可选）
            model: 使用的模型（local/gpt-4/claude/deepseek等）
            fallback_model: 备用模型（当主模型失败时自动切换）
            deepseek_api_key: DeepSeek 专用 API Key（用于 fallback）
            sector_results: 板块筛选结果（用于板块联动分析）
            gemini_api_key_2: 第二个 Gemini API Key（三级降级）
            gemini_model_2: 第二个 Gemini 模型名称
        """
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.deepseek_api_key = deepseek_api_key
        self.sector_results = sector_results or []
        self.gemini_api_key_2 = gemini_api_key_2
        self.gemini_model_2 = gemini_model_2
        self.model_used = f"Enhanced {model.upper()}" if model != "local" else "Enhanced Local Analyzer"

        self.llm_client = None
        self.deepseek_analyzer = None

        if api_key and model != "local":
            try:
                from .deepseek_analyzer import LLMNewsAnalyzer
                self.deepseek_analyzer = LLMNewsAnalyzer(
                    api_key, model,
                    fallback_model=fallback_model,
                    deepseek_api_key=deepseek_api_key,
                    gemini_api_key_2=gemini_api_key_2,
                    gemini_model_2=gemini_model_2
                )
                logger.info(f"已初始化LLMNewsAnalyzer新闻分析器 (主模型: {model}, 备用: {fallback_model})")
            except ImportError as e:
                logger.warning(f"无法导入LLM分析器: {e}")
        else:
            logger.info(f"LLM分析器未初始化: api_key={'有' if api_key else '无'}, model={model}")

    def analyze(self, context: Dict[str, Any], news_context: Optional[str],
                ai_analysis: Optional[Dict] = None,
                technical_analysis: Optional[Dict] = None,
                stock_data: Optional[Dict] = None) -> AnalysisResult:
        """
        综合分析股票数据

        Args:
            context: 股票上下文数据
            news_context: 新闻上下文
            ai_analysis: AI分析结果
            technical_analysis: 技术分析结果

        Returns:
            分析结果
        """
        try:
            from .analyzers import (
                TechnicalAnalyzer,
                NewsAnalyzer,
                PolicyAnalyzer,
                MarketEnvironmentAnalyzer
            )

            stock_name = context.get('stock_name', '未知股票')
            code = context.get('code', '未知代码')
            industry = context.get('industry')

            logger.info(f"开始综合分析: {stock_name} ({code})")

            technical_analyzer = TechnicalAnalyzer()
            news_analyzer = NewsAnalyzer()
            policy_analyzer = PolicyAnalyzer()
            market_analyzer = MarketEnvironmentAnalyzer(sector_results=self.sector_results)

            technical_detail, technical_score = technical_analyzer.analyze(
                technical_analysis, context
            )

            news_detail, news_score, news_headlines, policy_info, macro_info = news_analyzer.analyze(
                news_context, stock_name, code
            )

            llm_news_reason = ""
            llm_policy_score = None
            llm_macro_score = None
            if self.deepseek_analyzer and news_context:
                logger.info(f"使用LLM进行新闻深度分析: {stock_name}")
                llm_result = self.deepseek_analyzer.analyze(
                    news_context, stock_name, code, industry
                )
                if llm_result.success:
                    news_score = llm_result.sentiment_score
                    llm_news_reason = llm_result.sentiment_reason
                    llm_policy_score = llm_result.policy_score
                    llm_macro_score = llm_result.macro_score
                    if llm_result.key_events:
                        news_headlines = "；".join(llm_result.key_events)
                    if llm_result.policy_impact:
                        policy_info = llm_result.policy_impact
                    if llm_result.macro_impact:
                        macro_info = llm_result.macro_impact
                    logger.info(f"LLM分析完成，情绪: {news_score}, 政策: {llm_policy_score}, 宏观: {llm_macro_score}")

            policy_detail, _ = policy_analyzer.analyze(context, news_context)
            # 政策面无实质内容 → 传 None，不参与 LLM 加权
            _no_policy = ("", "信息不足", "无政策相关信息", "分析异常")
            if llm_policy_score is not None and policy_info and policy_info not in _no_policy:
                policy_score = llm_policy_score
            else:
                policy_score = None

            market_detail, market_score = market_analyzer.analyze(context)
            # 宏观面无实质内容 → 传 None，不参与 LLM 加权
            _no_macro = ("", "信息不足", "无宏观相关信息", "分析异常")
            if llm_macro_score is not None and macro_info and macro_info not in _no_macro:
                macro_score = llm_macro_score
            else:
                macro_score = None

            llm_base_score = self._calculate_llm_score(
                news_score, policy_score, macro_score, market_score
            )

            ai_score = self._extract_ai_score(ai_analysis)
            tech_score = technical_analyzer.extract_score(technical_analysis)

            # 新评分体系：硬数据 + LLM 融合
            indicators = (stock_data or {}).copy()
            weighted_score, score_detail = self._calculate_enhanced_weighted_score(
                indicators=indicators,
                technical_analysis=technical_analysis,
                context=context,
                llm_score=llm_base_score,
                ai_score=ai_score,
                tech_score=tech_score,
                stock_data=(stock_data or {}),
                news_context=news_context,
            )

            operation_advice, confidence_level = self._generate_operation_advice(weighted_score)

            trend_prediction = self._predict_trend(
                weighted_score, technical_score, news_score, policy_score, macro_score
            )

            recommendation_reason = self._generate_recommendation_reason(
                stock_name, code, technical_detail,
                weighted_score, operation_advice,
                llm_news_reason, policy_info, macro_info,
            )

            risk_warning = self._generate_risk_warning(
                policy_score, macro_score, market_score
            )

            buy_reason = self._generate_buy_reason(
                weighted_score, llm_news_reason, policy_info
            )

            stars = self._calculate_stars(weighted_score)

            # 打星理由包含各维度明细
            star_reason = (
                f"综合{weighted_score:.1f}分 " +
                f"| 技术{score_detail['tech_resonance']:.0f} " +
                f"| 量能{score_detail['volume_quality']:.0f} " +
                f"| 板块{score_detail['sector_bonus']:.0f} " +
                f"| LLM融合{score_detail['combined_ai_llm']:.0f} " +
                f"| LLM直分{score_detail['llm_direct']:.0f}" +
                ("" if score_detail['news_available'] else " (无新闻)")
            )

            analysis_summary = self._generate_summary(
                stock_name, code, weighted_score, operation_advice,
                confidence_level, trend_prediction
            )

            return AnalysisResult(
                sentiment_score=int(llm_base_score),
                trend_prediction=trend_prediction,
                operation_advice=operation_advice,
                confidence_level=confidence_level,
                analysis_summary=analysis_summary,
                news_summary=news_context or "无新闻信息",
                risk_warning=risk_warning,
                buy_reason=buy_reason,
                model_used=self.model_used,
                success=True,
                stars=stars,
                star_reason=star_reason,
                technical_analysis_detail=technical_detail,
                news_analysis_detail=news_detail,
                policy_analysis_detail=policy_detail,
                market_environment_analysis=market_detail,
                recommendation_reason=recommendation_reason,
                weighted_score=weighted_score,
                llm_weight=0.5,
                ai_weight=0.3,
                technical_weight=0.0,
                score_detail=score_detail,
                news_headlines=news_headlines,
                policy_info=policy_info,
                macro_info=macro_info,
                llm_news_reason=llm_news_reason
            )

        except Exception as e:
            logger.error(f"分析失败: {e}", exc_info=True)
            return self._create_error_result(str(e))

    # ── 新评分体系：硬数据主导（70%）+ LLM 做加法（20%）+ 板块联动（10%） ──

    def _calculate_tech_resonance_score(self, indicators: Dict[str, Any],
                                        technical_analysis: Optional[Dict],
                                        context: Dict[str, Any]) -> float:
        """技术共振评分（0~60，替代原来 50~70 的窄技术分）"""
        score = 0.0

        # 1. 金叉新鲜度 (0~20)
        gc_weeks = indicators.get("golden_cross_weeks", 99)
        if gc_weeks == 0:
            score += 20  # 本周刚金叉
        elif gc_weeks == 1:
            score += 16
        elif gc_weeks == 2:
            score += 12
        elif gc_weeks == 3:
            score += 8
        elif gc_weeks <= 5:
            score += 4
        # >5 周不加分

        # 金叉后涨幅惩罚（涨幅过大减分）
        gc_gain = indicators.get("golden_cross_gain_pct", 0)
        if gc_weeks <= 5 and gc_gain > 15:
            score -= 5   # 金叉后涨幅过大，追高扣分

        # 2. RSI 位置 (0~12)
        rsi = 50
        if isinstance(technical_analysis, dict):
            rsi = float(technical_analysis.get("rsi", 50))
        if 55 <= rsi <= 72:
            score += 12  # 强势非超买
        elif 45 <= rsi < 55:
            score += 6
        elif 72 < rsi <= 80:
            score += 3   # 偏强但接近超买
        # rsi < 45 或 > 80 不加分

        # 3. MA25 偏离度 (0~12)
        ma25_dev = indicators.get("ma25_deviation_pct", 0)
        if 3 <= ma25_dev <= 10:
            score += 12  # 最佳攻击区
        elif 0 < ma25_dev < 3:
            score += 8
        elif 10 < ma25_dev <= 20:
            score += 4
        elif ma25_dev > 20:
            score -= 3   # 过度延伸

        # 4. KDJ/均线共振 (0~10)
        kdj_golden = indicators.get("kdj_recent_golden", False)
        weeks_above = indicators.get("weeks_above_ma25", 0)
        if kdj_golden and weeks_above >= 3:
            score += 10  # KDJ金叉 + 连续站上MA25
        elif kdj_golden:
            score += 6
        elif weeks_above >= 5:
            score += 3   # 趋势稳固但无金叉

        # 5. MACD 金叉质量 (0~6)
        if indicators.get("macd_recently_crossed"):
            score += 6

        return max(0, min(60, score))

    def _calculate_volume_quality_score(self, indicators: Dict[str, Any]) -> float:
        """量能质量评分（0~30），取代表绝对阈值"""
        score = 0.0

        # 1. 量比 (0~12)
        vol_ratio = indicators.get("volume_ratio", 1.0)
        if 1.5 <= vol_ratio <= 2.5:
            score += 12  # 温和放量最佳
        elif 1.2 <= vol_ratio < 1.5:
            score += 8
        elif 1.0 <= vol_ratio < 1.2:
            score += 4
        elif vol_ratio > 2.5:
            score += 2   # 爆量，可能有对倒

        # 2. 日成交额活跃度 (0~8)，相对打分不设绝对值
        daily_amt = indicators.get("daily_amount_yi", 0)
        if daily_amt >= 20:
            score += 8   # 大资金关注
        elif daily_amt >= 10:
            score += 6
        elif daily_amt >= 5:
            score += 3
        # < 5 亿不扣分但也不加分（过滤阶段已保证 >=5亿）

        # 3. 量价配合 (0~10)
        vp_signal = indicators.get("vol_price_signal", "")
        if vp_signal == "healthy":
            score += 10  # 价涨量增
        elif vp_signal == "divergence":
            score += 2   # 价涨量缩 - 背离信号
        elif vp_signal == "distribution":
            score -= 5   # 价跌量增 - 减分！
        # weak 不加分

        return max(0, min(30, score))

    def _calculate_sector_linkage_score(self, stock_data: Dict[str, Any]) -> float:
        """板块联动加分（0~15），来源于 sector_results 注入"""
        score = 0.0
        sector_hint = stock_data.get("llm_market_detail", "") or \
                       stock_data.get("market_environment_analysis", "") or ""
        if not sector_hint:
            return 0.0

        # 从 LLM 市场环境分析文本中匹配板块排名
        import re
        rank_match = re.search(r'今日涨幅第(\d+)', sector_hint)
        if rank_match:
            rank = int(rank_match.group(1))
            if rank == 1:
                score += 12
            elif rank == 2:
                score += 8
            elif rank == 3:
                score += 5
            elif rank <= 5:
                score += 3

        # 板块联动强度关键词
        if '极强' in sector_hint:
            score += 3
        elif '强' in sector_hint and '不强' not in sector_hint:
            score += 1

        return max(0, min(15, score))

    def _calculate_enhanced_weighted_score(
        self, indicators: Dict[str, Any], technical_analysis: Optional[Dict],
        context: Dict[str, Any], llm_score: float, ai_score: Optional[int],
        tech_score: int, stock_data: Dict[str, Any],
        news_context: Optional[str] = None) -> tuple:
        """
        评分公式（子维度归一化到 0~100，技术面不给权重）：
        weighted = 量能质量×45% + LLM/AI融合×25% + LLM直接分×20% + 板块联动×10%
        """
        volume_quality = self._calculate_volume_quality_score(indicators)
        sector_bonus = self._calculate_sector_linkage_score(stock_data)

        volume_100 = volume_quality * 100.0 / 30.0
        sector_100 = sector_bonus * 100.0 / 15.0

        news_available = bool(news_context and len(news_context.strip()) > 30)

        if ai_score is not None:
            ai_norm = ai_score / 100.0 * 60
            llm_norm = llm_score / 100.0 * 60
            if abs(ai_norm - llm_norm) > 15:
                combined_ai_llm = max(ai_norm, llm_norm)
            else:
                combined_ai_llm = ai_norm * 0.4 + llm_norm * 0.6
            llm_ai_100 = combined_ai_llm * 100.0 / 60.0
            if not news_available:
                llm_ai_100 = ai_norm * 100.0 / 60.0
        else:
            llm_ai_100 = llm_score

        llm_direct_100 = llm_score

        weighted = (
            volume_100 * 0.45 +    # 量能质量（量比+成交额+量价信号，真金白银）
            llm_ai_100 * 0.25 +    # LLM/AI 智能融合
            llm_direct_100 * 0.20 + # LLM直接分（含政策25%+宏观20%）
            sector_100 * 0.10      # 板块联动
        )

        detail = {
            "tech_resonance": 0,
            "volume_quality": round(volume_100, 1),
            "sector_bonus": round(sector_100, 1),
            "combined_ai_llm": round(llm_ai_100, 1),
            "llm_direct": round(llm_direct_100, 1),
            "news_available": news_available,
        }
        return max(0, min(100, weighted)), detail

    # 保留旧接口兼容
    def _calculate_llm_score(self, news_score: Optional[int],
                            policy_score: Optional[int],
                            macro_score: Optional[int],
                            market_score: Optional[int]) -> float:
        weights = {"news": 0.40, "policy": 0.20, "macro": 0.15, "market": 0.25}
        scores = {"news": news_score, "policy": policy_score, "macro": macro_score, "market": market_score}
        available = {k: v for k, v in scores.items() if v is not None}
        if not available:
            return 50.0
        if len(available) < len(scores):
            total_weight = sum(weights[k] for k in available)
            return sum(available[k] * (weights[k] / total_weight) for k in available)
        return news_score * 0.40 + policy_score * 0.20 + macro_score * 0.15 + market_score * 0.25

    def _extract_ai_score(self, ai_analysis: Optional[Dict]) -> Optional[int]:
        if ai_analysis:
            return ai_analysis.get('ai_signal_score', 50)
        return None

    def _calculate_weighted_score(self, llm_score: float, ai_score: int,
                                 tech_score: int) -> float:
        """旧加权分（保留兼容）"""
        return llm_score * 0.5 + ai_score * 0.3 + tech_score * 0.2

    def _generate_operation_advice(self, weighted_score: float) -> tuple:
        """评分 0~100 的操作建议映射"""
        if weighted_score >= 72:
            return "强烈买入", "高"
        elif weighted_score >= 62:
            return "买入", "中高"
        elif weighted_score >= 50:
            return "持有", "中"
        elif weighted_score >= 38:
            return "观望", "中低"
        else:
            return "卖出", "低"

    def _predict_trend(self, weighted_score: float, technical_score: int,
                      news_score: int, policy_score: int, macro_score: int) -> str:
        if weighted_score >= 68:
            return "强势上涨"
        elif weighted_score >= 55:
            return "震荡上行"
        elif weighted_score >= 42:
            return "横盘震荡"
        elif weighted_score >= 30:
            return "震荡下行"
        else:
            return "弱势下跌"

    def _generate_recommendation_reason(
        self, stock_name: str, code: str,
        technical_detail: str, weighted_score: float,
        operation_advice: str, llm_news_reason: str,
        policy_info: str, macro_info: str,
    ) -> str:
        parts = []
        if llm_news_reason:
            parts.append(llm_news_reason)
        if policy_info and policy_info != "信息不足":
            parts.append(f"政策面：{policy_info}")
        if macro_info and macro_info != "信息不足":
            parts.append(f"宏观面：{macro_info}")
        parts.append(self._get_score_summary(weighted_score, operation_advice))
        return "；".join(parts)

    def _get_score_summary(self, weighted_score: float, operation_advice: str) -> str:
        if weighted_score >= 72:
            return f"综合评分{weighted_score:.1f}分，多维度共振积极，建议{operation_advice}。"
        elif weighted_score >= 55:
            return f"综合评分{weighted_score:.1f}分，多维度分析偏多，建议{operation_advice}。"
        elif weighted_score >= 42:
            return f"综合评分{weighted_score:.1f}分，多维度分析中性偏空，建议{operation_advice}。"
        else:
            return f"综合评分{weighted_score:.1f}分，多维度信号偏弱，建议{operation_advice}。"

    def _generate_risk_warning(self, policy_score: int,
                              macro_score: int, market_score: int) -> str:
        warnings = []
        if policy_score < 40:
            warnings.append("政策面不利，存在政策风险")
        if macro_score < 40:
            warnings.append("宏观环境不佳，存在系统性风险")
        if market_score < 40:
            warnings.append("市场环境不佳，存在流动性风险")
        if not warnings:
            warnings.append("投资有风险，入市需谨慎")
        return "；".join(warnings)

    def _generate_buy_reason(self, weighted_score: float,
                            llm_news_reason: str, policy_info: str) -> str:
        if weighted_score < 62:
            return "当前不建议买入"
        reasons = []
        if llm_news_reason:
            reasons.append(f"消息面：{llm_news_reason}")
        if policy_info and policy_info != "信息不足":
            reasons.append(f"政策面：{policy_info}")
        return "；".join(reasons) if reasons else "综合评分较高，可考虑买入"

    def _calculate_stars(self, weighted_score: float) -> int:
        """评分 0~100 的星级映射"""
        if weighted_score < self.WEIGHTED_SCORE_ZERO_STAR_BELOW:
            return 0
        if weighted_score >= 80:
            return 5
        if weighted_score >= 68:
            return 4
        if weighted_score >= 55:
            return 3
        if weighted_score >= 42:
            return 2
        return 1

    def _get_llm_synthesis(self, stars: int, weighted_score: float,
                          technical_detail: str,
                          news_detail: str, policy_detail: str,
                          market_detail: str, news_headlines: str,
                          policy_info: str, macro_info: str,
                          llm_news_reason: str = "",
                          ai_analysis: Optional[Dict] = None,
                          stock_name: str = "标的") -> str:
        """调用 LLM 进行综合推理，LLM分析原文优先于关键词占位符。"""
        if not self.deepseek_analyzer:
            return ""

        # 技术面
        td = technical_detail if technical_detail and technical_detail != "N/A" else "暂无技术面数据"

        # 消息面：LLM分析原文 > 关键词计数 > 默认
        nd = "暂无消息面数据"
        if llm_news_reason and llm_news_reason not in ("信息不足", "无新闻信息", ""):
            nd = llm_news_reason
            if news_headlines:
                nd += f"\n新闻标题：{news_headlines}"
        elif news_headlines:
            nd = f"新闻要点：{news_headlines}"
        elif news_detail and news_detail != "N/A":
            nd = news_detail

        # 政策面：LLM policy_impact > 默认
        pd = "暂无明显政策面影响"
        is_placeholder = policy_detail in ("政策面分析已由LLM完成", "N/A", "")
        if policy_info and policy_info not in ("信息不足", "无政策相关信息", "分析异常", ""):
            pd = policy_info
        elif not is_placeholder and policy_detail:
            pd = policy_detail

        # 宏观/市场环境：LLM macro_impact > 市场分析 > 默认
        md = "暂无市场环境数据"
        if macro_info and macro_info not in ("信息不足", "无宏观相关信息", "分析异常", ""):
            md = macro_info
        elif market_detail and market_detail != "N/A" and market_detail != "暂无明显市场环境影响":
            md = market_detail

        ai_info = ""
        if ai_analysis:
            ai_signal = ai_analysis.get('ai_buy_signal', 'N/A')
            ai_score_val = ai_analysis.get('ai_signal_score', 'N/A')
            if ai_signal != "N/A":
                ai_info = f"AI技术指标信号：{ai_signal}（评分{ai_score_val}分）"

        user_prompt = f"""请对以下股票进行多维度综合推理，严格基于给定的信息，不要凭空推测：

【股票】{stock_name}
【星级】{stars}星（满分5星）
【综合评分】{weighted_score:.1f}分

【技术面分析】
{td}

【消息面分析】
{nd}

【政策面分析】
{pd}

【市场环境】
{md}
{f"【AI技术指标】{ai_info}" if ai_info else ""}

请基于以上信息，输出：
1. 各维度之间是否存在矛盾或共振（若某维度确实无信息，如实说明，不要反复强调）
2. 当前最关键的驱动因素
3. 一段80-150字的综合投资理由
4. 推理评分: XX

专业、简洁、基于事实。"""

        try:
            synthesis = self.deepseek_analyzer.synthesize(user_prompt, max_tokens=400)
            if synthesis:
                logger.info(f"LLM综合推理成功: {synthesis[:80]}...")
                return synthesis
        except Exception as e:
            logger.warning(f"LLM综合推理失败: {e}")
        return ""

    def _generate_final_advice(self, stars: int, weighted_score: float) -> str:
        if stars <= 0:
            return "硬数据综合评分偏低，不建议作为重点标的；若已持仓宜严控仓位。"
        if stars >= 4:
            return "硬数据与技术共振强烈，当前具备较好投资价值，建议积极关注或买入"
        if stars >= 3:
            return "多维度综合偏多，建议持有或择机加仓"
        return "多维度信号偏弱，建议谨慎参与或观望"

    def _generate_summary(self, stock_name: str, code: str,
                         weighted_score: float, operation_advice: str,
                         confidence_level: str, trend_prediction: str) -> str:
        """生成分析摘要"""
        return f"{stock_name}({code})综合评分{weighted_score:.1f}分，建议{operation_advice}，置信度{confidence_level}，预测趋势{trend_prediction}。"

    def _create_error_result(self, error_message: str) -> AnalysisResult:
        """创建错误结果"""
        return AnalysisResult(
            sentiment_score=50,
            trend_prediction="N/A",
            operation_advice="N/A",
            confidence_level="N/A",
            analysis_summary="分析失败",
            news_summary="N/A",
            risk_warning="N/A",
            buy_reason="N/A",
            model_used=self.model_used,
            success=False,
            stars=0,
            star_reason="分析异常，跳过评级",
            error_message=error_message,
            technical_analysis_detail="",
            news_analysis_detail="",
            policy_analysis_detail="",
            market_environment_analysis="",
            recommendation_reason="",
            weighted_score=0,
            score_detail=None,
            news_headlines="",
            policy_info="",
            macro_info="",
            llm_news_reason="",
        )

    def rank_stocks(self, stock_results: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        对所有股票进行综合推理，按推理评分+成交量权重排序

        Args:
            stock_results: 股票分析结果列表
            top_n: 返回数量，默认10只

        Returns:
            推理后的股票列表（按推理分数+成交量权重排序）
        """
        if not stock_results:
            return []

        logger.info(f"开始LLM综合推理（共{len(stock_results)}只）...")

        ranked_results = []
        for i, r in enumerate(stock_results):
            try:
                stars = r.get("llm_stars", 0)
                weighted_score = r.get("llm_weighted_score", r.get("weighted_score", 50))
                technical_detail = r.get("llm_technical_detail", r.get("technical_analysis_detail", "N/A"))
                news_detail = r.get("llm_news_detail", r.get("news_analysis_detail", "N/A"))
                policy_detail = r.get("llm_policy_detail", r.get("policy_analysis_detail", "N/A"))
                market_detail = r.get("llm_market_detail", r.get("market_environment_analysis", "N/A"))
                news_headlines = r.get("news_headlines", "")
                policy_info = r.get("policy_info", "")
                macro_info = r.get("macro_info", "")
                llm_news_reason = r.get("llm_news_reason", "")  # LLM情绪分析原文
                ai_analysis = None
                stock_name = r.get("name", r.get("stock_name", "未知"))
                code = r.get("code", "")

                synthesis = self._get_llm_synthesis(
                    stars, weighted_score,
                    technical_detail,
                    news_detail, policy_detail, market_detail,
                    news_headlines, policy_info, macro_info,
                    llm_news_reason,
                    ai_analysis, stock_name
                )

                volume = r.get("volume", r.get("amount", 0))
                inference_score = self._parse_inference_score(synthesis, weighted_score, stars, volume)
                r["llm_inference_score"] = inference_score
                r["llm_inference_reason"] = synthesis

                logger.info(f"  [{i+1}/{len(stock_results)}] {stock_name} 推理评分: {inference_score:.1f}")
                ranked_results.append(r)

            except Exception as e:
                logger.warning(f"股票 {r.get('name', code)} 推理失败: {e}")
                r["llm_inference_score"] = r.get("llm_weighted_score", 50)
                r["llm_inference_reason"] = ""
                ranked_results.append(r)

        ranked_results.sort(key=lambda x: x.get("llm_inference_score", 0), reverse=True)
        logger.info(f"LLM综合推理完成，Top10: {[r['name'] for r in ranked_results[:10]]}")

        return ranked_results

    def _parse_inference_score(self, synthesis: str, weighted_score: float, stars: int, volume: float = 0) -> float:
        """
        从LLM推理文本中解析出量化评分。

        权重分配：LLM推理分×40% + 加权分×45% + 成交量权重×15%
        其中 LLM推理分从文本中提取（默认退回加权分），成交量权重小幅影响。
        """
        llm_inferred = self._extract_llm_score(synthesis) if synthesis else None

        base_score = weighted_score

        quality_bonus = 0.0
        if synthesis and synthesis.strip():
            if len(synthesis) > 60:
                quality_bonus = 5.0
            elif len(synthesis) > 20:
                quality_bonus = 2.0

        volume_bonus = 0.0
        if volume and volume > 0:
            volume_bonus = min(5.0, (volume / 100000000) * 0.5)

        if llm_inferred is not None:
            inference_score = base_score * 0.45 + llm_inferred * 0.40 + quality_bonus + volume_bonus
        else:
            inference_score = base_score * 0.90 + quality_bonus + volume_bonus

        return min(100, inference_score)

    @staticmethod
    def _extract_llm_score(synthesis: str) -> Optional[float]:
        """从 LLM 合成文本中提取推理评分"""
        import re
        patterns = [
            r'推理评分[：:]\s*(\d+(?:\.\d+)?)',
            r'推理分[：:]\s*(\d+(?:\.\d+)?)',
            r'inference.?score[：:=]\s*(\d+(?:\.\d+)?)',
        ]
        for pat in patterns:
            m = re.search(pat, synthesis, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def deep_analyze_top3(self, top3: List[Dict]) -> Optional[str]:
        """
        对 Top3 进行深度链式推理分析（使用 DeepSeek V4 Pro）。

        Args:
            top3: 前 3 只股票的结果列表（至少 3 只）

        Returns:
            深度分析文本，失败返回 None
        """
        if not self.deepseek_analyzer or len(top3) < 1:
            logger.warning("deep_analyze_top3: 分析器未初始化或数据不足")
            return None

        # 补齐到3只（不足则用空占位）
        stocks = list(top3[:3])
        while len(stocks) < 3:
            stocks.append({"name": "无", "code": "无", "llm_stars": 0, "llm_weighted_score": 0})

        logger.info(f"开始 Top3 深度链式推理: {[s.get('name') for s in stocks]}")
        try:
            analysis = self.deepseek_analyzer.deep_analyze_top3(
                stocks[0], stocks[1], stocks[2]
            )
            return analysis
        except Exception as e:
            logger.error(f"Top3深度分析失败: {e}", exc_info=True)
            return None
