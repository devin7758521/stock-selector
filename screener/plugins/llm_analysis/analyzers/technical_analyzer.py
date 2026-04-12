# -*- coding: utf-8 -*-
"""
技术面分析器

负责股票技术指标分析，包括MACD、KDJ、RSI、均线等指标的分析和评分。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("stock_selector.analyzer.technical")


class TechnicalAnalyzer:
    """
    技术面分析器

    分析维度：
    - MACD指标（金叉/死叉判断）
    - KDJ指标（超买/超卖判断）
    - RSI指标（相对强弱指标）
    - 均线系统（多头/空头排列）
    """

    def analyze(self, technical_analysis: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[str, int]:
        """
        分析技术面

        Args:
            technical_analysis: 技术分析数据
            context: 股票上下文数据

        Returns:
            Tuple[分析详情, 技术评分]
        """
        if not technical_analysis:
            return "无技术指标数据", 50

        details = []
        score = 50

        details, score = self._analyze_macd(technical_analysis, details, score)
        details, score = self._analyze_kdj(technical_analysis, details, score)
        details, score = self._analyze_rsi(technical_analysis, details, score)
        details, score = self._analyze_ma(context, details, score)

        return "；".join(details), max(0, min(100, score))

    def _analyze_macd(self, technical_analysis: Dict[str, Any],
                      details: list, score: int) -> Tuple[list, int]:
        """分析MACD指标"""
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

        return details, score

    def _analyze_kdj(self, technical_analysis: Dict[str, Any],
                      details: list, score: int) -> Tuple[list, int]:
        """分析KDJ指标"""
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

        return details, score

    def _analyze_rsi(self, technical_analysis: Dict[str, Any],
                      details: list, score: int) -> Tuple[list, int]:
        """分析RSI指标"""
        rsi = technical_analysis.get('rsi', 50)
        if rsi > 70:
            details.append(f"RSI超买({rsi:.1f})，短期有回调风险")
            score -= 5
        elif rsi < 30:
            details.append(f"RSI超卖({rsi:.1f})，短期有反弹机会")
            score += 5
        else:
            details.append(f"RSI处于正常区间({rsi:.1f})")

        return details, score

    def _analyze_ma(self, context: Dict[str, Any],
                     details: list, score: int) -> Tuple[list, int]:
        """分析均线系统"""
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

        return details, score

    def extract_score(self, technical_analysis: Dict[str, Any]) -> int:
        """从技术分析中提取评分"""
        score = 50

        if not technical_analysis:
            return score

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
