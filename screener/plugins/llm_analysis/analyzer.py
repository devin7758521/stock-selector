# -*- coding: utf-8 -*-
"""
LLM 分析器模块

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

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
    stars: int  # 五星评级 1-5
    star_reason: str  # 打星理由
    error_message: Optional[str] = None


class LLMAnalyzer:
    """
    LLM 分析器
    用于分析股票数据和新闻信息
    """
    
    def __init__(self):
        """初始化分析器"""
        self.model_used = "Local Analyzer"
    
    def analyze(self, context: Dict[str, Any], news_context: Optional[str]) -> AnalysisResult:
        """
        分析股票数据
        
        Args:
            context: 股票上下文数据
            news_context: 新闻上下文
            
        Returns:
            分析结果
        """
        try:
            # 从上下文获取数据
            stock_name = context.get('stock_name', '未知股票')
            code = context.get('code', '未知代码')
            
            # 简单的情绪分析
            sentiment_score = 50  # 默认中性
            
            # 基于新闻的简单分析
            news_summary = """无新闻信息"""
            if news_context:
                news_summary = news_context
                # 简单的新闻情绪分析
                positive_words = ['上涨', '利好', '增长', '盈利', '创新', '突破', '政策支持']
                negative_words = ['下跌', '利空', '亏损', '下滑', '风险', '警告', '政策限制']
                
                positive_count = sum(1 for word in positive_words if word in news_context)
                negative_count = sum(1 for word in negative_words if word in news_context)
                
                if positive_count > negative_count:
                    sentiment_score = min(100, 50 + positive_count * 10)
                elif negative_count > positive_count:
                    sentiment_score = max(0, 50 - negative_count * 10)
            
            # 基于情绪分的操作建议
            if sentiment_score >= 70:
                operation_advice = "买入"
                confidence_level = "高"
            elif sentiment_score >= 50:
                operation_advice = "持有"
                confidence_level = "中"
            else:
                operation_advice = "卖出"
                confidence_level = "低"
            
            # 生成分析摘要
            analysis_summary = f"{stock_name}({code}) 的情绪分析结果为 {sentiment_score} 分，建议 {operation_advice}，置信度 {confidence_level}。"
            
            # 生成买入理由
            buy_reason = ""
            if sentiment_score >= 70:
                buy_reason = f"基于新闻分析，{stock_name} 近期有积极因素，建议买入。"
            
            # 生成风险警告
            risk_warning = "投资有风险，入市需谨慎。"
            
            # 生成趋势预测
            trend_prediction = "看涨" if sentiment_score >= 60 else "看跌" if sentiment_score <= 40 else "震荡"
            
            # 计算五星评级
            stars = self._calculate_stars(sentiment_score)
            
            # 生成打星理由
            star_reason = self._generate_star_reason(sentiment_score, trend_prediction, operation_advice, news_context)
            
            return AnalysisResult(
                sentiment_score=sentiment_score,
                trend_prediction=trend_prediction,
                operation_advice=operation_advice,
                confidence_level=confidence_level,
                analysis_summary=analysis_summary,
                news_summary=news_summary,
                risk_warning=risk_warning,
                buy_reason=buy_reason,
                model_used=self.model_used,
                success=True,
                stars=stars,
                star_reason=star_reason
            )
            
        except Exception as e:
            logger.error(f"分析失败: {e}")
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
    
    def _calculate_stars(self, sentiment_score: int) -> int:
        """
        计算五星评级
        
        Args:
            sentiment_score: 情绪分
            
        Returns:
            星级 1-5
        """
        if sentiment_score >= 90:
            return 5
        elif sentiment_score >= 75:
            return 4
        elif sentiment_score >= 60:
            return 3
        elif sentiment_score >= 40:
            return 2
        else:
            return 1
    
    def _generate_star_reason(self, sentiment_score: int, trend_prediction: str, operation_advice: str, news_context: Optional[str]) -> str:
        """
        生成打星理由
        
        Args:
            sentiment_score: 情绪分
            trend_prediction: 趋势预测
            operation_advice: 操作建议
            news_context: 新闻上下文
            
        Returns:
            打星理由
        """
        reasons = []
        
        # 根据情绪分
        if sentiment_score >= 90:
            reasons.append("情绪分极高，市场表现强劲")
        elif sentiment_score >= 75:
            reasons.append("情绪分较高，市场表现良好")
        elif sentiment_score >= 60:
            reasons.append("情绪分适中，市场表现稳定")
        elif sentiment_score >= 40:
            reasons.append("情绪分较低，市场表现疲软")
        else:
            reasons.append("情绪分极低，市场表现低迷")
        
        # 根据趋势
        if trend_prediction == "看涨":
            reasons.append("预测趋势为看涨，有望获得收益")
        elif trend_prediction == "看跌":
            reasons.append("预测趋势为看跌，存在风险")
        else:
            reasons.append("预测趋势为震荡，市场较为平稳")
        
        # 根据操作建议
        if operation_advice == "买入":
            reasons.append("操作建议为买入，适合进场")
        elif operation_advice == "卖出":
            reasons.append("操作建议为卖出，建议离场")
        else:
            reasons.append("操作建议为持有，保持观望")
        
        # 根据新闻
        if news_context:
            reasons.append("有相关新闻信息可供参考")
        else:
            reasons.append("暂无相关新闻信息")
        
        return "；".join(reasons)
