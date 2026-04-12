# -*- coding: utf-8 -*-
"""
政策面分析器

负责分析国内外财经政策、行业政策等因素对股票的影响。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("stock_selector.analyzer.policy")


class PolicyAnalyzer:
    """
    政策面分析器

    分析维度：
    - 行业政策（支持/限制）
    - 宏观经济因素（美联储、通胀、GDP等）
    - 国内外财经形势
    """

    INDUSTRY_KEYWORDS = {
        '新能源': 1, '芯片': 1, '人工智能': 1, '5G': 1, '半导体': 1,
        '医药': 0, '消费': 0, '金融': 0, '地产': -1, '教育': -1
    }

    SUPPORT_KEYWORDS = ['政策支持', '国家战略', '产业扶持', '补贴', '减税']
    RESTRICT_KEYWORDS = ['监管', '限制', '整顿', '处罚', '收紧']

    MACRO_KEYWORDS = {
        '美联储': -1, '加息': -1, '降息': 1, '通胀': -1,
        'GDP': 0, '经济复苏': 1, '经济下行': -1, '贸易战': -2
    }

    def analyze(self, context: Dict[str, Any],
                news_context: Optional[str]) -> Tuple[str, int]:
        """
        分析政策面

        Args:
            context: 股票上下文数据
            news_context: 新闻上下文

        Returns:
            Tuple[分析详情, 政策评分]
        """
        details = []
        score = 50

        details, score = self._analyze_industry_policy(news_context, details, score)
        details, score = self._analyze_macro_policy(news_context, details, score)

        if not details:
            details.append("暂无明显政策面影响")

        return "；".join(details), max(0, min(100, score))

    def _analyze_industry_policy(self, news_context: Optional[str],
                                 details: list, score: int) -> Tuple[list, int]:
        """分析行业政策"""
        if not news_context:
            return details, score

        for keyword in self.SUPPORT_KEYWORDS:
            if keyword in news_context:
                details.append(f"发现政策支持信号: {keyword}")
                score += 5

        for keyword in self.RESTRICT_KEYWORDS:
            if keyword in news_context:
                details.append(f"发现政策限制信号: {keyword}")
                score -= 5

        return details, score

    def _analyze_macro_policy(self, news_context: Optional[str],
                               details: list, score: int) -> Tuple[list, int]:
        """分析宏观经济政策"""
        if not news_context:
            return details, score

        for keyword, weight in self.MACRO_KEYWORDS.items():
            if keyword in news_context:
                details.append(f"关注宏观经济因素: {keyword}")
                score += weight * 3

        return details, score

    def calculate_policy_score(self, news_context: str) -> int:
        """计算政策评分"""
        if not news_context:
            return 50

        score = 50

        for keyword in self.SUPPORT_KEYWORDS:
            if keyword in news_context:
                score += 5

        for keyword in self.RESTRICT_KEYWORDS:
            if keyword in news_context:
                score -= 5

        for keyword, weight in self.MACRO_KEYWORDS.items():
            if keyword in news_context:
                score += weight * 3

        return max(0, min(100, score))
