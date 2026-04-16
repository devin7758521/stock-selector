# -*- coding: utf-8 -*-
"""
市场环境分析器

负责分析大盘走势、板块轮动、资金流向等市场整体环境因素。
包含板块联动分析：强势板块中的个股获得额外加分。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger("stock_selector.analyzer.market")


class MarketEnvironmentAnalyzer:
    """
    市场环境分析器

    分析维度：
    - 量能分析（放量/缩量）
    - 成交额分析（流动性判断）
    - 板块联动分析（强势板块加分）
    """

    def __init__(self, sector_results: Optional[List[Dict]] = None):
        self.sector_results = sector_results or []

    def analyze(self, context: Dict[str, Any]) -> Tuple[str, int]:
        details = []
        score = 50

        details, score = self._analyze_volume(context, details, score)
        details, score = self._analyze_sector(context, details, score)

        if not details:
            details.append("市场环境分析数据不足")

        return "；".join(details), score

    def _analyze_volume(self, context: Dict[str, Any],
                        details: list, score: int) -> Tuple[list, int]:
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

    def _analyze_sector(self, context: Dict[str, Any],
                        details: list, score: int) -> Tuple[list, int]:
        if not self.sector_results:
            return details, score

        industry = context.get("industry", "")
        stock_name = context.get("stock_name", "")

        matched_sectors = []
        for s in self.sector_results:
            sname = s.get("name", "")
            if industry and (industry in sname or sname in industry):
                matched_sectors.append(s)
            elif stock_name and sname in stock_name:
                matched_sectors.append(s)

        if matched_sectors:
            best = matched_sectors[0]
            trend = best.get("sector_trend", "")
            dev = best.get("vol_deviation_pct", 0)

            if "放量上行" in trend:
                details.append(f"所属板块「{best['name']}」{trend}，板块联动利好")
                score += 10
            elif "温和上行" in trend:
                details.append(f"所属板块「{best['name']}」{trend}，板块联动偏多")
                score += 5
            elif "缩量整理" in trend:
                details.append(f"所属板块「{best['name']}」{trend}，板块联动中性")
            elif "缩量下行" in trend:
                details.append(f"所属板块「{best['name']}」{trend}，板块联动偏空")
                score -= 5
        else:
            strong_names = [s["name"] for s in self.sector_results[:5]]
            details.append(f"当前强势板块: {'、'.join(strong_names)}")

        return details, score

    def calculate_market_score(self, context: Dict[str, Any]) -> int:
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

        _, sector_bonus = self._analyze_sector(context, [], 0)
        score += sector_bonus

        return max(0, min(100, score))
