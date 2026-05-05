# -*- coding: utf-8 -*-
"""
===================================
Scrapling 新闻抓取模块 (A 股适配版) — 已修复 Scrapling API
===================================

修复说明（2026-05）：
  旧版代码用 `Fetcher.fetch(url)` —— 但 Fetcher 只有 `.get()/.post()` 等 HTTP 方法，
  `.fetch()` 是 StealthyFetcher / DynamicFetcher（Playwright 系）独有接口。
  正确映射：
    basic  模式 → Fetcher.get(url, timeout=N)
    stealth 模式 → StealthyFetcher.fetch(url, headless=True, ...)

  元素文本提取也一并修复：
    css 选择器带 `::text` 时 el.get() 返回纯文本；
    不带 `::text` 时 el.get() 返回外层 HTML，需用 el.text 或手动剥 tag。

Copyright (c) 2026 stock selector
"""

import logging
import os
import re
import time
from typing import List, Dict, Optional, Set

from .news_akshare import NewsResult, _classify_sentiment, _is_ad

logger = logging.getLogger(__name__)

# A 股适配的 Scrapling 新闻源
# (name, url_template, css_selector, lang)
# css_selector 末尾带 ::text 时 el.get() 直接返回纯文本，否则需剥 HTML tag
SCRAPLING_NEWS_SOURCES_A_STOCK = [
    # 个股新闻源 — 选择器带 ::text，el.get() 即是文本
    ("东方财富个股", "https://so.eastmoney.com/web/s?keyword={code}", "h3 a::text, .title a::text", "zh"),
    ("同花顺个股",   "http://so.10jqka.com.cn/s?q={code}",           ".search-result-title a::text", "zh"),
    ("新浪财经个股", "https://search.sina.com.cn/?q={name}+{code}&range=all&c=news",
                    ".box-result a::text, .result a::text", "zh"),
    ("雪球个股",     "https://xueqiu.com/k?q={name}+{code}",          ".search__item__title a::text, h3 a::text", "zh"),
    # 宏观/市场新闻源
    ("东方财富财经", "https://so.eastmoney.com/web/s?keyword=宏观经济+A股", "h3 a::text, .title a::text", "zh"),
    ("新浪财经市场", "https://search.sina.com.cn/?q=A股+市场+政策&range=all&c=news", ".box-result a::text", "zh"),
    # 英文财经源（全球视野）
    ("Reuters",       "https://www.reuters.com/search/news?query=China+stock+{name}",
                      "h3.search-result-title::text", "en"),
    ("Yahoo Finance", "https://finance.yahoo.com/quote/{code}.SS/news/", "h3 a::text, h3::text", "en"),
    ("Google News",   "https://news.google.com/search?q={name}+stock+China&hl=zh-CN", "h3::text, h4::text", "zh"),
    ("Investing.com", "https://www.investing.com/news/stock-market-news",
                      "article a[title]::attr(title)", "en"),
]

# 政策/宏观专用新闻源（独立于个股抓取，解决"信息不足"）
SCRAPLING_POLICY_SOURCES = [
    # 国内政策
    ("财联社电报",   "https://www.cls.cn/searchPage?keyword=政策+宏观&type=telegraph",
                     ".telegraph-content-box::text, .telegraph-list .title::text", "zh"),
    ("财联社要闻",   "https://www.cls.cn/searchPage?keyword=A股+央行&type=all",
                     ".c-article-title::text, .search-article-item h3::text", "zh"),
    ("新华网财经",   "http://www.news.cn/fortune/search.htm?searchword=政策+A股",
                     ".news-item h3::text, .search-result h3 a::text, .tit::text", "zh"),
    ("东方财富政策", "https://so.eastmoney.com/web/s?keyword=央行+货币政策+财政政策+A股",
                     "h3 a::text, .title a::text", "zh"),
    # 国际形势
    ("Reuters中文",  "https://cn.reuters.com/search/news?query=中国+经济+政策+贸易",
                     ".search-result-title::text, h3.article-headline::text", "zh"),
    ("华尔街见闻",   "https://wallstreetcn.com/search?q=宏观+政策+美联储",
                     ".article-item .title::text, .search-result-item h3::text", "zh"),
    ("BBC中文",      "https://www.bbc.com/zhongwen/simp/search?q=中国经济贸易",
                     ".title-wrapper h3::text, .promo-heading__title::text, h3::text", "zh"),
    ("新浪国际财经", "https://search.sina.com.cn/?q=美联储+贸易战+关税+国际形势&range=all&c=news",
                     ".box-result a::text, .result a::text", "zh"),
    # 监管/部委
    ("证监会",       "https://search.sina.com.cn/?q=证监会+监管+政策&range=all&c=news",
                     ".box-result a::text", "zh"),
    ("央行",         "https://search.sina.com.cn/?q=央行+降息+降准+LPR+MLF&range=all&c=news",
                     ".box-result a::text", "zh"),
]


def _get_scrapling_mode() -> str:
    """获取 Scrapling 模式：basic 或 stealth"""
    return os.environ.get("SCRAPLING_MODE", "basic").lower()


def _dedup_key(title: str) -> str:
    """生成去重键：标题前 50 字符小写"""
    return (title or "")[:50].lower().strip()


def _el_text(el) -> str:
    """
    从 Scrapling 元素中安全提取纯文本。
    - 选择器带 ::text / ::attr(xxx) 时，el.get() 已是字符串
    - 否则 el.get() 返回外层 HTML，用 el.text 或 strip HTML tags 兜底
    """
    # 优先用 .text（纯文本属性，大多数版本均有）
    if hasattr(el, 'text') and el.text:
        return str(el.text).strip()

    # 其次 .get()
    if hasattr(el, 'get'):
        raw = el.get() or ""
        # 若含 HTML 标签则剥离
        if '<' in raw:
            raw = re.sub(r'<[^>]+>', '', raw)
        return raw.strip()

    return str(el).strip()


def scrapling_stock_news(
    stock_code: str,
    stock_name: str = "",
    max_per_source: int = 3,
    max_total: int = 10,
    seen_titles: Optional[Set[str]] = None,
) -> List[NewsResult]:
    """
    使用 Scrapling 抓取个股新闻

    Args:
        stock_code: 股票代码（6位）
        stock_name: 股票名称
        max_per_source: 每个源最多抓取条数
        max_total: 总共最多返回条数
        seen_titles: 已见标题集合（跨调用去重）

    Returns:
        新闻列表
    """
    if seen_titles is None:
        seen_titles = set()

    code_6 = stock_code.zfill(6)[-6:] if stock_code else ""
    all_news: List[NewsResult] = []
    mode = _get_scrapling_mode()

    try:
        if mode == "stealth":
            from scrapling.fetchers import StealthyFetcher
            logger.info("Scrapling mode: stealth (Playwright / patchright)")

            for src_name, url_tpl, css_sel, lang in SCRAPLING_NEWS_SOURCES_A_STOCK:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code=code_6, name=stock_name or code_6)
                    page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=15)
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"Scrapling stealth {src_name} ({code_6}): {e}")

        else:
            # basic 模式：Fetcher 用 .get()，不是 .fetch()
            from scrapling.fetchers import Fetcher
            logger.info("Scrapling mode: basic (HTTP via curl_cffi)")

            for src_name, url_tpl, css_sel, lang in SCRAPLING_NEWS_SOURCES_A_STOCK:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code=code_6, name=stock_name or code_6)
                    page = Fetcher.get(url, timeout=15)      # ← 关键修复：.get() 非 .fetch()
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"Scrapling basic {src_name} ({code_6}): {e}")

        if all_news:
            logger.info(f"Scrapling 个股新闻({code_6}): 获取到 {len(all_news)} 条")

    except ImportError:
        logger.info("scrapling 未安装，跳过 Scrapling 新闻抓取 (pip install 'scrapling[fetchers]')")
    except Exception as e:
        logger.warning(f"Scrapling 新闻抓取失败: {e}")

    return all_news[:max_total]


def scrapling_market_news(
    max_per_source: int = 3,
    max_total: int = 15,
    seen_titles: Optional[Set[str]] = None,
) -> List[NewsResult]:
    """
    使用 Scrapling 抓取市场/宏观新闻

    Args:
        max_per_source: 每个源最多抓取条数
        max_total: 总共最多返回条数
        seen_titles: 已见标题集合

    Returns:
        新闻列表
    """
    if seen_titles is None:
        seen_titles = set()

    all_news: List[NewsResult] = []
    mode = _get_scrapling_mode()

    # 只使用宏观/市场相关的源
    macro_sources = [
        s for s in SCRAPLING_NEWS_SOURCES_A_STOCK
        if any(kw in s[0] for kw in ["财经", "市场", "Reuters", "Investing", "Google"])
    ]

    try:
        if mode == "stealth":
            from scrapling.fetchers import StealthyFetcher

            for src_name, url_tpl, css_sel, lang in macro_sources:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code="", name="")
                    page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=15)
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"Scrapling stealth 宏观 {src_name}: {e}")

        else:
            from scrapling.fetchers import Fetcher

            for src_name, url_tpl, css_sel, lang in macro_sources:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code="", name="")
                    page = Fetcher.get(url, timeout=15)      # ← 关键修复
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"Scrapling basic 宏观 {src_name}: {e}")

        if all_news:
            logger.info(f"Scrapling 市场新闻: 获取到 {len(all_news)} 条")

    except ImportError:
        logger.info("scrapling 未安装，跳过 Scrapling 市场新闻")
    except Exception as e:
        logger.warning(f"Scrapling 市场新闻抓取失败: {e}")

    return all_news[:max_total]


def scrapling_policy_news(
    max_per_source: int = 5,
    max_total: int = 20,
    seen_titles: Optional[Set[str]] = None,
) -> List[NewsResult]:
    """
    使用 Scrapling 抓取政策/宏观/国际形势新闻（独立于个股/市场抓取）。

    专门解决"信息不足"问题，覆盖：
    - 国内政策（财联社/新华网/东方财富政策）
    - 国际形势（Reuters中文/华尔街见闻/BBC中文/新浪国际）
    - 监管/部委（证监会/央行）

    Returns:
        新闻列表
    """
    if seen_titles is None:
        seen_titles = set()

    all_news: List[NewsResult] = []
    mode = _get_scrapling_mode()

    try:
        if mode == "stealth":
            from scrapling.fetchers import StealthyFetcher

            for src_name, url_tpl, css_sel, lang in SCRAPLING_POLICY_SOURCES:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code="", name="")
                    page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=20)
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.4)
                except Exception as e:
                    logger.debug(f"Scrapling stealth 政策 {src_name}: {e}")

        else:
            from scrapling.fetchers import Fetcher

            for src_name, url_tpl, css_sel, lang in SCRAPLING_POLICY_SOURCES:
                if len(all_news) >= max_total:
                    break
                try:
                    url = url_tpl.format(code="", name="")
                    page = Fetcher.get(url, timeout=20)
                    _collect_from_page(page, css_sel, src_name, max_per_source,
                                       seen_titles, all_news, max_total)
                    time.sleep(0.4)
                except Exception as e:
                    logger.debug(f"Scrapling basic 政策 {src_name}: {e}")

        if all_news:
            logger.info(f"Scrapling 政策/宏观新闻: 获取到 {len(all_news)} 条")

    except ImportError:
        logger.info("scrapling 未安装，跳过 Scrapling 政策新闻")
    except Exception as e:
        logger.warning(f"Scrapling 政策新闻抓取失败: {e}")

    return all_news[:max_total]


def _collect_from_page(page, css_sel: str, src_name: str,
                        max_per_source: int, seen_titles: Set[str],
                        all_news: List[NewsResult], max_total: int) -> None:
    """从页面 CSS 匹配结果中提取新闻标题 + 摘要，去重后加入 all_news。"""
    titles = page.css(css_sel)
    for el in titles[:max_per_source]:
        if len(all_news) >= max_total:
            break
        text = _el_text(el)
        if not text or len(text) < 10 or _is_ad(text):
            continue
        key = _dedup_key(text)
        if key in seen_titles:
            continue
        seen_titles.add(key)

        snippet = _extract_sibling_snippet(el)

        all_news.append(NewsResult(
            title=text,
            content=snippet,
            url="",
            source=src_name,
            pub_date=""
        ))


def _extract_sibling_snippet(el, max_len: int = 150) -> str:
    """从元素附近提取摘要文本"""
    snippet_selectors = [
        "p::text", ".desc::text", ".description::text",
        ".summary::text", ".content::text", ".abstract::text",
        "span.desc::text", "small::text",
    ]
    try:
        page = getattr(el, 'parent', None)
        if page is None:
            return ""
        for sel in snippet_selectors:
            try:
                items = page.css(sel)
                if items:
                    first = items[0]
                    text = _el_text(first)
                    if text and len(text) > 15 and text != _el_text(el):
                        return text[:max_len]
            except Exception:
                continue
    except Exception:
        pass
    return ""


def scrapling_stock_news_fallback(
    stock_code: str,
    stock_name: str = "",
    max_results: int = 5,
) -> List[NewsResult]:
    """
    Scrapling 不可用时的轻量备用方案：requests + BS4 抓取多源

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        max_results: 最大返回条数

    Returns:
        新闻列表
    """
    import requests
    from bs4 import BeautifulSoup

    results: List[NewsResult] = []
    code_6 = stock_code.zfill(6)[-6:] if stock_code else ""
    seen: Set[str] = set()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }

    sources = [
        {
            "name": "东方财富",
            "url": f"http://so.eastmoney.com/web/s?keyword={code_6}",
            "selectors": ["h3 a", "li a", ".title a"],
        },
        {
            "name": "新浪财经",
            "url": f"https://search.sina.com.cn/?q={stock_name or code_6}+股票&range=all&c=news",
            "selectors": [".box-result a", ".result a", "a"],
        },
        {
            "name": "同花顺",
            "url": f"http://so.10jqka.com.cn/s?q={stock_name or code_6}",
            "selectors": [".search-result-title a", ".result-item a", "a"],
        },
    ]

    for src in sources:
        if len(results) >= max_results:
            break
        try:
            resp = requests.get(src["url"], headers=headers, timeout=8)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for sel in src["selectors"]:
                if len(results) >= max_results:
                    break
                for item in soup.select(sel):
                    if len(results) >= max_results:
                        break
                    title = item.get_text(strip=True)
                    if not title or len(title) < 10 or _is_ad(title):
                        continue
                    key = _dedup_key(title)
                    if key in seen:
                        continue
                    seen.add(key)
                    link = item.get("href", "")
                    results.append(NewsResult(
                        title=title,
                        content="",
                        url=link if link.startswith("http") else "",
                        source=src["name"],
                        pub_date=""
                    ))
        except Exception as e:
            logger.debug(f"备用搜索 {src['name']}({code_6}) 失败: {e}")

    if results:
        logger.info(f"多源备用搜索({code_6}): 获取 {len(results)} 条")
    return results
