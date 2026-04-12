# -*- coding: utf-8 -*-
"""
基本面分析器

负责股票基本面分析，包括ROE、PE、PB、营收增长等财务指标的分析和评分。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("stock_selector.analyzer.fundamental")


class FundamentalAnalyzer:
    """
    基本面分析器

    分析维度：
    - ROE（净资产收益率）
    - PE（市盈率）
    - PB（市净率）
    - 营收增长率
    """

    def analyze(self, fundamental_analysis: Dict[str, Any],
                context: Dict[str, Any]) -> Tuple[str, int]:
        """
        分析基本面

        Args:
            fundamental_analysis: 基本面分析数据
            context: 股票上下文数据

        Returns:
            Tuple[分析详情, 基本面评分]
        """
        if not fundamental_analysis:
            return "无基本面数据", 50

        details = []
        score = fundamental_analysis.get('score', 50)

        details, score = self._analyze_roe(fundamental_analysis, details, score)
        details, score = self._analyze_pe(fundamental_analysis, details, score)
        details, score = self._analyze_pb(fundamental_analysis, details, score)
        details, score = self._analyze_revenue_growth(fundamental_analysis, details, score)

        return "；".join(details), score

    def _analyze_roe(self, fundamental_analysis: Dict[str, Any],
                     details: list, score: int) -> Tuple[list, int]:
        """分析ROE指标"""
        roe = fundamental_analysis.get('roe', 0)
        if roe > 15:
            details.append(f"ROE优秀({roe:.2f}%)，盈利能力强")
            score += 15
        elif roe > 10:
            details.append(f"ROE良好({roe:.2f}%)，盈利能力尚可")
            score += 10
        elif roe > 5:
            details.append(f"ROE一般({roe:.2f}%)，盈利能力偏弱")
            score += 5
        else:
            details.append(f"ROE较差({roe:.2f}%)，盈利能力不足")
            score -= 5

        return details, score

    def _analyze_pe(self, fundamental_analysis: Dict[str, Any],
                     details: list, score: int) -> Tuple[list, int]:
        """分析PE指标"""
        pe = fundamental_analysis.get('pe', 0)
        if 0 < pe < 15:
            details.append(f"PE估值偏低({pe:.1f})，具有安全边际")
            score += 10
        elif 15 <= pe < 30:
            details.append(f"PE估值合理({pe:.1f})")
            score += 5
        elif pe >= 30:
            details.append(f"PE估值偏高({pe:.1f})，存在估值风险")
            score -= 5

        return details, score

    def _analyze_pb(self, fundamental_analysis: Dict[str, Any],
                     details: list, score: int) -> Tuple[list, int]:
        """分析PB指标"""
        pb = fundamental_analysis.get('pb', 0)
        if 0 < pb < 2:
            details.append(f"PB估值较低({pb:.2f})，具有安全边际")
            score += 8
        elif 2 <= pb < 5:
            details.append(f"PB估值合理({pb:.2f})")
            score += 4
        else:
            details.append(f"PB估值偏高({pb:.2f})")
            score -= 4

        return details, score

    def _analyze_revenue_growth(self, fundamental_analysis: Dict[str, Any],
                                 details: list, score: int) -> Tuple[list, int]:
        """分析营收增长率"""
        revenue_growth = fundamental_analysis.get('revenue_growth', 0)
        if revenue_growth > 30:
            details.append(f"营收高速增长({revenue_growth:.1f}%)，成长性好")
            score += 12
        elif revenue_growth > 15:
            details.append(f"营收稳健增长({revenue_growth:.1f}%)")
            score += 8
        elif revenue_growth > 0:
            details.append(f"营收小幅增长({revenue_growth:.1f}%)")
            score += 3
        else:
            details.append(f"营收负增长({revenue_growth:.1f}%)，成长性欠佳")
            score -= 8

        return details, score
