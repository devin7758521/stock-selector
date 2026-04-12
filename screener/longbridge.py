# -*- coding: utf-8 -*-
"""
长桥API接口

用于获取长桥自选股和持仓股数据

安全措施：
1. 不存储账号密码
2. 使用Cookie方式登录
3. 本地运行，避免网络传输敏感信息
4. 完善的错误处理
"""

import os
import json
import logging
import requests
from typing import List, Dict, Optional, Any

logger = logging.getLogger("justice.longbridge")


class LongbridgeAPI:
    """长桥API接口"""
    
    def __init__(self, cookie: Optional[str] = None):
        """
        初始化长桥API
        
        Args:
            cookie: 已登录的cookie字符串（推荐方式）
        """
        self.cookie = cookie
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json"
        }
        
        if cookie:
            self.session.cookies.update(self._parse_cookie(cookie))
    
    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        """解析cookie字符串"""
        cookies = {}
        for item in cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        return cookies
    
    def get_watchlist(self) -> List[Dict[str, str]]:
        """
        获取自选股列表
        
        Returns:
            自选股列表，格式：[{"code": "600036", "name": "招商银行"}]
        """
        try:
            url = "https://www.longbridgeapp.com/api/watchlist"
            params = {
                "page": 1,
                "limit": 1000
            }
            
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                stocks = []
                for item in data.get("data", {}).get("items", []):
                    stocks.append({
                        "code": item.get("code"),
                        "name": item.get("name")
                    })
                logger.info(f"成功获取长桥自选股: {len(stocks)} 只")
                return stocks
            else:
                logger.error(f"获取长桥自选股失败: {data.get('message', '未知错误')}")
                return []
                
        except Exception as e:
            logger.error(f"获取长桥自选股异常: {e}")
            return []
    
    def get_portfolio(self) -> List[Dict[str, Any]]:
        """
        获取持仓股列表
        
        Returns:
            持仓股列表，格式：[{"code": "600036", "name": "招商银行", "amount": 100, "cost": 35.5, "current": 36.2}]
        """
        try:
            url = "https://www.longbridgeapp.com/api/portfolio"
            
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                stocks = []
                for item in data.get("data", {}).get("positions", []):
                    stocks.append({
                        "code": item.get("code"),
                        "name": item.get("name"),
                        "amount": item.get("quantity"),
                        "cost": item.get("avg_cost"),
                        "current": item.get("current_price")
                    })
                logger.info(f"成功获取长桥持仓股: {len(stocks)} 只")
                return stocks
            else:
                logger.error(f"获取长桥持仓股失败: {data.get('message', '未知错误')}")
                return []
                
        except Exception as e:
            logger.error(f"获取长桥持仓股异常: {e}")
            return []
    
    def export_watchlist(self, filename: str = "longbridge_watchlist.json") -> bool:
        """
        导出自选股到文件
        
        Args:
            filename: 导出文件名
            
        Returns:
            是否导出成功
        """
        try:
            watchlist = self.get_watchlist()
            if watchlist:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(watchlist, f, ensure_ascii=False, indent=2)
                logger.info(f"长桥自选股已导出到: {filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"导出长桥自选股失败: {e}")
            return False
    
    def import_watchlist(self, filename: str = "longbridge_watchlist.json") -> List[Dict[str, str]]:
        """
        从文件导入自选股
        
        Args:
            filename: 导入文件名
            
        Returns:
            自选股列表
        """
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    watchlist = json.load(f)
                logger.info(f"从文件导入长桥自选股: {len(watchlist)} 只")
                return watchlist
            else:
                logger.error(f"文件不存在: {filename}")
                return []
        except Exception as e:
            logger.error(f"导入长桥自选股失败: {e}")
            return []
