# -*- coding: utf-8 -*-
"""
===================================
A股新闻搜索模块 - 基于AkShare（已加超时保护）
===================================

所有 AkShare 调用均通过 _ak_call() 包装，设置超时上限，
防止单个接口挂死导致整个流程卡死。

Copyright (c) 2026 stock selector
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── 全局超时配置（秒）────────────────────────────────────────
AK_TIMEOUT_DEFAULT = 15   # 普通接口
AK_TIMEOUT_NEWS    = 20   # 新闻接口（数据量稍大）
AK_TIMEOUT_MACRO   = 10   # 宏观数据接口

AD_KEYWORDS = [
    '东方财富免费版', '东方财富Level-2', '东方财富策略', '广告', '免费',
    '妙想', '投研助理', 'Choice金融', 'Choice', '金融终端', 'Level-2',
    '下载', '客户端', '电脑版', '手机版', 'app', '软件', '推广',
    'VIP', '付费', '订阅', '开户', '低佣', '万一',
]

POSITIVE_KEYWORDS = [
    '涨停', '大涨', '大幅上涨', '业绩增长', '营收增长', '净利润增长',
    '突破', '创新高', '获批', '中标', '订单', '签约', '合作',
    '增持', '回购', '分红', '送股', '扩产', '景气', '复苏',
    '政策支持', '利好', '增长', '提升', '超预期',
    '金叉', '买入', '推荐', '上调', '超配', '看多',
]

NEGATIVE_KEYWORDS = [
    '跌停', '大跌', '大幅下跌', '业绩下降', '营收下降', '净利润下降',
    '亏损', '预亏', '预警', '减持', '回购失败', '诉讼', '仲裁',
    '政策利空', '监管', '调查', '整改', '处分', '风险提示',
    '下调', '减持', '卖出', '看空', '风险', '暴雷', '造假',
    '破发', '破净', 'st', '*st', '退市',
]


def _ak_call(func, *args, timeout: int = AK_TIMEOUT_DEFAULT, **kwargs):
    """
    带超时保护的 AkShare 调用包装器。
    超时或异常均返回 None，不抛出，由调用方判断是否降级。
    """
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(func, *args, **kwargs)
            return future.result(timeout=timeout)
    except FuturesTimeout:
        logger.warning(f"AkShare 调用超时({timeout}s): {func.__name__}")
        return None
    except Exception as e:
        logger.debug(f"AkShare 调用失败 {func.__name__}: {e}")
        return None


def _classify_sentiment(title: str, content: str = "") -> str:
    text = (title + " " + content).lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw.lower() in text)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw.lower() in text)
    if pos > neg:
        return "利好"
    elif neg > pos:
        return "利空"
    return "中性"


def _is_ad(title: str) -> bool:
    if not title:
        return True
    tl = title.lower()
    if any(kw.lower() in tl for kw in AD_KEYWORDS):
        return True
    if len(title) < 6:
        return True
    return False


def _parse_date(date_str: Optional[str], days: int = 7) -> bool:
    if not date_str:
        return True
    try:
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%m/%d', '%H:%M']:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                if fmt in ['%m-%d', '%m/%d', '%H:%M']:
                    parsed = parsed.replace(year=datetime.now().year)
                return (datetime.now() - parsed).days <= days
            except ValueError:
                continue
        return True
    except Exception:
        return True


class NewsResult:
    def __init__(self, title: str, content: str = "", url: str = "",
                 source: str = "", pub_date: str = ""):
        self.title = title
        self.content = content
        self.url = url
        self.source = source
        self.pub_date = pub_date
        self.sentiment = _classify_sentiment(title, content)

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


# ─────────────────────────────────────────────────────────────
# 个股新闻
# ─────────────────────────────────────────────────────────────
def search_akshare_stock_news(stock_code: str, stock_name: str = "",
                               days: int = 7, max_results: int = 5) -> List[NewsResult]:
    results: List[NewsResult] = []
    code_6 = stock_code.zfill(6) if len(stock_code) < 6 else stock_code[-6:]

    try:
        import akshare as ak

        # ← 加了 timeout=AK_TIMEOUT_NEWS
        df = _ak_call(ak.stock_news_em, symbol=code_6, timeout=AK_TIMEOUT_NEWS)

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
            logger.info(f"AkShare 个股新闻({code_6}): {len(results)} 条")

    except ImportError:
        logger.warning("AkShare 未安装: pip install akshare")
    except Exception as e:
        logger.warning(f"AkShare 个股新闻失败: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 市场新闻
# ─────────────────────────────────────────────────────────────
def search_akshare_market_news(days: int = 3, max_results: int = 10) -> List[NewsResult]:
    results: List[NewsResult] = []

    try:
        import akshare as ak

        # 按优先级依次尝试，每个都有超时保护
        news_sources = [
            ("news_em",          lambda: _ak_call(ak.news_em, timeout=AK_TIMEOUT_NEWS)),
            ("stock_hot_rank_em",lambda: _ak_call(ak.stock_hot_rank_em, timeout=AK_TIMEOUT_DEFAULT)),
            ("stock_zt_pool_em", lambda: _ak_call(ak.stock_zt_pool_em,
                                                   date=datetime.now().strftime("%Y%m%d"),
                                                   timeout=AK_TIMEOUT_DEFAULT)),
        ]

        for func_name, func_call in news_sources:
            if len(results) >= max_results:
                break
            try:
                df = func_call()
                if df is None or df.empty:
                    logger.debug(f"AkShare {func_name} 返回空")
                    continue

                count = 0
                for row in df.to_dict('records'):
                    if count >= max_results:
                        break
                    title = content = pub = url = ""
                    source = "东方财富"

                    if func_name == "stock_hot_rank_em":
                        title = str(row.get('股票名称', row.get('证券名称', '')))
                        source = "东方财富热门"
                    elif func_name == "stock_zt_pool_em":
                        name = row.get('名称', '')
                        pct  = row.get('涨跌幅', '')
                        title = f"涨停: {name} 涨跌幅:{pct}%"
                        source = "东方财富涨停"
                    elif func_name == "news_em":
                        title   = str(row.get('新闻标题', row.get('标题', '')))
                        content = str(row.get('新闻内容', row.get('内容', '')))[:200]
                        pub     = str(row.get('发布时间', row.get('时间', '')))
                        url     = str(row.get('来源链接', row.get('来源', '')))
                        source  = "东方财富财经"

                    if not title or _is_ad(title):
                        continue
                    if pub and not _parse_date(pub, days):
                        continue

                    news_result = NewsResult(
                        title=title,
                        content=content[:200] if content else '',
                        url=url,
                        source=source,
                        pub_date=pub
                    )
                    results.append(news_result)
                    count += 1

                if results:
                    logger.info(f"AkShare 市场新闻({func_name}): {len(results)} 条")
                    break   # 有结果就不继续尝试下一个源

            except Exception as e:
                logger.debug(f"AkShare {func_name} 处理失败: {e}")
                continue

    except ImportError:
        logger.warning("AkShare 未安装")
    except Exception as e:
        logger.warning(f"AkShare 市场新闻失败: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 宏观新闻
# ─────────────────────────────────────────────────────────────
def search_akshare_macro_news(days: int = 3, max_results: int = 5) -> List[NewsResult]:
    results: List[NewsResult] = []

    try:
        import akshare as ak

        # ← 加了 timeout=AK_TIMEOUT_MACRO
        df = _ak_call(ak.macro_china_money_supply, timeout=AK_TIMEOUT_MACRO)

        if df is not None and not df.empty:
            count = 0
            for _, row in df.iterrows():
                if count >= max_results:
                    break
                title   = str(row.iloc[0])[:50] if len(row) > 0 else ''
                content = str(row.to_dict())[:200]
                news_result = NewsResult(
                    title=f"宏观数据: {title}",
                    content=content,
                    source="AkShare宏观",
                    pub_date=""
                )
                results.append(news_result)
                count += 1

    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"AkShare 宏观数据失败: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 备用爬虫（requests + BS4）
# ─────────────────────────────────────────────────────────────
def search_stock_news_fallback(stock_code: str, stock_name: str = "",
                                days: int = 7, max_results: int = 5) -> List[NewsResult]:
    import requests
    from bs4 import BeautifulSoup

    results: List[NewsResult] = []
    code_6 = stock_code.zfill(6)[-6:]

    try:
        url = f"http://so.eastmoney.com/web/s?keyword={code_6}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        count = 0
        for item in soup.select('li'):
            if count >= max_results:
                break
            a = item.select_one('a')
            if not a:
                continue
            title = a.get_text(strip=True)
            if _is_ad(title):
                continue
            link  = a.get('href', '')
            time_elem = item.select_one('.time') or item.select_one('.news-time')
            pub   = time_elem.get_text(strip=True) if time_elem else ''
            if pub and not _parse_date(pub, days):
                continue
            results.append(NewsResult(
                title=title, content='', url=link,
                source="东方财富(备用)", pub_date=pub
            ))
            count += 1

        logger.info(f"东方财富备用搜索({code_6}): {len(results)} 条")

    except Exception as e:
        logger.warning(f"东方财富备用搜索失败: {e}")

    return results


# ─────────────────────────────────────────────────────────────
# 对外接口：构建新闻上下文
# ─────────────────────────────────────────────────────────────
def build_news_context(stock_code: str, stock_name: str = "",
                       days: int = 7, max_results: int = 5) -> tuple:
    news_list: List[NewsResult] = []

    akshare_results = search_akshare_stock_news(stock_code, stock_name, days, max_results)
    if akshare_results:
        news_list = akshare_results
    else:
        tavily_results = search_tavily_stock_news(stock_name, stock_code, days, max_results)
        if tavily_results:
            news_list = tavily_results
        else:
            fallback = search_stock_news_fallback(stock_code, stock_name, days, max_results)
            if fallback:
                news_list = fallback

    if not news_list:
        return "", False

    good = sum(1 for n in news_list if n.sentiment == "利好")
    bad  = sum(1 for n in news_list if n.sentiment == "利空")
    lines = [f"【{stock_name or stock_code} 新闻/公告】", f"📊 汇总: 利好{good} 利空{bad}"]
    for i, news in enumerate(news_list, 1):
        emoji = "📈" if news.sentiment == "利好" else "📉" if news.sentiment == "利空" else "📊"
        date_part = f" ({news.pub_date})" if news.pub_date else ""
        lines.append(f"{i}. {emoji}【{news.sentiment}】【{news.source}】{news.title}{date_part}")
        if news.content:
            lines.append(f"   {news.content[:100]}...")

    return "\n".join(lines), True


def build_all_news_context(stock_code: str, stock_name: str = "",
                           stock_days: int = 7, stock_max: int = 5,
                           market_days: int = 3, market_max: int = 10,
                           macro_days: int = 3, macro_max: int = 5,
                           cached_market_ctx: Optional[str] = None,
                           cached_macro_ctx: Optional[str] = None,
                           ) -> tuple:
    stock_news = _search_news_list(stock_code, stock_name, stock_days, stock_max)
    stock_ctx  = _format_news_context(stock_news, f"{stock_name or stock_code}个股新闻") if stock_news else None

    if cached_market_ctx is not None:
        market_ctx = cached_market_ctx or None
    else:
        market_news = _search_market_news_list(market_days, market_max)
        market_ctx  = _format_news_context(market_news, "市场财经新闻") if market_news else None

    if cached_macro_ctx is not None:
        macro_ctx = cached_macro_ctx or None
    else:
        macro_news = _search_macro_news_list(macro_days, macro_max)
        macro_ctx  = _format_news_context(macro_news, "宏观政策新闻") if macro_news else None

    has_any = bool(stock_ctx or market_ctx or macro_ctx)
    return stock_ctx, market_ctx, macro_ctx, has_any


def _search_news_list(stock_code, stock_name, days, max_results) -> List[NewsResult]:
    from .news_scrapling import scrapling_stock_news, scrapling_stock_news_fallback

    news_list: List[NewsResult] = []
    seen: set = set()

    for n in scrapling_stock_news(stock_code, stock_name, max_total=max_results):
        key = (n.title or "")[:50].lower()
        if key not in seen:
            seen.add(key); news_list.append(n)

    if len(news_list) < max_results:
        for n in search_akshare_stock_news(stock_code, stock_name, days, max_results):
            key = (n.title or "")[:50].lower()
            if key not in seen:
                seen.add(key); news_list.append(n)

    if len(news_list) < max_results:
        for n in search_tavily_stock_news(stock_name, stock_code, days, max_results):
            key = (n.title or "")[:50].lower()
            if key not in seen:
                seen.add(key); news_list.append(n)

    if len(news_list) < max_results:
        for n in scrapling_stock_news_fallback(stock_code, stock_name, max_results):
            key = (n.title or "")[:50].lower()
            if key not in seen:
                seen.add(key); news_list.append(n)

    if not news_list:
        news_list = search_stock_news_fallback(stock_code, stock_name, days, max_results)

    return news_list


def _search_market_news_list(days, max_results) -> List[NewsResult]:
    from .news_scrapling import scrapling_market_news

    news_list: List[NewsResult] = []
    seen: set = set()

    for n in scrapling_market_news(max_total=max_results):
        key = (n.title or "")[:60].lower()
        if key not in seen:
            seen.add(key); news_list.append(n)

    if len(news_list) < max_results:
        try:
            for n in search_akshare_market_news(days, max_results):
                key = (n.title or "")[:60].lower()
                if key not in seen:
                    seen.add(key); news_list.append(n)
        except Exception as e:
            logger.warning(f"AkShare 市场新闻补充失败: {e}")

    return news_list


def _search_macro_news_list(days, max_results) -> List[NewsResult]:
    try:
        return search_akshare_macro_news(days, max_results)
    except Exception as e:
        logger.warning(f"宏观新闻搜索失败: {e}")
        return []


def _format_news_context(news_list: List[NewsResult], title: str) -> str:
    if not news_list:
        return ""
    good = sum(1 for n in news_list if n.sentiment == "利好")
    bad  = sum(1 for n in news_list if n.sentiment == "利空")
    lines = [f"【{title}】利好:{good} 利空:{bad}"]
    for i, news in enumerate(news_list, 1):
        emoji = "📈" if news.sentiment == "利好" else "📉" if news.sentiment == "利空" else "📊"
        if news.content and len(news.content) > 10:
            brief = news.content[:60].replace("\n", " ").strip()
            lines.append(f"{i}.{emoji}{news.title}｜{brief}")
        else:
            lines.append(f"{i}.{emoji}{news.title}")
    return "\n".join(lines)


def search_tavily_stock_news(stock_name: str, stock_code: str = "",
                             days: int = 7, max_results: int = 5) -> List[NewsResult]:
    results: List[NewsResult] = []
    tavily_key = os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_API_KEY_2")
    if not tavily_key:
        return results

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        query  = f"{stock_name} {stock_code} 股票 A股"
        response = client.search(query=query, search_days=min(days, 7), max_results=max_results)

        for item in response.get("results", [])[:max_results]:
            title   = item.get("title", "")[:200]
            content = item.get("content", "")[:200]
            news_result = NewsResult(
                title=title, content=content,
                url=item.get("url", ""),
                source="Tavily", pub_date=""
            )
            results.append(news_result)

        if results:
            logger.info(f"Tavily 个股新闻({stock_name}): {len(results)} 条")

    except ImportError:
        logger.warning("Tavily 未安装: pip install tavily-python")
    except Exception as e:
        logger.warning(f"Tavily 搜索失败: {e}")

    return results


def build_macro_context(days: int = 3, max_results: int = 5) -> tuple:
    results = search_akshare_market_news(days, max_results)
    if not results:
        return "", False

    good  = sum(1 for n in results if n.sentiment == "利好")
    bad   = sum(1 for n in results if n.sentiment == "利空")
    lines = [f"【宏观政策新闻】利好:{good} 利空:{bad}"]
    for i, news in enumerate(results, 1):
        emoji  = "📈" if news.sentiment == "利好" else "📉" if news.sentiment == "利空" else "📊"
        impact = _brief_policy_impact(news.title, news.sentiment)
        if news.content and len(news.content) > 10:
            brief = news.content[:50].replace("\n", " ").strip()
            lines.append(f"{i}.{emoji}{news.title}｜{impact}｜{brief}")
        else:
            lines.append(f"{i}.{emoji}{news.title}｜{impact}")
    return "\n".join(lines), True


_POLICY_IMPACT_KEYWORDS = {
    "降息": "流动性宽松，利好股市估值",
    "降准": "释放流动性，利好市场",
    "逆回购": "短期流动性投放",
    "MLF": "中期流动性调节",
    "LPR": "贷款利率调整",
    "减税": "企业盈利改善",
    "补贴": "相关行业受益",
    "扶持": "政策支持行业",
    "刺激": "经济刺激政策",
    "扩内需": "消费相关受益",
    "新基建": "基建链受益",
    "新能源": "新能源产业链利好",
    "半导体": "国产替代加速",
    "芯片": "科技自主可控",
    "房地产": "地产链政策变化",
    "限产": "供给收缩，价格或上行",
    "监管": "行业监管趋严",
    "反垄断": "平台经济受限",
    "加息": "流动性收紧，利空估值",
    "通胀": "货币政策或收紧",
    "贸易战": "出口链承压",
    "制裁": "相关企业受影响",
    "衰退": "经济下行压力",
    "违约": "信用风险上升",
}


def _brief_policy_impact(title: str, sentiment: str) -> str:
    for kw, impact in _POLICY_IMPACT_KEYWORDS.items():
        if kw in title:
            return impact
    if sentiment == "利好":
        return "政策面偏暖"
    elif sentiment == "利空":
        return "政策面偏空"
    return "影响待观察"
