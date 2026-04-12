# -*- coding: utf-8 -*-
"""
增强版 LLM 分析器模块

功能：
1. 多维度综合分析（技术面、基本面、消息面、政策面）
2. 权重机制：LLM > AI > 技术指标
3. 国内外财经政治形势分析
4. 详细的推理过程和打星理由
5. 预留真正的LLM API接口（litellm）

Copyright (c) 2026 driverplus. All rights reserved.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json

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
    
    # 新增：详细分析维度
    technical_analysis_detail: str = ""
    fundamental_analysis_detail: str = ""
    news_analysis_detail: str = ""
    policy_analysis_detail: str = ""
    market_environment_analysis: str = ""
    
    # 新增：推荐理由（综合推理后的结论）
    recommendation_reason: str = ""
    
    # 新增：权重计算
    weighted_score: float = 0.0
    llm_weight: float = 0.5  # LLM权重50%
    ai_weight: float = 0.3   # AI权重30%
    technical_weight: float = 0.2  # 技术指标权重20%
    
    error_message: Optional[str] = None


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
    """
    
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
        
        # 如果有API key，尝试初始化litellm
        self.llm_client = None
        if api_key and model != "local":
            try:
                import litellm
                self.llm_client = litellm
                logger.info(f"已初始化LLM客户端: {model}")
            except ImportError:
                logger.warning("litellm未安装，将使用本地分析器")
    
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
            stock_name = context.get('stock_name', '未知股票')
            code = context.get('code', '未知代码')
            
            logger.info(f"开始综合分析: {stock_name} ({code})")
            
            # 1. 技术面分析
            technical_detail, technical_score = self._analyze_technical(
                technical_analysis, context
            )
            
            # 2. 基本面分析
            fundamental_detail, fundamental_score = self._analyze_fundamental(
                fundamental_analysis, context
            )
            
            # 3. 消息面分析
            news_detail, news_score = self._analyze_news(news_context, stock_name, code)
            
            # 4. 政策面分析
            policy_detail, policy_score = self._analyze_policy(context, news_context)
            
            # 5. 市场环境分析
            market_detail, market_score = self._analyze_market_environment(context)
            
            # 6. 综合评分计算（使用权重机制）
            llm_base_score = self._calculate_llm_score(
                technical_score, fundamental_score, news_score, 
                policy_score, market_score
            )
            
            # 7. 如果有AI分析，结合AI评分
            ai_score = 50
            if ai_analysis:
                ai_score = ai_analysis.get('ai_signal_score', 50)
            
            # 8. 如果有技术分析，提取技术评分
            tech_score = 50
            if technical_analysis:
                tech_score = self._extract_technical_score(technical_analysis)
            
            # 9. 计算加权总分
            weighted_score = (
                llm_base_score * 0.5 +  # LLM权重50%
                ai_score * 0.3 +         # AI权重30%
                tech_score * 0.2         # 技术指标权重20%
            )
            
            # 10. 生成操作建议
            operation_advice, confidence_level = self._generate_operation_advice(
                weighted_score, llm_base_score, ai_score, tech_score
            )
            
            # 11. 生成趋势预测
            trend_prediction = self._predict_trend(
                weighted_score, technical_score, news_score, policy_score
            )
            
            # 12. 生成推荐理由（综合推理后的结论）
            recommendation_reason = self._generate_recommendation_reason(
                technical_detail, fundamental_detail, news_detail,
                policy_detail, market_detail, weighted_score,
                operation_advice, trend_prediction
            )
            
            # 13. 生成风险警告
            risk_warning = self._generate_risk_warning(
                fundamental_score, policy_score, market_score
            )
            
            # 14. 生成买入理由
            buy_reason = self._generate_buy_reason(
                weighted_score, technical_detail, fundamental_detail, 
                news_detail, policy_detail
            )
            
            # 15. 计算五星评级
            stars = self._calculate_stars(weighted_score)
            
            # 16. 生成打星理由
            star_reason = self._generate_star_reason(
                stars, weighted_score, llm_base_score, ai_score, tech_score,
                technical_detail, fundamental_detail, news_detail, 
                policy_detail, market_detail
            )
            
            # 17. 生成分析摘要
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
                technical_weight=0.2
            )
            
        except Exception as e:
            logger.error(f"分析失败: {e}", exc_info=True)
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
                error_message=str(e)
            )
    
    def _analyze_technical(self, technical_analysis: Optional[Dict], 
                          context: Dict[str, Any]) -> tuple:
        """技术面分析"""
        if not technical_analysis:
            return "无技术指标数据", 50
        
        details = []
        score = 50
        
        # MACD分析
        macd = technical_analysis.get('macd', {})
        macd_value = macd.get('value', 0)
        macd_histogram = macd.get('histogram', 0)
        
        if macd_value > 0 and macd_histogram > 0:
            details.append(f"MACD金叉且柱状图为正({macd_value:.2f})，技术面看涨")
            score += 10
        elif macd_value < 0 and macd_histogram < 0:
            details.append(f"MACD死叉且柱状图为负({macd_value:.2f})，技术面看跌")
            score -= 10
        else:
            details.append(f"MACD处于震荡状态({macd_value:.2f})")
        
        # KDJ分析
        kdj = technical_analysis.get('kdj', {})
        k = kdj.get('k', 50)
        d = kdj.get('d', 50)
        j = kdj.get('j', 50)
        
        if k > d and j > k:
            details.append(f"KDJ金叉向上(K={k:.1f}, D={d:.1f}, J={j:.1f})，短期看涨")
            score += 8
        elif k < d and j < k:
            details.append(f"KDJ死叉向下(K={k:.1f}, D={d:.1f}, J={j:.1f})，短期看跌")
            score -= 8
        
        # RSI分析
        rsi = technical_analysis.get('rsi', 50)
        if rsi > 70:
            details.append(f"RSI超买({rsi:.1f})，短期有回调风险")
            score -= 5
        elif rsi < 30:
            details.append(f"RSI超卖({rsi:.1f})，短期有反弹机会")
            score += 5
        else:
            details.append(f"RSI处于正常区间({rsi:.1f})")
        
        # 均线分析
        if 'technical' in context:
            tech = context['technical']
            latest_price = tech.get('latest_price', 0)
            ma5 = tech.get('ma5', 0)
            ma10 = tech.get('ma10', 0)
            ma20 = tech.get('ma20', 0)
            
            if latest_price > ma5 > ma10 > ma20:
                details.append("价格站上所有均线，多头排列")
                score += 10
            elif latest_price < ma5 < ma10 < ma20:
                details.append("价格跌破所有均线，空头排列")
                score -= 10
        
        return "；".join(details), max(0, min(100, score))
    
    def _analyze_fundamental(self, fundamental_analysis: Optional[Dict],
                            context: Dict[str, Any]) -> tuple:
        """基本面分析"""
        if not fundamental_analysis:
            return "无基本面数据", 50
        
        details = []
        score = fundamental_analysis.get('score', 50)
        
        # ROE分析
        roe = fundamental_analysis.get('roe', 0)
        if roe > 15:
            details.append(f"ROE优秀({roe:.2f}%)，盈利能力强")
        elif roe > 10:
            details.append(f"ROE良好({roe:.2f}%)，盈利能力尚可")
        elif roe > 5:
            details.append(f"ROE一般({roe:.2f}%)，盈利能力偏弱")
        else:
            details.append(f"ROE较差({roe:.2f}%)，盈利能力不足")
        
        # PE分析
        pe = fundamental_analysis.get('pe', 0)
        if 0 < pe < 15:
            details.append(f"PE估值偏低({pe:.1f})，具有安全边际")
        elif 15 <= pe < 30:
            details.append(f"PE估值合理({pe:.1f})")
        elif pe >= 30:
            details.append(f"PE估值偏高({pe:.1f})，存在估值风险")
        
        # PB分析
        pb = fundamental_analysis.get('pb', 0)
        if 0 < pb < 2:
            details.append(f"PB估值较低({pb:.2f})，具有安全边际")
        elif 2 <= pb < 5:
            details.append(f"PB估值合理({pb:.2f})")
        else:
            details.append(f"PB估值偏高({pb:.2f})")
        
        # 营收增长分析
        revenue_growth = fundamental_analysis.get('revenue_growth', 0)
        if revenue_growth > 30:
            details.append(f"营收高速增长({revenue_growth:.1f}%)，成长性好")
        elif revenue_growth > 15:
            details.append(f"营收稳健增长({revenue_growth:.1f}%)")
        elif revenue_growth > 0:
            details.append(f"营收小幅增长({revenue_growth:.1f}%)")
        else:
            details.append(f"营收负增长({revenue_growth:.1f}%)，成长性欠佳")
        
        return "；".join(details), score
    
    def _analyze_news(self, news_context: Optional[str], 
                     stock_name: str, code: str) -> tuple:
        """消息面分析"""
        if not news_context:
            return f"暂无{stock_name}({code})相关新闻信息", 50
        
        details = []
        score = 50
        
        # 关键词分析
        positive_keywords = {
            '上涨': 2, '利好': 3, '增长': 2, '盈利': 2, '创新': 1,
            '突破': 2, '政策支持': 3, '订单': 1, '合作': 1, '并购': 2,
            '业绩预增': 3, '分红': 2, '回购': 2, '增持': 2
        }
        
        negative_keywords = {
            '下跌': -2, '利空': -3, '亏损': -2, '下滑': -2, '风险': -1,
            '警告': -2, '政策限制': -3, '诉讼': -2, '违规': -3, '减持': -1,
            '业绩预亏': -3, '质押': -1, '冻结': -2
        }
        
        positive_score = 0
        negative_score = 0
        
        for keyword, weight in positive_keywords.items():
            count = news_context.count(keyword)
            if count > 0:
                positive_score += weight * count
                details.append(f"发现积极关键词'{keyword}'({count}次)")
        
        for keyword, weight in negative_keywords.items():
            count = news_context.count(keyword)
            if count > 0:
                negative_score += weight * count
                details.append(f"发现消极关键词'{keyword}'({count}次)")
        
        # 计算新闻情绪分
        total_keywords = positive_score + abs(negative_score)
        if total_keywords > 0:
            sentiment_ratio = (positive_score + abs(negative_score)) / (positive_score + abs(negative_score) + 1)
            score = 50 + (positive_score + negative_score) * 2
            score = max(0, min(100, score))
        
        if not details:
            details.append("新闻内容中性，无明显利好利空")
        
        return "；".join(details), score
    
    def _analyze_policy(self, context: Dict[str, Any], 
                       news_context: Optional[str]) -> tuple:
        """政策面分析"""
        details = []
        score = 50
        
        # 行业政策关键词
        industry_keywords = {
            '新能源': 1, '芯片': 1, '人工智能': 1, '5G': 1, '半导体': 1,
            '医药': 0, '消费': 0, '金融': 0, '地产': -1, '教育': -1
        }
        
        # 政策支持关键词
        support_keywords = ['政策支持', '国家战略', '产业扶持', '补贴', '减税']
        # 政策限制关键词
        restrict_keywords = ['监管', '限制', '整顿', '处罚', '收紧']
        
        # 从新闻中提取政策信息
        if news_context:
            for keyword in support_keywords:
                if keyword in news_context:
                    details.append(f"发现政策支持信号: {keyword}")
                    score += 5
            
            for keyword in restrict_keywords:
                if keyword in news_context:
                    details.append(f"发现政策限制信号: {keyword}")
                    score -= 5
        
        # 国内外财经形势分析
        macro_keywords = {
            '美联储': -1, '加息': -1, '降息': 1, '通胀': -1,
            'GDP': 0, '经济复苏': 1, '经济下行': -1, '贸易战': -2
        }
        
        if news_context:
            for keyword, weight in macro_keywords.items():
                if keyword in news_context:
                    details.append(f"关注宏观经济因素: {keyword}")
                    score += weight * 3
        
        if not details:
            details.append("暂无明显政策面影响")
        
        return "；".join(details), max(0, min(100, score))
    
    def _analyze_market_environment(self, context: Dict[str, Any]) -> tuple:
        """市场环境分析"""
        details = []
        score = 50
        
        # 从context中提取市场数据
        if 'volume_analysis' in context:
            vol_analysis = context['volume_analysis']
            vol_deviation = vol_analysis.get('vol_deviation_pct', 0)
            daily_amount = vol_analysis.get('daily_amount_yi', 0)
            
            if vol_deviation > 5:
                details.append(f"量能显著放大({vol_deviation:.2f}%)，市场活跃度高")
                score += 5
            elif vol_deviation < -5:
                details.append(f"量能显著萎缩({vol_deviation:.2f}%)，市场活跃度低")
                score -= 5
            
            if daily_amount > 10:
                details.append(f"成交额充沛({daily_amount:.2f}亿)，流动性好")
                score += 3
        
        # 大盘走势判断（简化版）
        # 实际应用中应该获取大盘指数数据
        details.append("建议结合大盘走势综合判断")
        
        if not details:
            details.append("市场环境分析数据不足")
        
        return "；".join(details), score
    
    def _calculate_llm_score(self, technical_score: int, fundamental_score: int,
                            news_score: int, policy_score: int, 
                            market_score: int) -> float:
        """计算LLM综合评分"""
        # LLM综合评分 = 技术面*20% + 基本面*30% + 消息面*25% + 政策面*15% + 市场环境*10%
        llm_score = (
            technical_score * 0.20 +
            fundamental_score * 0.30 +
            news_score * 0.25 +
            policy_score * 0.15 +
            market_score * 0.10
        )
        return llm_score
    
    def _extract_technical_score(self, technical_analysis: Dict) -> int:
        """从技术分析中提取评分"""
        score = 50
        
        macd = technical_analysis.get('macd', {})
        if macd.get('value', 0) > 0:
            score += 10
        
        kdj = technical_analysis.get('kdj', {})
        if kdj.get('k', 50) > kdj.get('d', 50):
            score += 5
        
        rsi = technical_analysis.get('rsi', 50)
        if 30 < rsi < 70:
            score += 5
        
        return max(0, min(100, score))
    
    def _generate_recommendation_reason(self, technical_detail: str, 
                                        fundamental_detail: str,
                                        news_detail: str, policy_detail: str,
                                        market_detail: str, weighted_score: float,
                                        operation_advice: str, 
                                        trend_prediction: str) -> str:
        """
        生成推荐理由（综合推理后的结论）
        
        这个方法会综合技术面、基本面、消息面、政策面、市场环境等多维度信息，
        进行推理分析，给出简洁明了的推荐理由。
        """
        reasons = []
        
        # 1. 技术面推理
        if '看涨' in technical_detail and '金叉' in technical_detail:
            if '看跌' in technical_detail or '死叉' in technical_detail:
                reasons.append("技术面多空交织，MACD金叉但KDJ死叉，短期震荡概率大")
            else:
                reasons.append("技术面向好，MACD金叉看涨")
        elif '看跌' in technical_detail or '死叉' in technical_detail:
            reasons.append("技术面偏弱，短期承压")
        else:
            reasons.append("技术面中性")
        
        # 2. 基本面推理
        if '优秀' in fundamental_detail or '良好' in fundamental_detail:
            reasons.append("基本面扎实，具有投资价值")
        elif '较差' in fundamental_detail or '不足' in fundamental_detail:
            reasons.append("基本面欠佳，存在业绩风险")
        elif '无基本面数据' in fundamental_detail:
            reasons.append("缺乏基本面数据支撑")
        
        # 3. 消息面推理
        if '积极' in news_detail or '利好' in news_detail:
            reasons.append("消息面有利好因素")
        elif '消极' in news_detail or '利空' in news_detail:
            reasons.append("消息面存在利空")
        else:
            reasons.append("消息面中性")
        
        # 4. 政策面推理
        if '政策支持' in policy_detail:
            reasons.append("政策面有支持")
        elif '政策限制' in policy_detail or '监管' in policy_detail:
            reasons.append("政策面存在不确定性")
        
        # 5. 市场环境推理
        if '量能显著放大' in market_detail:
            reasons.append("量能放大，市场活跃度高")
        elif '量能显著萎缩' in market_detail:
            reasons.append("量能萎缩，市场活跃度低")
        
        # 6. 综合判断
        if weighted_score >= 70:
            summary = f"综合评分{weighted_score:.1f}分，多维度分析显示积极信号，建议{operation_advice}。"
        elif weighted_score >= 55:
            summary = f"综合评分{weighted_score:.1f}分，多维度分析显示中性偏多，建议{operation_advice}。"
        elif weighted_score >= 45:
            summary = f"综合评分{weighted_score:.1f}分，多维度分析显示中性偏空，建议{operation_advice}。"
        else:
            summary = f"综合评分{weighted_score:.1f}分，多维度分析显示消极信号，建议{operation_advice}。"
        
        # 组合所有理由
        all_reasons = "；".join(reasons)
        return f"{all_reasons}。{summary}"
    
    def _generate_operation_advice(self, weighted_score: float, 
                                   llm_score: float, ai_score: int,
                                   tech_score: int) -> tuple:
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
        """计算五星评级"""
        if weighted_score >= 85:
            return 5
        elif weighted_score >= 75:
            return 4
        elif weighted_score >= 60:
            return 3
        elif weighted_score >= 45:
            return 2
        else:
            return 1
    
    def _generate_star_reason(self, stars: int, weighted_score: float,
                             llm_score: float, ai_score: int, tech_score: int,
                             technical_detail: str, fundamental_detail: str,
                             news_detail: str, policy_detail: str,
                             market_detail: str) -> str:
        """生成打星理由"""
        reasons = []
        
        # 星级总体评价
        star_desc = {
            5: "五星评级，强烈推荐",
            4: "四星评级，值得关注",
            3: "三星评级，中性评价",
            2: "二星评级，谨慎参与",
            1: "一星评级，不建议参与"
        }
        reasons.append(star_desc.get(stars, "评级未知"))
        
        # 评分依据
        reasons.append(f"加权总分{weighted_score:.1f}分（LLM:{llm_score:.1f}×50% + AI:{ai_score}×30% + 技术:{tech_score}×20%）")
        
        # 各维度亮点
        if '看涨' in technical_detail or '金叉' in technical_detail:
            reasons.append("技术面向好")
        
        if '优秀' in fundamental_detail or '良好' in fundamental_detail:
            reasons.append("基本面扎实")
        
        if '积极' in news_detail or '利好' in news_detail:
            reasons.append("消息面积极")
        
        if '政策支持' in policy_detail:
            reasons.append("政策面支持")
        
        return "；".join(reasons)
    
    def _generate_summary(self, stock_name: str, code: str,
                         weighted_score: float, operation_advice: str,
                         confidence_level: str, trend_prediction: str) -> str:
        """生成分析摘要"""
        return f"{stock_name}({code})综合评分{weighted_score:.1f}分，建议{operation_advice}，置信度{confidence_level}，预测趋势{trend_prediction}。"
