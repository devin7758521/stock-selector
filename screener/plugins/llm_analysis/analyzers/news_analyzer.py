# -*- coding: utf-8 -*-
"""
消息面分析器

负责从新闻上下文中提取结构化信息（标题、摘要）。
评分由 LLM 直接输出，本模块不再做关键词打分。

Copyright (c) 2026 stock selector. All rights reserved.
"""

import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("stock_selector.analyzer.news")


class NewsAnalyzer:

    def analyze(self, news_context: Optional[str],
                stock_name: str, code: str) -> Tuple[str, int, str, str, str]:
        if not news_context:
            return f"暂无{stock_name}({code})相关新闻信息", 50, "", "", ""

        headlines = self._extract_headlines(news_context)
        news_headlines_str = "；".join(headlines) if headlines else ""
        detail = f"{stock_name}({code})：共提取{len(headlines)}条新闻要点" if headlines else "新闻内容中性，无明显利好利空"

        return detail, 50, news_headlines_str, "", ""

    def _extract_headlines(self, news_context: str):
        headlines = []
        for line in news_context.split('\n'):
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in ['【', '】', '搜索结果', '来源：']):
                continue
            if 10 < len(line) < 150:
                clean = line.split('。')[0] if '。' in line else line
                clean = clean.split('；')[0] if '；' in clean else clean
                if clean and len(clean) > 5:
                    headlines.append(clean[:60])
        return headlines

    def calculate_sentiment_score(self, news_context: str) -> int:
        return 50
