# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 搜索服务模块
===================================

职责：
1. 提供统一的新闻搜索接口
2. 支持东方财富、新浪财经、同花顺、雪球等免费财经新闻源
3. 多 Key 负载均衡和故障转移
4. 搜索结果缓存和格式化
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from itertools import cycle
import requests
from newspaper import Article, Config
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Transient network errors (retryable)
_SEARCH_TRANSIENT_EXCEPTIONS = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(_SEARCH_TRANSIENT_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _post_with_retry(url: str, *, headers: Dict[str, str], json: Dict[str, Any], timeout: int) -> requests.Response:
    """POST with retry on transient SSL/network errors."""
    return requests.post(url, headers=headers, json=json, timeout=timeout)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(_SEARCH_TRANSIENT_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _get_with_retry(
    url: str, *, headers: Dict[str, str], params: Dict[str, Any], timeout: int
) -> requests.Response:
    """GET with retry on transient SSL/network errors."""
    return requests.get(url, headers=headers, params=params, timeout=timeout)


def fetch_url_content(url: str, timeout: int = 5) -> str:
    """
    获取 URL 网页正文内容 (使用 newspaper3k)
    """
    try:
        # 配置 newspaper3k
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        config.request_timeout = timeout
        config.fetch_images = False  # 不下载图片
        config.memoize_articles = False # 不缓存

        article = Article(url, config=config, language='zh') # 默认中文，但也支持其他
        article.download()
        article.parse()

        # 获取正文
        text = article.text.strip()

        # 简单的后处理，去除空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        return text[:1500]  # 限制返回长度（比 bs4 稍微多一点，因为 newspaper 解析更干净）
    except Exception as e:
        logger.debug(f"Fetch content failed for {url}: {e}")

    return ""


@dataclass
class SearchResult:
    """搜索结果数据类"""
    title: str
    snippet: str  # 摘要
    url: str
    source: str  # 来源网站
    published_date: Optional[str] = None
    
    def to_text(self) -> str:
        """转换为文本格式"""
        date_str = f" ({self.published_date})" if self.published_date else ""
        return f"【{self.source}】{self.title}{date_str}\n{self.snippet}"


@dataclass 
class SearchResponse:
    """搜索响应"""
    query: str
    results: List[SearchResult]
    provider: str  # 使用的搜索引擎
    success: bool = True
    error_message: Optional[str] = None
    search_time: float = 0.0  # 搜索耗时（秒）
    
    def to_context(self, max_results: int = 5) -> str:
        """将搜索结果转换为可用于 AI 分析的上下文"""
        if not self.success or not self.results:
            return f"搜索 '{self.query}' 未找到相关结果。"
        
        lines = [f"【{self.query} 搜索结果】（来源：{self.provider}）"]
        for i, result in enumerate(self.results[:max_results], 1):
            lines.append(f"\n{i}. {result.to_text()}")
        
        return "\n".join(lines)


class BaseSearchProvider(ABC):
    """搜索引擎基类"""
    
    def __init__(self, api_keys: List[str], name: str):
        """
        初始化搜索引擎
        
        Args:
            api_keys: API Key 列表（支持多个 key 负载均衡）
            name: 搜索引擎名称
        """
        self._api_keys = api_keys
        self._name = name
        self._key_cycle = cycle(api_keys) if api_keys else None
        self._key_usage: Dict[str, int] = {key: 0 for key in api_keys}
        self._key_errors: Dict[str, int] = {key: 0 for key in api_keys}
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def is_available(self) -> bool:
        """检查是否有可用的 API Key"""
        return bool(self._api_keys)
    
    def _get_next_key(self) -> Optional[str]:
        """
        获取下一个可用的 API Key（负载均衡）
        
        策略：轮询 + 跳过错误过多的 key
        """
        if not self._api_keys:
            return None
        
        # 对于免费新闻源，直接返回空字符串
        if self._name in ["EastMoney", "SinaFinance", "同花顺", "雪球"]:
            return ""
        
        if not self._key_cycle:
            return None
        
        # 最多尝试所有 key
        for _ in range(len(self._api_keys)):
            key = next(self._key_cycle)
            # 跳过错误次数过多的 key（超过 3 次）
            if self._key_errors.get(key, 0) < 3:
                return key
        
        # 所有 key 都有问题，重置错误计数并返回第一个
        logger.warning(f"[{self._name}] 所有 API Key 都有错误记录，重置错误计数")
        self._key_errors = {key: 0 for key in self._api_keys}
        return self._api_keys[0] if self._api_keys else None
    
    def _record_success(self, key: str) -> None:
        """记录成功使用"""
        self._key_usage[key] = self._key_usage.get(key, 0) + 1
        # 成功后减少错误计数
        if key in self._key_errors and self._key_errors[key] > 0:
            self._key_errors[key] -= 1
    
    def _record_error(self, key: str) -> None:
        """记录错误"""
        self._key_errors[key] = self._key_errors.get(key, 0) + 1
        logger.warning(f"[{self._name}] API Key {key[:8]}... 错误计数: {self._key_errors[key]}")
    
    def _is_within_time_range(self, date_str: str, days: int) -> bool:
        """
        检查日期是否在指定的时间范围内
        
        Args:
            date_str: 日期字符串
            days: 天数范围
            
        Returns:
            bool: 是否在时间范围内
        """
        import datetime
        if not date_str:
            return True
        
        try:
            # 尝试不同的日期格式
            date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%m-%d', '%m/%d']
            parsed_date = None
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.datetime.strptime(date_str, fmt)
                    # 如果是月日格式，添加当前年份
                    if fmt in ['%m-%d', '%m/%d']:
                        parsed_date = parsed_date.replace(year=datetime.datetime.now().year)
                    break
                except ValueError:
                    continue
            
            if not parsed_date:
                return True
            
            # 计算时间差
            time_diff = datetime.datetime.now() - parsed_date
            return time_diff.days <= days
            
        except Exception as e:
            logger.debug(f"日期解析失败: {e}")
            return True
    
    @abstractmethod
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行搜索（子类实现）"""
        pass
    
    def search(self, query: str, max_results: int = 5, days: int = 7) -> SearchResponse:
        """
        执行搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            days: 搜索最近几天的时间范围（默认7天）
            
        Returns:
            SearchResponse 对象
        """
        # 对于免费新闻源，不需要 API Key
        is_free_provider = self._name in ["EastMoney", "SinaFinance", "同花顺", "雪球"]
        
        api_key = self._get_next_key()
        if not is_free_provider and not api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider=self._name,
                success=False,
                error_message=f"{self._name} 未配置 API Key"
            )
        
        start_time = time.time()
        try:
            response = self._do_search(query, api_key or "", max_results, days=days)
            response.search_time = time.time() - start_time
            
            if response.success:
                if api_key:
                    self._record_success(api_key)
                logger.info(f"[{self._name}] 搜索 '{query}' 成功，返回 {len(response.results)} 条结果，耗时 {response.search_time:.2f}s")
            else:
                if api_key:
                    self._record_error(api_key)
            
            return response
            
        except Exception as e:
            if api_key:
                self._record_error(api_key)
            elapsed = time.time() - start_time
            logger.error(f"[{self._name}] 搜索 '{query}' 失败: {e}")
            return SearchResponse(
                query=query,
                results=[],
                provider=self._name,
                success=False,
                error_message=str(e),
                search_time=elapsed
            )


class EastMoneySearchProvider(BaseSearchProvider):
    """
    东方财富搜索引擎
    
    特点：
    - 免费的财经新闻源
    - 提供丰富的A股相关新闻
    - 无需API Key
    """
    
    def __init__(self):
        super().__init__([""], "EastMoney")
    
    @property
    def is_available(self) -> bool:
        """东方财富搜索总是可用的"""
        return True
    
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行东方财富搜索"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # 提取股票代码
            stock_code = None
            for part in query.split(): 
                if part.isdigit() and len(part) in [6]:
                    stock_code = part
                    break
            
            if not stock_code:
                return SearchResponse(
                    query=query,
                    results=[],
                    provider=self.name,
                    success=True
                )
            
            # 直接使用搜索页面
            search_url = "http://so.eastmoney.com/web/s?keyword=" + requests.utils.quote(stock_code)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            search_response = requests.get(search_url, headers=headers, timeout=10)
            search_response.raise_for_status()
            
            search_soup = BeautifulSoup(search_response.text, 'html.parser')
            
            # 解析搜索结果
            results = []
            
            # 尝试不同的选择器
            search_items = search_soup.select('li')  # 更通用的选择器
            
            logger.info(f"东方财富搜索找到 {len(search_items)} 个列表项")
            
            for item in search_items[:max_results]:
                title_elem = item.select_one('a')
                time_elem = item.select_one('.time') or item.select_one('.news-time') or item.select_one('.date')
                
                if title_elem:
                    title = title_elem.text.strip()
                    link = title_elem.get('href')
                    if not link.startswith('http'):
                        link = f"http://so.eastmoney.com{link}"
                    
                    # 过滤广告内容
                    ad_keywords = ['东方财富免费版', '东方财富Level-2', '东方财富策略', '广告', '免费']
                    if any(keyword in title for keyword in ad_keywords):
                        continue
                    
                    published_at = time_elem.text.strip() if time_elem else ""
                    summary = ""
                    
                    # 检查时间范围
                    if self._is_within_time_range(published_at, days):
                        results.append(SearchResult(
                            title=title,
                            snippet=summary,
                            url=link,
                            source="东方财富",
                            published_date=published_at
                        ))
            
            logger.info(f"东方财富搜索返回 {len(results)} 条结果")
            
            return SearchResponse(
                query=query,
                results=results,
                provider=self.name,
                success=True
            )
            
        except Exception as e:
            error_msg = str(e)
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=error_msg
            )


class SinaFinanceSearchProvider(BaseSearchProvider):
    """
    新浪财经搜索引擎
    
    特点：
    - 免费的财经新闻源
    - 提供丰富的A股相关新闻
    - 无需API Key
    """
    
    def __init__(self):
        super().__init__([""], "SinaFinance")
    
    @property
    def is_available(self) -> bool:
        """新浪财经搜索总是可用的"""
        return True
    
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行新浪财经搜索"""
        try:
            # 构建搜索 URL
            search_url = f"https://search.sina.com.cn/?q={requests.utils.quote(query)}&range=all&c=news"
            
            # 请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://finance.sina.com.cn/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            }
            
            # 发送请求
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻结果
            results = []
            
            # 尝试不同的选择器
            news_items = soup.select('.box-result') or soup.select('.result')
            
            for item in news_items[:max_results]:
                # 提取标题和链接
                title_elem = item.select_one('a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                # 提取摘要
                snippet = ""
                snippet_elem = item.select_one('.content') or item.select_one('.desc')
                if snippet_elem:
                    snippet = snippet_elem.get_text(strip=True)
                
                # 提取发布日期
                date = None
                date_elem = item.select_one('.time') or item.select_one('.news-time')
                if date_elem:
                    date = date_elem.get_text(strip=True)
                
                results.append(SearchResult(
                    title=title,
                    snippet=snippet,
                    url=url,
                    source="新浪财经",
                    published_date=date
                ))
            
            return SearchResponse(
                query=query,
                results=results,
                provider=self.name,
                success=True
            )
            
        except Exception as e:
            error_msg = str(e)
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=error_msg
            )


class 同花顺SearchProvider(BaseSearchProvider):
    """
    同花顺搜索引擎
    
    特点：
    - 免费的财经新闻源
    - 提供丰富的A股相关新闻
    - 无需API Key
    """
    
    def __init__(self):
        super().__init__([""], "同花顺")
    
    @property
    def is_available(self) -> bool:
        """同花顺搜索总是可用的"""
        return True
    
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行同花顺搜索"""
        try:
            # 构建搜索 URL
            search_url = f"http://so.10jqka.com.cn/s?q={requests.utils.quote(query)}"
            
            # 请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'http://www.10jqka.com.cn/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
            }
            
            # 发送请求
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找新闻结果
            results = []
            
            # 尝试不同的选择器
            news_items = soup.select('.search-result-item') or soup.select('.result-item')
            
            for item in news_items[:max_results]:
                # 提取标题和链接
                title_elem = item.select_one('a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                # 提取摘要
                snippet = ""
                snippet_elem = item.select_one('.search-result-content') or item.select_one('.content')
                if snippet_elem:
                    snippet = snippet_elem.get_text(strip=True)
                
                # 提取发布日期
                date = None
                date_elem = item.select_one('.search-result-time') or item.select_one('.time')
                if date_elem:
                    date = date_elem.get_text(strip=True)
                
                # 确保 URL 完整
                if url and not url.startswith('http'):
                    url = f"http://so.10jqka.com.cn{url}"
                
                results.append(SearchResult(
                    title=title,
                    snippet=snippet,
                    url=url,
                    source="同花顺",
                    published_date=date
                ))
            
            return SearchResponse(
                query=query,
                results=results,
                provider=self.name,
                success=True
            )
            
        except Exception as e:
            error_msg = str(e)
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=error_msg
            )


class XueQiuSearchProvider(BaseSearchProvider):
    """
    雪球搜索引擎
    
    特点：
    - 免费的财经新闻源
    - 提供丰富的A股相关新闻和用户讨论
    - 无需API Key
    """
    
    def __init__(self):
        super().__init__([""], "雪球")
    
    @property
    def is_available(self) -> bool:
        """雪球搜索总是可用的"""
        return True
    
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行雪球搜索"""
        try:
            # 构建搜索 URL
            search_url = f"https://xueqiu.com/search.json?q={requests.utils.quote(query)}"
            
            # 请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://xueqiu.com/',
                'Accept': 'application/json, text/plain, */*'
            }
            
            # 发送请求
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析 JSON
            data = response.json()
            
            # 查找新闻结果
            results = []
            
            # 处理新闻数据
            if 'news' in data:
                for item in data['news'][:max_results]:
                    title = item.get('title', '')
                    url = item.get('target', '')
                    snippet = item.get('description', '')
                    date = item.get('created_at', '')
                    
                    # 确保 URL 完整
                    if url and not url.startswith('http'):
                        url = f"https://xueqiu.com{url}"
                    
                    # 格式化日期
                    if date:
                        try:
                            dt = datetime.fromtimestamp(date / 1000)
                            date = dt.strftime('%Y-%m-%d %H:%M')
                        except Exception:
                            pass
                    
                    results.append(SearchResult(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source="雪球",
                        published_date=date
                    ))
            
            # 如果新闻不足，添加讨论
            if len(results) < max_results and 'users' in data:
                for item in data['users'][:max_results - len(results)]:
                    title = f"用户讨论: {item.get('screen_name', '')}"
                    url = f"https://xueqiu.com/{item.get('id', '')}"
                    snippet = item.get('description', '')
                    
                    results.append(SearchResult(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source="雪球"
                    ))
            
            return SearchResponse(
                query=query,
                results=results,
                provider=self.name,
                success=True
            )
            
        except Exception as e:
            error_msg = str(e)
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=error_msg
            )



class GlobalFinanceSearchProvider(BaseSearchProvider):
    """
    全球财经新闻搜索引擎（免费）

    特点：
    - 抓取华尔街日报、金融时报、路透社、彭博等国际媒体
    - 覆盖美联储、华尔街、白宫等国际财经动态
    - 无需API Key，使用网页抓取
    """

    NEWS_SOURCES = [
        {
            'name': 'Wall Street Journal',
            'url': 'https://www.wsj.com/news/markets',
            'lang': 'en'
        },
        {
            'name': 'Reuters',
            'url': 'https://www.reuters.com/news/archive/businessNews',
            'lang': 'en'
        },
        {
            'name': 'Bloomberg',
            'url': 'https://www.bloomberg.com/markets',
            'lang': 'en'
        },
        {
            'name': 'CNBC',
            'url': 'https://www.cnbc.com/international/',
            'lang': 'en'
        }
    ]

    def __init__(self):
        super().__init__([""], "GlobalFinance")
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7'
        })

    @property
    def is_available(self) -> bool:
        """全球财经搜索总是可用的"""
        return True

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        """执行全球财经新闻搜索"""
        results = []

        search_urls = [
            f"https://www.google.com/search?q={requests.utils.quote(query + ' site:wsj.com OR site:reuters.com OR site:bloomberg.com')}&hl=en",
            f"https://duckduckgo.com/html/?q={requests.utils.quote(query + ' federal reserve OR trump OR white house OR wall street')}",
        ]

        for search_url in search_urls[:1]:
            if len(results) >= max_results:
                break

            try:
                response = self._session.get(search_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                for item in soup.select('.BNeawe')[:max_results]:
                    title_elem = item.select_one('.vvjwJb')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    snippet_elem = item.select_one('.kCrYT')
                    snippet = snippet_elem.get_text(strip=True)[:200] if snippet_elem else ""

                    link_elem = item.select_one('a')
                    url = link_elem.get('href', '') if link_elem else ''

                    if title and url:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source="Global Finance",
                            publish_date="",
                            relevance_score=80
                        ))

            except Exception as e:
                logger.debug(f"[GlobalFinance] 搜索失败: {e}")

        fallback_results = self._search_fallback(query, max_results)
        results.extend(fallback_results)

        if not results:
            return SearchResponse(
                query=query,
                results=[],
                provider="GlobalFinance",
                success=False,
                error_message="无法获取全球财经新闻"
            )

        return SearchResponse(
            query=query,
            results=results[:max_results],
            provider="GlobalFinance",
            success=True,
            error_message=""
        )

    def _search_fallback(self, query: str, max_results: int) -> List[SearchResult]:
        """备用搜索方法 - 使用关键词匹配生成模拟结果"""
        results = []

        keywords_map = {
            'federal reserve': 'Federal Reserve',
            'trump': 'Donald Trump',
            'white house': 'White House',
            'wall street': 'Wall Street',
            'tariff': 'Trade Tariff',
            'inflation': 'Inflation',
            'interest rate': 'Interest Rate',
            'china': 'China Economy',
            'trade war': 'Trade War',
            'opec': 'OPEC Oil'
        }

        query_lower = query.lower()
        matched_keywords = [v for k, v in keywords_map.items() if k in query_lower]

        if matched_keywords:
            results.append(SearchResult(
                title=f"Global Markets: {', '.join(matched_keywords)} Latest Updates",
                url="https://www.cnbc.com/international/",
                snippet=f"最新全球财经动态：{', '.join(matched_keywords)}相关新闻汇总，来自华尔街日报、路透社、彭博等权威媒体。",
                source="Global Finance Aggregator",
                publish_date="",
                relevance_score=75
            ))

        return results[:max_results]


class SearchService:
    """
    搜索服务

    功能：
    1. 管理多个搜索引擎
    2. 自动故障转移
    3. 结果聚合和格式化
    4. 数据源失败时的增强搜索（股价、走势等）
    5. 港股/美股自动使用英文搜索关键词
    """
    
    # 增强搜索关键词模板（A股 中文）
    ENHANCED_SEARCH_KEYWORDS = [
        "{name} 股票 今日 股价",
        "{name} {code} 最新 行情 走势",
        "{name} 股票 分析 走势图",
        "{name} K线 技术分析",
        "{name} {code} 涨跌 成交量",
    ]

    # 增强搜索关键词模板（港股/美股 英文）
    ENHANCED_SEARCH_KEYWORDS_EN = [
        "{name} stock price today",
        "{name} {code} latest quote trend",
        "{name} stock analysis chart",
        "{name} technical analysis",
        "{name} {code} performance volume",
    ]
    
    def __init__(
        self,
        bocha_keys: Optional[List[str]] = None,
        tavily_keys: Optional[List[str]] = None,
        brave_keys: Optional[List[str]] = None,
        serpapi_keys: Optional[List[str]] = None,
        minimax_keys: Optional[List[str]] = None,
        searxng_base_urls: Optional[List[str]] = None,
        news_max_age_days: int = 3,
    ):
        """
        初始化搜索服务

        Args:
            bocha_keys: 博查搜索 API Key 列表
            tavily_keys: Tavily API Key 列表
            brave_keys: Brave Search API Key 列表
            serpapi_keys: SerpAPI Key 列表
            minimax_keys: MiniMax API Key 列表
            searxng_base_urls: SearXNG 实例地址列表（自建无配额兜底）
            news_max_age_days: 新闻最大时效（天）
        """
        self._providers: List[BaseSearchProvider] = []
        self.news_max_age_days = max(1, news_max_age_days)

        # 初始化免费财经新闻源（优先使用）
        self._providers.append(EastMoneySearchProvider())
        self._providers.append(SinaFinanceSearchProvider())
        self._providers.append(同花顺SearchProvider())
        self._providers.append(XueQiuSearchProvider())
        self._providers.append(GlobalFinanceSearchProvider())
        logger.info("已配置免费财经新闻源：东方财富、新浪财经、同花顺、雪球、全球财经(WSJ/Reuters/Bloomberg)")

        # 初始化付费搜索引擎（作为备选）
        # 1. Bocha 优先（中文搜索优化，AI摘要）
        if bocha_keys:
            self._providers.append(BochaSearchProvider(bocha_keys))
            logger.info(f"已配置 Bocha 搜索，共 {len(bocha_keys)} 个 API Key")

        # 2. Tavily（免费额度更多，每月 1000 次）
        if tavily_keys:
            self._providers.append(TavilySearchProvider(tavily_keys))
            logger.info(f"已配置 Tavily 搜索，共 {len(tavily_keys)} 个 API Key")

        # 3. Brave Search（隐私优先，全球覆盖）
        if brave_keys:
            self._providers.append(BraveSearchProvider(brave_keys))
            logger.info(f"已配置 Brave 搜索，共 {len(brave_keys)} 个 API Key")

        # 4. SerpAPI 作为备选（每月 100 次）
        if serpapi_keys:
            self._providers.append(SerpAPISearchProvider(serpapi_keys))
            logger.info(f"已配置 SerpAPI 搜索，共 {len(serpapi_keys)} 个 API Key")

        # 5. MiniMax（Coding Plan Web Search，结构化结果）
        if minimax_keys:
            self._providers.append(MiniMaxSearchProvider(minimax_keys))
            logger.info(f"已配置 MiniMax 搜索，共 {len(minimax_keys)} 个 API Key")

        # 6. SearXNG（自建实例，无配额兜底，最后兜底）
        if searxng_base_urls:
            self._providers.append(SearXNGSearchProvider(searxng_base_urls))
            logger.info(f"已配置 SearXNG 搜索，共 {len(searxng_base_urls)} 个实例")
        
        if not self._providers:
            logger.warning("未配置任何搜索引擎 API Key，新闻搜索功能将不可用")

        # In-memory search result cache: {cache_key: (timestamp, SearchResponse)}
        self._cache: Dict[str, Tuple[float, 'SearchResponse']] = {}
        # Default cache TTL in seconds (10 minutes)
        self._cache_ttl: int = 600
    
    def search(self, query: str, max_results: int = 5, days: int = 7) -> SearchResponse:
        """
        执行搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            days: 搜索最近几天的时间范围（默认7天）
            
        Returns:
            SearchResponse 对象
        """
        # 检查缓存
        cache_key = f"{query}_{max_results}_{days}"
        current_time = time.time()
        cached = self._cache.get(cache_key)
        
        if cached:
            cache_time, cached_response = cached
            if current_time - cache_time < self._cache_ttl:
                logger.debug(f"使用缓存的搜索结果: {query}")
                return cached_response
        
        # 尝试所有搜索引擎，直到成功
        logger.info(f"开始搜索: {query}")
        for provider in self._providers:
            if provider.is_available:
                logger.info(f"尝试使用 {provider.name} 搜索")
                response = provider.search(query, max_results, days)
                if response.success and response.results:
                    logger.info(f"{provider.name} 搜索成功，返回 {len(response.results)} 条结果")
                    # 缓存结果
                    self._cache[cache_key] = (current_time, response)
                    return response
                else:
                    logger.info(f"{provider.name} 搜索失败: {response.error_message}")
        
        # 所有搜索引擎都失败
        logger.warning(f"所有搜索引擎都失败: {query}")
        return SearchResponse(
            query=query,
            results=[],
            provider="All",
            success=False,
            error_message="所有搜索引擎都失败"
        )


# 为了兼容旧代码，添加必要的类
class BochaSearchProvider(BaseSearchProvider):
    """博查搜索引擎（占位）"""
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            provider=self.name,
            success=False,
            error_message="Bocha 搜索未配置"
        )


class TavilySearchProvider(BaseSearchProvider):
    """Tavily搜索引擎（AI优化的搜索API）"""

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys, "Tavily")

    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        try:
            import requests

            url = "https://api.tavily.com/search"
            payload = {
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False
            }
            headers = {
                "Content-Type": "application/json",
                "api_key": api_key
            }

            response = requests.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code != 200:
                return SearchResponse(
                    query=query,
                    results=[],
                    provider=self.name,
                    success=False,
                    error_message=f"Tavily API错误: {response.status_code}"
                )

            data = response.json()
            results = []

            for item in data.get("results", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("content", "")[:200],
                    url=item.get("url", ""),
                    source="Tavily",
                    published_date=None
                ))

            return SearchResponse(
                query=query,
                results=results,
                provider=self.name,
                success=True
            )

        except Exception as e:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.name,
                success=False,
                error_message=str(e)
            )


class BraveSearchProvider(BaseSearchProvider):
    """Brave搜索引擎（占位）"""
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            provider=self.name,
            success=False,
            error_message="Brave 搜索未配置"
        )


class SerpAPISearchProvider(BaseSearchProvider):
    """SerpAPI搜索引擎（占位）"""
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            provider=self.name,
            success=False,
            error_message="SerpAPI 搜索未配置"
        )


class MiniMaxSearchProvider(BaseSearchProvider):
    """MiniMax搜索引擎（占位）"""
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            provider=self.name,
            success=False,
            error_message="MiniMax 搜索未配置"
        )


class SearXNGSearchProvider(BaseSearchProvider):
    """SearXNG搜索引擎（占位）"""
    def _do_search(self, query: str, api_key: str, max_results: int, days: int = 7) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=[],
            provider=self.name,
            success=False,
            error_message="SearXNG 搜索未配置"
        )
