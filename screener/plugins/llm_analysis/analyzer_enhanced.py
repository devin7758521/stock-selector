# -*- coding: utf-8 -*-
"""
增强版 LLM 分析器模块

功能：
1. 多维度综合分析（技术面、基本面、消息面、政策面）
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
    fundamental_analysis_detail: str = ""
    news_analysis_detail: str = ""
    policy_analysis_detail: str = ""
    market_environment_analysis: str = ""

    recommendation_reason: str = ""

    weighted_score: float = 0.0
    llm_weight: float = 0.5
    ai_weight: float = 0.3
    technical_weight: float = 0.2

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
    2. 基本面分析（ROE、PE、PB、营收增长等）
    3. 消息面分析（新闻、公告、市场情绪）
    4. 政策面分析（国内外财经政策、行业政策）
    5. 市场环境分析（大盘走势、板块轮动、资金流向）

    权重机制：
    - LLM综合评分：50%
    - AI分析评分：30%
    - 技术指标评分：20%

    星级：0～5 星；加权综合分（内部 0～100）低于 WEIGHTED_SCORE_ZERO_STAR_BELOW 为「无星」。
    """

    # 可调：低于该加权分则为 0 星（无星）
    WEIGHTED_SCORE_ZERO_STAR_BELOW: float = 32.0

    def __init__(self, api_key: Optional[str] = None, model: str = "local"):
        """
        初始化分析器

        Args:
            api_key: LLM API密钥（可选）
            model: 使用的模型（local/gpt-4/claude/deepseek等）
        """
        self.api_key = api_key
        self.model = model
        self.model_used = f"Enhanced {model.upper()}" if model != "local" else "Enhanced Local Analyzer"

        self.llm_client = None
        self.deepseek_analyzer = None

        if api_key and model != "local":
            try:
                from .deepseek_analyzer import LLMNewsAnalyzer
                self.deepseek_analyzer = LLMNewsAnalyzer(api_key, model)
                logger.info(f"已初始化{LLMNewsAnalyzer.__name__}新闻分析器 (模型: {model})")
            except ImportError as e:
                logger.warning(f"无法导入LLM分析器: {e}")
        else:
            logger.info(f"LLM分析器未初始化: api_key={'有' if api_key else '无'}, model={model}")

    def analyze(self, context: Dict[str, Any], news_context: Optional[str],
                ai_analysis: Optional[Dict] = None,
                technical_analysis: Optional[Dict] = None,
                fundamental_analysis: Optional[Dict] = None) -> AnalysisResult:
        """
        综合分析股票数据

        Args:
            context: 股票上下文数据
            news_context: 新闻上下文
            ai_analysis: AI分析结果
            technical_analysis: 技术分析结果
            fundamental_analysis: 基本面分析结果

        Returns:
            分析结果
        """
        try:
            from .analyzers import (
                TechnicalAnalyzer,
                FundamentalAnalyzer,
                NewsAnalyzer,
                PolicyAnalyzer,
                MarketEnvironmentAnalyzer
            )

            stock_name = context.get('stock_name', '未知股票')
            code = context.get('code', '未知代码')
            industry = context.get('industry')

            logger.info(f"开始综合分析: {stock_name} ({code})")

            technical_analyzer = TechnicalAnalyzer()
            fundamental_analyzer = FundamentalAnalyzer()
            news_analyzer = NewsAnalyzer()
            policy_analyzer = PolicyAnalyzer()
            market_analyzer = MarketEnvironmentAnalyzer()

            technical_detail, technical_score = technical_analyzer.analyze(
                technical_analysis, context
            )

            fundamental_detail, fundamental_score = fundamental_analyzer.analyze(
                fundamental_analysis, context
            )

            news_detail, news_score, news_headlines, policy_info, macro_info = news_analyzer.analyze(
                news_context, stock_name, code
            )

            llm_news_reason = ""
            if self.deepseek_analyzer and news_context:
                logger.info(f"使用DeepSeek进行新闻深度分析: {stock_name}")
                llm_result = self.deepseek_analyzer.analyze(
                    news_context, stock_name, code, industry
                )
                if llm_result.success:
                    news_score = llm_result.sentiment_score
                    llm_news_reason = llm_result.sentiment_reason
                    if llm_result.key_events:
                        news_headlines = "；".join(llm_result.key_events)
                    if llm_result.policy_impact:
                        policy_info = llm_result.policy_impact
                    if llm_result.macro_impact:
                        macro_info = llm_result.macro_impact
                    logger.info(f"DeepSeek分析完成，情绪评分: {news_score}")

            policy_detail, policy_score = policy_analyzer.analyze(
                context, news_context
            )

            market_detail, market_score = market_analyzer.analyze(context)

            llm_base_score = self._calculate_llm_score(
                technical_score, fundamental_score, news_score,
                policy_score, market_score
            )

            ai_score = self._extract_ai_score(ai_analysis)
            tech_score = technical_analyzer.extract_score(technical_analysis)

            weighted_score = self._calculate_weighted_score(
                llm_base_score, ai_score, tech_score
            )

            operation_advice, confidence_level = self._generate_operation_advice(weighted_score)

            trend_prediction = self._predict_trend(
                weighted_score, technical_score, news_score, policy_score
            )

            recommendation_reason = self._generate_recommendation_reason(
                stock_name,
                code,
                technical_detail,
                fundamental_detail,
                news_detail,
                policy_detail,
                market_detail,
                weighted_score,
                operation_advice,
                ai_analysis,
            )

            risk_warning = self._generate_risk_warning(
                fundamental_score, policy_score, market_score
            )

            buy_reason = self._generate_buy_reason(
                weighted_score, technical_detail, fundamental_detail,
                news_detail, policy_detail
            )

            stars = self._calculate_stars(weighted_score)

            star_reason = self._generate_star_reason(
                stars, weighted_score, llm_base_score, ai_score, tech_score,
                technical_detail, fundamental_detail, news_detail,
                policy_detail, market_detail, news_headlines, policy_info, macro_info,
                llm_news_reason,
                ai_analysis=ai_analysis,
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
                fundamental_analysis_detail=fundamental_detail,
                news_analysis_detail=news_detail,
                policy_analysis_detail=policy_detail,
                market_environment_analysis=market_detail,
                recommendation_reason=recommendation_reason,
                weighted_score=weighted_score,
                llm_weight=0.5,
                ai_weight=0.3,
                technical_weight=0.2,
                news_headlines=news_headlines,
                policy_info=policy_info,
                macro_info=macro_info,
                llm_news_reason=llm_news_reason
            )

        except Exception as e:
            logger.error(f"分析失败: {e}", exc_info=True)
            return self._create_error_result(str(e))

    def _calculate_llm_score(self, technical_score: int, fundamental_score: int,
                            news_score: int, policy_score: int,
                            market_score: int) -> float:
        """计算LLM综合评分"""
        return (
            technical_score * 0.20 +
            fundamental_score * 0.30 +
            news_score * 0.25 +
            policy_score * 0.15 +
            market_score * 0.10
        )

    def _extract_ai_score(self, ai_analysis: Optional[Dict]) -> int:
        """提取AI评分"""
        if ai_analysis:
            return ai_analysis.get('ai_signal_score', 50)
        return 50
    
    def _extract_technical_score(self, technical_detail: str) -> int:
        """从技术面分析中提取评分"""
        score = 50
        if 'MACD金叉' in technical_detail or 'KDJ多头' in technical_detail:
            score += 20
        if 'RSI超卖' in technical_detail:
            score += 15
        if '均线多头' in technical_detail:
            score += 15
        if 'MACD死叉' in technical_detail or 'KDJ空头' in technical_detail:
            score -= 20
        if 'RSI超买' in technical_detail:
            score -= 15
        if '均线空头' in technical_detail:
            score -= 15
        return max(0, min(100, score))
    
    def _extract_fundamental_score(self, fundamental_detail: str) -> int:
        """从基本面分析中提取评分"""
        score = 50
        if 'ROE优秀' in fundamental_detail:
            score += 15
        if 'PE估值偏低' in fundamental_detail or 'PE估值合理' in fundamental_detail:
            score += 10
        if 'PB估值较低' in fundamental_detail or 'PB估值合理' in fundamental_detail:
            score += 8
        if '营收高速增长' in fundamental_detail or '营收稳健增长' in fundamental_detail:
            score += 12
        if 'ROE较差' in fundamental_detail:
            score -= 15
        if 'PE估值偏高' in fundamental_detail:
            score -= 10
        if 'PB估值偏高' in fundamental_detail:
            score -= 8
        if '营收负增长' in fundamental_detail:
            score -= 12
        return max(0, min(100, score))
    
    def _extract_news_score(self, news_detail: str) -> int:
        """从消息面分析中提取评分"""
        score = 50
        if '利好' in news_detail or '积极' in news_detail:
            score += 25
        if '利空' in news_detail or '消极' in news_detail:
            score -= 25
        return max(0, min(100, score))
    
    def _extract_policy_score(self, policy_detail: str) -> int:
        """从政策面分析中提取评分"""
        score = 50
        if '政策支持' in policy_detail:
            score += 20
        if '政策限制' in policy_detail or '监管' in policy_detail:
            score -= 20
        return max(0, min(100, score))

    def _calculate_weighted_score(self, llm_score: float, ai_score: int,
                                 tech_score: int) -> float:
        """计算加权总分"""
        return (
            llm_score * 0.5 +
            ai_score * 0.3 +
            tech_score * 0.2
        )

    def _generate_operation_advice(self, weighted_score: float) -> tuple:
        """生成操作建议"""
        if weighted_score >= 75:
            return "强烈买入", "高"
        elif weighted_score >= 65:
            return "买入", "中高"
        elif weighted_score >= 55:
            return "持有", "中"
        elif weighted_score >= 45:
            return "观望", "中低"
        else:
            return "卖出", "低"

    def _predict_trend(self, weighted_score: float, technical_score: int,
                      news_score: int, policy_score: int) -> str:
        """预测趋势"""
        if weighted_score >= 65 and technical_score >= 60 and news_score >= 55:
            return "强势上涨"
        elif weighted_score >= 55:
            return "震荡上行"
        elif weighted_score >= 45:
            return "横盘震荡"
        elif weighted_score >= 35:
            return "震荡下行"
        else:
            return "弱势下跌"

    def _generate_recommendation_reason(
        self,
        stock_name: str,
        code: str,
        technical_detail: str,
        fundamental_detail: str,
        news_detail: str,
        policy_detail: str,
        market_detail: str,
        weighted_score: float,
        operation_advice: str,
        ai_analysis: Optional[Dict],
    ) -> str:
        """内部留存用简要结论（微信等渠道不展示长篇推理，故不再单独请求 LLM 综述）。"""
        reasons = []
        reasons.extend(self._extract_technical_reason(technical_detail))
        reasons.extend(self._extract_fundamental_reason(fundamental_detail))
        reasons.extend(self._extract_news_reason(news_detail))
        reasons.extend(self._extract_policy_reason(policy_detail))
        reasons.extend(self._extract_market_reason(market_detail))

        summary = self._get_score_summary(weighted_score, operation_advice)
        all_reasons = "；".join(reasons)
        return f"{all_reasons}。{summary}"

    def _extract_technical_reason(self, technical_detail: str) -> List[str]:
        """提取技术面推理"""
        reasons = []
        if '看涨' in technical_detail and '金叉' in technical_detail:
            if '看跌' in technical_detail or '死叉' in technical_detail:
                reasons.append("技术面多空交织，MACD金叉但KDJ死叉，短期震荡概率大")
            else:
                reasons.append("技术面向好，MACD金叉看涨")
        elif '看跌' in technical_detail or '死叉' in technical_detail:
            reasons.append("技术面偏弱，短期承压")
        else:
            reasons.append("技术面中性")
        return reasons

    def _extract_fundamental_reason(self, fundamental_detail: str) -> List[str]:
        """提取基本面推理"""
        reasons = []
        if '优秀' in fundamental_detail or '良好' in fundamental_detail:
            reasons.append("基本面扎实，具有投资价值")
        elif '较差' in fundamental_detail or '不足' in fundamental_detail:
            reasons.append("基本面欠佳，存在业绩风险")
        elif '无基本面数据' in fundamental_detail:
            reasons.append("缺乏基本面数据支撑")
        return reasons

    def _extract_news_reason(self, news_detail: str) -> List[str]:
        """提取消息面推理"""
        reasons = []
        if '积极' in news_detail or '利好' in news_detail:
            reasons.append("消息面有利好因素")
        elif '消极' in news_detail or '利空' in news_detail:
            reasons.append("消息面存在利空")
        else:
            reasons.append("消息面中性")
        return reasons

    def _extract_policy_reason(self, policy_detail: str) -> List[str]:
        """提取政策面推理"""
        reasons = []
        if '政策支持' in policy_detail:
            reasons.append("政策面有支持")
        elif '政策限制' in policy_detail or '监管' in policy_detail:
            reasons.append("政策面存在不确定性")
        return reasons

    def _extract_market_reason(self, market_detail: str) -> List[str]:
        """提取市场环境推理"""
        reasons = []
        if '量能显著放大' in market_detail:
            reasons.append("量能放大，市场活跃度高")
        elif '量能显著萎缩' in market_detail:
            reasons.append("量能萎缩，市场活跃度低")
        return reasons

    def _get_score_summary(self, weighted_score: float, operation_advice: str) -> str:
        """获取评分摘要"""
        if weighted_score >= 70:
            return f"综合评分{weighted_score:.1f}分，多维度分析显示积极信号，建议{operation_advice}。"
        elif weighted_score >= 55:
            return f"综合评分{weighted_score:.1f}分，多维度分析显示中性偏多，建议{operation_advice}。"
        elif weighted_score >= 45:
            return f"综合评分{weighted_score:.1f}分，多维度分析显示中性偏空，建议{operation_advice}。"
        else:
            return f"综合评分{weighted_score:.1f}分，多维度分析显示消极信号，建议{operation_advice}。"

    def _generate_risk_warning(self, fundamental_score: int,
                              policy_score: int, market_score: int) -> str:
        """生成风险警告"""
        warnings = []

        if fundamental_score < 40:
            warnings.append("基本面较差，存在业绩风险")

        if policy_score < 40:
            warnings.append("政策面不利，存在政策风险")

        if market_score < 40:
            warnings.append("市场环境不佳，存在流动性风险")

        if not warnings:
            warnings.append("投资有风险，入市需谨慎")

        return "；".join(warnings)

    def _generate_buy_reason(self, weighted_score: float,
                            technical_detail: str, fundamental_detail: str,
                            news_detail: str, policy_detail: str) -> str:
        """生成买入理由"""
        if weighted_score < 60:
            return "当前不建议买入"

        reasons = []

        if '看涨' in technical_detail or '金叉' in technical_detail:
            reasons.append("技术面出现买入信号")

        if '优秀' in fundamental_detail or '良好' in fundamental_detail:
            reasons.append("基本面表现良好")

        if '积极' in news_detail or '利好' in news_detail:
            reasons.append("消息面有利好因素")

        if '政策支持' in policy_detail:
            reasons.append("政策面有支持")

        return "；".join(reasons) if reasons else "综合评分较高，可考虑买入"

    def _calculate_stars(self, weighted_score: float) -> int:
        """计算星级 0～5（0 为无星：加权综合过低）。"""
        if weighted_score < self.WEIGHTED_SCORE_ZERO_STAR_BELOW:
            return 0
        if weighted_score >= 85:
            return 5
        if weighted_score >= 75:
            return 4
        if weighted_score >= 60:
            return 3
        if weighted_score >= 45:
            return 2
        return 1

    @staticmethod
    def _clip(text: str, max_len: int = 180) -> str:
        t = (text or "").replace("\n", " ").strip()
        if len(t) <= max_len:
            return t
        return t[: max_len - 1] + "…"

    def _generate_star_reason(self, stars: int, weighted_score: float,
                             llm_score: float, ai_score: int, tech_score: int,
                             technical_detail: str, fundamental_detail: str,
                             news_detail: str, policy_detail: str,
                             market_detail: str,
                             news_headlines: str = "",
                             policy_info: str = "",
                             macro_info: str = "",
                             llm_news_reason: str = "",
                             ai_analysis: Optional[Dict] = None) -> str:
        """生成打星理由：五星须写清「凭什么五星」；不写权重公式与交叉验证等长篇推理。"""
        star_desc = {
            5: "五星评级，强烈推荐",
            4: "四星评级，值得关注",
            3: "三星评级，中性评价",
            2: "二星评级，谨慎参与",
            1: "一星评级，不建议参与",
            0: "无星，综合极差档（加权分低于模型内部门槛），不建议关注",
        }

        if stars == 5:
            lines = [
                "【五星依据】加权综合达到优秀档（约"
                f"{weighted_score:.0f}分，内部模型口径），各维度要点如下："
            ]
            td = technical_detail if technical_detail and technical_detail != "N/A" else "暂无有效技术描述"
            fd = fundamental_detail if fundamental_detail and fundamental_detail != "N/A" else "暂无有效基本面数据"
            lines.append(f"①技术：{self._clip(td, 200)}")
            lines.append(f"②基本面：{self._clip(fd, 200)}")
            if llm_news_reason:
                lines.append(f"③新闻解读（Gemini/LLM）：{self._clip(llm_news_reason, 220)}")
            else:
                nd = news_detail if news_detail and news_detail != "N/A" else "消息面中性或信息不足"
                nh = f" 标题摘要：{self._clip(news_headlines, 120)}" if news_headlines else ""
                lines.append(f"③消息面：{self._clip(nd, 160)}{nh}")
            pd = policy_detail if policy_detail and policy_detail != "N/A" else "政策面影响不明显"
            lines.append(f"④政策：{self._clip(pd, 140)}")
            if policy_info:
                lines.append(f"   政策关键词：{self._clip(policy_info, 120)}")
            md = market_detail if market_detail and market_detail != "N/A" else "市场环境一般"
            lines.append(f"⑤市场流动性：{self._clip(md, 140)}")
            if macro_info:
                lines.append(f"⑥宏观线索：{self._clip(macro_info, 160)}")
            if ai_analysis:
                lines.append(
                    "⑦同步参考AI插件：信号="
                    f"{ai_analysis.get('ai_buy_signal', 'N/A')}，评分="
                    f"{ai_analysis.get('ai_signal_score', 'N/A')}。"
                )
            lines.append(
                "【结论】多维度同时支撑或无明显短板，故授予五星（全市场五星名额最多保留2只，超出将降为四星）。"
            )
            return " ".join(lines)

        reasons = [star_desc.get(stars, "评级未知")]

        analysis_reasons = []
        if technical_detail and technical_detail != "N/A":
            tech_reason = self._analyze_technical_reason(technical_detail)
            if tech_reason:
                analysis_reasons.append(f"【技术面】{tech_reason}")
        if fundamental_detail and fundamental_detail != "N/A":
            fund_reason = self._analyze_fundamental_reason(fundamental_detail)
            if fund_reason:
                analysis_reasons.append(f"【基本面】{fund_reason}")
        if news_detail and news_detail != "N/A":
            news_reason = self._analyze_news_reason(news_detail, news_headlines)
            if news_reason:
                analysis_reasons.append(f"【消息面】{news_reason}")
        if policy_detail and policy_detail != "N/A":
            policy_reason = self._analyze_policy_reason(policy_detail, policy_info)
            if policy_reason:
                analysis_reasons.append(f"【政策面】{policy_reason}")
        if market_detail and market_detail != "N/A":
            market_reason = self._analyze_market_reason(market_detail)
            if market_reason:
                analysis_reasons.append(f"【市场环境】{market_reason}")
        if macro_info:
            analysis_reasons.append(f"【宏观环境】{self._clip(macro_info, 200)}")
        if llm_news_reason:
            analysis_reasons.append(f"【新闻要点】{self._clip(llm_news_reason, 200)}")
        elif not self.deepseek_analyzer:
            analysis_reasons.append("【说明】未配置 LLM 时新闻为关键词摘要")

        reasons.append(f"加权综合约{weighted_score:.0f}分（模型内部口径，非投资建议）")
        reasons.extend(analysis_reasons)
        final_advice = self._generate_final_advice(
            stars, weighted_score, technical_detail, fundamental_detail, news_detail, policy_detail
        )
        reasons.append(final_advice)
        return "；".join(reasons)
    
    def _generate_final_advice(self, stars: int, weighted_score: float, 
                             technical_detail: str, fundamental_detail: str, 
                             news_detail: str, policy_detail: str) -> str:
        """生成最终建议（根据个股情况）"""
        if stars <= 0:
            return (
                "加权综合处于极低档，技术/基本面/情绪等至少一端明显偏弱，"
                "不建议作为重点标的；若已持仓宜严控仓位。"
            )
        if stars >= 4:
            if '金叉' in technical_detail and '利好' in news_detail:
                return "技术面与消息面共振，短期上涨概率大，建议积极买入"
            elif 'ROE优秀' in fundamental_detail and '政策支持' in policy_detail:
                return "基本面与政策面支撑强劲，长期价值凸显，建议长期持有"
            else:
                return "综合各维度分析，当前具备较好投资价值，建议积极关注或买入"
        elif stars >= 3:
            if '金叉' in technical_detail and '营收负增长' in fundamental_detail:
                return "技术面向好但基本面存在隐患，建议短线操作"
            elif 'ROE优秀' in fundamental_detail and '利空' in news_detail:
                return "基本面扎实但消息面不利，建议逢低布局"
            else:
                return "综合各维度分析，当前中性偏多，建议持有或观望"
        else:
            if '死叉' in technical_detail or '空头' in technical_detail:
                return "技术面走弱，建议观望或减仓"
            elif 'ROE较差' in fundamental_detail or '营收负增长' in fundamental_detail:
                return "基本面欠佳，建议回避"
            else:
                return "综合各维度分析，当前风险较高，建议谨慎参与或观望"
    
    def _analyze_technical_reason(self, technical_detail: str) -> str:
        """分析技术面推理"""
        reasons = []
        
        if 'MACD金叉' in technical_detail:
            reasons.append("MACD金叉形成，中期趋势向好")
        elif 'MACD死叉' in technical_detail:
            reasons.append("MACD死叉形成，中期趋势转弱")
        
        if 'KDJ多头' in technical_detail:
            reasons.append("KDJ处于多头区域，短期动能强劲")
        elif 'KDJ空头' in technical_detail:
            reasons.append("KDJ处于空头区域，短期动能不足")
        
        if 'RSI超买' in technical_detail:
            reasons.append("RSI超买，短期可能回调")
        elif 'RSI超卖' in technical_detail:
            reasons.append("RSI超卖，短期可能反弹")
        
        if '均线多头' in technical_detail:
            reasons.append("均线多头排列，长期趋势向上")
        elif '均线空头' in technical_detail:
            reasons.append("均线空头排列，长期趋势向下")
        
        if not reasons:
            return technical_detail
        return "；".join(reasons)
    
    def _analyze_fundamental_reason(self, fundamental_detail: str) -> str:
        """分析基本面推理"""
        reasons = []
        
        if 'ROE' in fundamental_detail:
            if '高于行业平均' in fundamental_detail:
                reasons.append("ROE高于行业平均，盈利能力较强")
            elif '低于行业平均' in fundamental_detail:
                reasons.append("ROE低于行业平均，盈利能力较弱")
        
        if 'PE' in fundamental_detail:
            if '估值合理' in fundamental_detail:
                reasons.append("PE估值合理，安全边际较高")
            elif '估值偏高' in fundamental_detail:
                reasons.append("PE估值偏高，存在调整风险")
            elif '估值偏低' in fundamental_detail:
                reasons.append("PE估值偏低，具有投资价值")
        
        if '营收增长' in fundamental_detail:
            if '大幅增长' in fundamental_detail:
                reasons.append("营收大幅增长，成长动能强劲")
            elif '稳定增长' in fundamental_detail:
                reasons.append("营收稳定增长，经营状况良好")
            elif '负增长' in fundamental_detail:
                reasons.append("营收负增长，成长动力不足")
        
        if not reasons:
            return fundamental_detail
        return "；".join(reasons)
    
    def _analyze_news_reason(self, news_detail: str, news_headlines: str) -> str:
        """分析消息面推理"""
        reasons = []
        
        if '利好' in news_detail or '积极' in news_detail:
            if '业绩预增' in news_detail:
                reasons.append("业绩预增，基本面预期向好")
            if '大订单' in news_detail:
                reasons.append("获得大订单，未来业绩有保障")
            if '扩产' in news_detail:
                reasons.append("产能扩张，长期增长可期")
            if '政策支持' in news_detail:
                reasons.append("政策支持，行业发展受益")
        elif '利空' in news_detail or '消极' in news_detail:
            if '业绩下滑' in news_detail:
                reasons.append("业绩下滑，基本面承压")
            if '减持' in news_detail:
                reasons.append("股东减持，短期压力较大")
            if '监管' in news_detail:
                reasons.append("监管压力，行业不确定性增加")
        
        if news_headlines:
            reasons.append(f"关键事件：{news_headlines}")
        
        if not reasons:
            return news_detail
        return "；".join(reasons)
    
    def _analyze_policy_reason(self, policy_detail: str, policy_info: str) -> str:
        """分析政策面推理"""
        reasons = []
        
        if '政策支持' in policy_detail:
            reasons.append("政策支持，行业发展环境良好")
        elif '政策收紧' in policy_detail:
            reasons.append("政策收紧，行业面临调整压力")
        
        if policy_info:
            reasons.append(f"具体政策：{policy_info}")
        
        if not reasons:
            return policy_detail
        return "；".join(reasons)
    
    def _analyze_market_reason(self, market_detail: str) -> str:
        """分析市场环境推理"""
        if '量能显著放大' in market_detail:
            return "量能显著放大，市场活跃度高，资金流入明显"
        elif '成交额充沛' in market_detail:
            return "成交额充沛，流动性好，交易活跃"
        elif '量能萎缩' in market_detail:
            return "量能萎缩，市场活跃度低，资金参与意愿不强"
        elif '成交额低迷' in market_detail:
            return "成交额低迷，流动性不足，短期波动可能较大"
        else:
            return market_detail

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
            stars=3,
            star_reason="分析失败，无法给出打星理由",
            error_message=error_message
        )
