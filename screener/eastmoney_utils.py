# -*- coding: utf-8 -*-
"""
东方财富、同花顺、长桥工具类

提供东方财富、同花顺、长桥自选股和持仓股导入功能
"""

import os
import logging
from typing import List, Dict, Optional

from screener.eastmoney import EastMoneyAPI
from screener.tenjqka import 同花顺API
from screener.longbridge import LongbridgeAPI
from screener.utils import load_config

logger = logging.getLogger("justice.broker.utils")

def get_eastmoney_watchlist(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取东方财富自选股
    
    Args:
        cookie: 东方财富cookie
        
    Returns:
        自选股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("EASTMONEY_COOKIE", "")
        if not cookie:
            logger.warning("未提供东方财富cookie，无法获取自选股")
            return []
    
    api = EastMoneyAPI(cookie=cookie)
    return api.get_watchlist()

def get_eastmoney_portfolio(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取东方财富持仓股
    
    Args:
        cookie: 东方财富cookie
        
    Returns:
        持仓股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("EASTMONEY_COOKIE", "")
        if not cookie:
            logger.warning("未提供东方财富cookie，无法获取持仓股")
            return []
    
    api = EastMoneyAPI(cookie=cookie)
    return api.get_portfolio()

def export_eastmoney_watchlist(filename: str = "eastmoney_watchlist.json", cookie: Optional[str] = None) -> bool:
    """
    导出自选股到文件
    
    Args:
        filename: 导出文件名
        cookie: 东方财富cookie
        
    Returns:
        是否导出成功
    """
    if not cookie:
        cookie = os.environ.get("EASTMONEY_COOKIE", "")
        if not cookie:
            logger.warning("未提供东方财富cookie，无法导出自选股")
            return False
    
    api = EastMoneyAPI(cookie=cookie)
    return api.export_watchlist(filename)

def import_eastmoney_watchlist(filename: str = "eastmoney_watchlist.json") -> List[Dict[str, str]]:
    """
    从文件导入自选股
    
    Args:
        filename: 导入文件名
        
    Returns:
        自选股列表
    """
    api = EastMoneyAPI()
    return api.import_watchlist(filename)

# 同花顺相关函数
def get_tenjqka_watchlist(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取同花顺自选股
    
    Args:
        cookie: 同花顺cookie
        
    Returns:
        自选股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("TENJQKA_COOKIE", "")
        if not cookie:
            logger.warning("未提供同花顺cookie，无法获取自选股")
            return []
    
    api = 同花顺API(cookie=cookie)
    return api.get_watchlist()

def get_tenjqka_portfolio(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取同花顺持仓股
    
    Args:
        cookie: 同花顺cookie
        
    Returns:
        持仓股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("TENJQKA_COOKIE", "")
        if not cookie:
            logger.warning("未提供同花顺cookie，无法获取持仓股")
            return []
    
    api = 同花顺API(cookie=cookie)
    return api.get_portfolio()

# 长桥相关函数
def get_longbridge_watchlist(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取长桥自选股
    
    Args:
        cookie: 长桥cookie
        
    Returns:
        自选股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("LONGBRIDGE_COOKIE", "")
        if not cookie:
            logger.warning("未提供长桥cookie，无法获取自选股")
            return []
    
    api = LongbridgeAPI(cookie=cookie)
    return api.get_watchlist()

def get_longbridge_portfolio(cookie: Optional[str] = None) -> List[Dict[str, str]]:
    """
    获取长桥持仓股
    
    Args:
        cookie: 长桥cookie
        
    Returns:
        持仓股列表
    """
    if not cookie:
        # 尝试从环境变量获取
        cookie = os.environ.get("LONGBRIDGE_COOKIE", "")
        if not cookie:
            logger.warning("未提供长桥cookie，无法获取持仓股")
            return []
    
    api = LongbridgeAPI(cookie=cookie)
    return api.get_portfolio()
