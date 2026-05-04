# -*- coding: utf-8 -*-
"""
政策面分析器

评分由 LLM 直接输出，本模块仅做结构化描述。
保留 analyze() 接口兼容性，实际评分在 analyzer_enhanced 中用 LLM 结果覆盖。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("stock_selector.analyzer.policy")


class PolicyAnalyzer:

    def analyze(self, context: Dict[str, Any],
                news_context: Optional[str]) -> Tuple[str, int]:
        if not news_context:
            return "暂无明显政策面影响", 50
        return "政策面分析已由LLM完成", 50

    def calculate_policy_score(self, news_context: str) -> int:
        return 50
