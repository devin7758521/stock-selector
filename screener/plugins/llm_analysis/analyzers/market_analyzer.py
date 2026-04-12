# -*- coding: utf-8 -*-
"""
市场环境分析器

负责分析大盘走势、板块轮动、资金流向等市场整体环境因素。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("stock_selector.analyzer.market")


class MarketEnvironmentAnalyzer:
    """
    市场环境分析器

    分析维度：
    - 量能分析（放量/缩量）
    - 成交额分析（流动性判断）
    - 大盘走势结合
    """

    def analyze(self, context: Dict[str, Any]) -> Tuple[str, int]:
        """
        分析市场环境

        Args:
            context: 股票上下文数据

        Returns:
            Tuple[分析详情, 市场环境评分]
        """
        details = []
        score = 50

        details, score = self._analyze_volume(context, details, score)
        details.append("建议结合大盘走势综合判断")

        if not details:
            details.append("市场环境分析数据不足")

        return "；".join(details), score

    def _analyze_volume(self, context: Dict[str, Any],
                        details: list, score: int) -> Tuple[list, int]:
        """分析量能和市场环境"""
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

        return details, score

    def calculate_market_score(self, context: Dict[str, Any]) -> int:
        """计算市场环境评分"""
        score = 50

        if 'volume_analysis' in context:
            vol_analysis = context['volume_analysis']
            vol_deviation = vol_analysis.get('vol_deviation_pct', 0)
            daily_amount = vol_analysis.get('daily_amount_yi', 0)

            if vol_deviation > 5:
                score += 5
            elif vol_deviation < -5:
                score -= 5

            if daily_amount > 10:
                score += 3

        return max(0, min(100, score))
