# -*- coding: utf-8 -*-
"""
===================================
A股新闻搜索模块 - 基于AkShare
===================================

提供稳定、准确、免费的A股新闻搜索功能：
1. AkShare 实时财经新闻
2. AkShare 个股新闻
3. 东方财富/新浪财经备用

Copyright (c) 2026 stock selector
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

AD_KEYWORDS = [
    '东方财富免费版', '东方财富Level-2', '东方财富策略', '广告', '免费',
    '妙想', '投研助理', 'Choice金融', 'Choice', '金融终端', 'Level-2',
    '下载', '客户端', '电脑版', '手机版',
]


def _is_ad(title: str) -> bool:
    """判断是否为广告"""
    if not title:
        return True
    title_lower = title.lower()
    if any(kw.lower() in title_lower for kw in AD_KEYWORDS):
        return True
    if len(title) < 6:
        return True
    return False


def _parse_date(date_str: Optional[str], days: int = 7) -> bool:
    """检查日期是否在指定范围内"""
    if not date_str:
        return True
    try:
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%m/%d', '%H:%M']:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                if fmt in ['%m-%d', '%m/%d', '%H:%M']:
                    parsed = parsed.replace(year=datetime.now().year)
                if (datetime.now() - parsed).days <= days:
                    return True
                return False
            except ValueError:
                continue
        return True
    except Exception:
        return True


class NewsResult:
    """新闻结果"""
    def __init__(self, title: str, content: str = "", url: str = "",
                 source: str = "", pub_date: str = ""):
        self.title = title
        self.content = content
        self.url = url
        self.source = source
        self.pub_date = pub_date

    def __repr__(self):
        return f"<NewsResult {self.title[:20]}>"

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "pub_date": self.pub_date
        }


def search_akshare_stock_news(stock_code: str, stock_name: str = "",
                               days: int = 7, max_results: int = 5) -> List[NewsResult]:
    """
    使用 AkShare 获取个股新闻

    Args:
        stock_code: 股票代码（支持 6位代码）
        stock_name: 股票名称（可选）
        days: 最近几天（默认7天）
        max_results: 最大返回条数

    Returns:
        新闻列表
    """
    results: List[NewsResult] = []

    code_6 = stock_code.zfill(6) if len(stock_code) < 6 else stock_code[-6:]

    try:
        import akshare as ak

        try:
            df = ak.stock_news_em(symbol=code_6)
            if df is not None and not df.empty:
                count = 0
                for _, row in df.iterrows():
                    if count >= max_results:
                        break
                    title = str(row.get('新闻标题', '')).strip()
                    if _is_ad(title):
                        continue
                    content = str(row.get('新闻内容', '')).strip()
                    url = str(row.get('文章来源', '')).strip()
                    if not url or url == 'nan':
                        url = ''
                    pub = str(row.get('发布时间', '')).strip()
                    if pub and pub != 'nan':
                        if not _parse_date(pub, days):
                            continue
                    results.append(NewsResult(
                        title=title,
                        content=content[:200] if content else '',
                        url=url,
                        source="东方财富",
                        pub_date=pub
                    ))
                    count += 1
                logger.info(f"AkShare 个股新闻({code_6}): 获取到 {len(results)} 条")
        except Exception as e:
            logger.warning(f"AkShare stock_news_em({code_6}) 失败: {e}")

    except ImportError:
        logger.warning("AkShare 未安装: pip install akshare")
    except Exception as e:
        logger.warning(f"AkShare 导入/初始化失败: {e}")

    return results


def search_akshare_market_news(days: int = 3, max_results: int = 10) -> List[NewsResult]:
    """
    使用 AkShare 获取市场/宏观财经新闻

    Args:
        days: 最近几天
        max_results: 最大返回条数

    Returns:
        新闻列表
    """
    results: List[NewsResult] = []

    try:
        import akshare as ak

        try:
            df = ak.stock_teleport_em()
            if df is not None and not df.empty:
                count = 0
                for _, row in df.iterrows():
                    if count >= max_results:
                        break
                    title = str(row.get('新闻标题', '')).strip()
                    if _is_ad(title):
                        continue
                    content = str(row.get('新闻内容', '')).strip()
                    url = str(row.get('来源链接', '')).strip()
                    pub = str(row.get('发布时间', '')).strip()
                    if pub and not _parse_date(pub, days):
                        continue
                    results.append(NewsResult(
                        title=title,
                        content=content[:300] if content else '',
                        url=url,
                        source="东方财富宏观",
                        pub_date=pub
                    ))
                    count += 1
                logger.info(f"AkShare 宏观新闻: 获取到 {len(results)} 条")
        except Exception as e:
            logger.warning(f"AkShare stock_teleport_em 失败: {e}")

    except ImportError:
        logger.warning("AkShare 未安装")
    except Exception as e:
        logger.warning(f"AkShare 宏观新闻失败: {e}")

    return results


def search_akshare_macro_news(days: int = 3, max_results: int = 5) -> List[NewsResult]:
    """
    使用 AkShare 获取国内外宏观新闻

    Args:
        days: 最近几天
        max_results: 最大返回条数

    Returns:
        新闻列表
    """
    results: List[NewsResult] = []

    try:
        import akshare as ak

        try:
            df = ak.macro_china_money_supply()
            if df is not None and not df.empty:
                count = 0
                for _, row in df.iterrows():
                    if count >= max_results:
                        break
                    title = str(row.iloc[0])[:50] if len(row) > 0 else ''
                    content = str(row.to_dict())[:200]
                    results.append(NewsResult(
                        title=f"宏观数据: {title}",
                        content=content,
                        source="AkShare宏观",
                        pub_date=""
                    ))
                    count += 1
        except Exception as e:
            logger.debug(f"AkShare macro_china_money_supply 失败(可忽略): {e}")

    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"AkShare 宏观数据获取失败: {e}")

    return results


def search_stock_news_fallback(stock_code: str, stock_name: str = "",
                                days: int = 7, max_results: int = 5) -> List[NewsResult]:
    """
    备用新闻搜索：使用爬虫直接抓取东方财富个股新闻页面

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        days: 最近几天
        max_results: 最大条数

    Returns:
        新闻列表
    """
    import requests
    from bs4 import BeautifulSoup

    results: List[NewsResult] = []
    code_6 = stock_code.zfill(6)[-6:]

    try:
        url = f"http://so.eastmoney.com/web/s?keyword={code_6}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        items = soup.select('li')
        count = 0
        for item in items:
            if count >= max_results:
                break
            a = item.select_one('a')
            if not a:
                continue
            title = a.get_text(strip=True)
            if _is_ad(title):
                continue
            link = a.get('href', '')
            time_elem = item.select_one('.time') or item.select_one('.news-time')
            pub = time_elem.get_text(strip=True) if time_elem else ''
            if pub and not _parse_date(pub, days):
                continue
            results.append(NewsResult(
                title=title,
                content='',
                url=link,
                source="东方财富(备用)",
                pub_date=pub
            ))
            count += 1

        logger.info(f"东方财富备用搜索({code_6}): 获取 {len(results)} 条")

    except Exception as e:
        logger.warning(f"东方财富备用搜索失败: {e}")

    return results


def build_news_context(stock_code: str, stock_name: str = "",
                       days: int = 7, max_results: int = 5) -> tuple[str, bool]:
    """
    构建新闻上下文字符串，优先用 AkShare，失败则用备用爬虫/Tavily

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        days: 时间范围（天）
        max_results: 最大条数

    Returns:
        (context_str, success)
    """
    news_list: List[NewsResult] = []

    akshare_results = search_akshare_stock_news(stock_code, stock_name, days, max_results)
    if akshare_results:
        news_list = akshare_results
    else:
        tavily_results = search_tavily_stock_news(stock_name, stock_code, days, max_results)
        if tavily_results:
            news_list = tavily_results
        else:
            fallback_results = search_stock_news_fallback(stock_code, stock_name, days, max_results)
            if fallback_results:
                news_list = fallback_results

    if not news_list:
        return "", False

    lines = [f"【{stock_name or stock_code} 新闻/公告】"]
    for i, news in enumerate(news_list, 1):
        date_part = f" ({news.pub_date})" if news.pub_date else ""
        lines.append(f"{i}. 【{news.source}】{news.title}{date_part}")
        if news.content:
            lines.append(f"   {news.content[:150]}...")

    return "\n".join(lines), True


def search_tavily_stock_news(stock_name: str, stock_code: str = "",
                             days: int = 7, max_results: int = 5) -> List[NewsResult]:
    """
    使用 Tavily AI 搜索增强新闻覆盖

    Args:
        stock_name: 股票名称
        stock_code: 股票代码
        days: 时间范围
        max_results: 最大条数

    Returns:
        新闻列表
    """
    results: List[NewsResult] = []

    tavily_key = os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return results

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)

        query = f"{stock_name} {stock_code} 股票 A股"
        search_days = min(days, 7)

        response = client.search(
            query=query,
            search_days=search_days,
            max_results=max_results
        )

        for item in response.get("results", [])[:max_results]:
            results.append(NewsResult(
                title=item.get("title", "")[:200],
                content=item.get("content", "")[:200],
                url=item.get("url", ""),
                source="Tavily",
                pub_date=""
            ))

        if results:
            logger.info(f"Tavily 个股新闻({stock_name}): 获取到 {len(results)} 条")

    except ImportError:
        logger.warning("Tavily 未安装: pip install tavily-python")
    except Exception as e:
        logger.warning(f"Tavily 搜索失败: {e}")

    return results


def build_macro_context(days: int = 3, max_results: int = 5) -> tuple[str, bool]:
    """
    构建宏观/市场环境上下文

    Returns:
        (context_str, success)
    """
    results = search_akshare_market_news(days, max_results)
    if not results:
        return "", False

    lines = ["【国内财经/宏观新闻】"]
    for i, news in enumerate(results, 1):
        date_part = f" ({news.pub_date})" if news.pub_date else ""
        lines.append(f"{i}. {news.title}{date_part}")
        if news.content:
            lines.append(f"   {news.content[:100]}...")

    return "\n".join(lines), True
