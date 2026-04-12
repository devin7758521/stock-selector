# -*- coding: utf-8 -*-
"""
券商集成功能测试

测试东方财富、同花顺、长桥API接口是否正常工作
"""

import logging
from screener.eastmoney import EastMoneyAPI
from screener.tenjqka import 同花顺API
from screener.longbridge import LongbridgeAPI
from screener.eastmoney_utils import get_eastmoney_watchlist, get_tenjqka_watchlist, get_longbridge_watchlist

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

def test_eastmoney_api():
    """测试东方财富API"""
    print("\n" + "=" * 80)
    print("测试东方财富API")
    print("=" * 80)
    
    # 测试API初始化
    api = EastMoneyAPI()
    print("✅ 东方财富API初始化成功")
    
    # 测试获取自选股（不使用cookie）
    watchlist = get_eastmoney_watchlist()
    if watchlist:
        print(f"✅ 成功获取东方财富自选股: {len(watchlist)} 只")
    else:
        print("⚠️  未获取到东方财富自选股（需要设置cookie）")

def test_tenjqka_api():
    """测试同花顺API"""
    print("\n" + "=" * 80)
    print("测试同花顺API")
    print("=" * 80)
    
    # 测试API初始化
    api = 同花顺API()
    print("✅ 同花顺API初始化成功")
    
    # 测试获取自选股（不使用cookie）
    watchlist = get_tenjqka_watchlist()
    if watchlist:
        print(f"✅ 成功获取同花顺自选股: {len(watchlist)} 只")
    else:
        print("⚠️  未获取到同花顺自选股（需要设置cookie）")

def test_longbridge_api():
    """测试长桥API"""
    print("\n" + "=" * 80)
    print("测试长桥API")
    print("=" * 80)
    
    # 测试API初始化
    api = LongbridgeAPI()
    print("✅ 长桥API初始化成功")
    
    # 测试获取自选股（不使用cookie）
    watchlist = get_longbridge_watchlist()
    if watchlist:
        print(f"✅ 成功获取长桥自选股: {len(watchlist)} 只")
    else:
        print("⚠️  未获取到长桥自选股（需要设置cookie）")

if __name__ == "__main__":
    print("开始测试券商集成功能...")
    
    test_eastmoney_api()
    test_tenjqka_api()
    test_longbridge_api()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    print("提示：")
    print("1. 如果显示'未获取到自选股'，表示需要设置对应平台的cookie")
    print("2. 请参考EASTMONEY_CONFIG.md文档获取和设置cookie")
    print("3. 设置cookie后，可使用analyze_eastmoney.py脚本进行完整分析")
