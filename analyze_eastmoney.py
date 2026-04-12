# -*- coding: utf-8 -*-
"""
券商自选股分析示例

演示如何从东方财富、同花顺、长桥导入自选股和持仓股并进行分析
"""

import os
import logging
from screener.plugins.stock_list_analysis.plugin import StockListAnalysisPlugin
from screener.utils import load_config

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

def analyze_eastmoney_watchlist():
    """分析东方财富自选股"""
    print("=" * 80)
    print("分析东方财富自选股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取东方财富cookie（从环境变量或手动输入）
    cookie = os.environ.get("EASTMONEY_COOKIE", "")
    
    if not cookie:
        print("请输入东方财富cookie:")
        cookie = input().strip()
    
    # 分析自选股
    print("\n开始分析东方财富自选股...")
    result = plugin.analyze_eastmoney_watchlist(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

def analyze_eastmoney_portfolio():
    """分析东方财富持仓股"""
    print("=" * 80)
    print("分析东方财富持仓股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取东方财富cookie（从环境变量或手动输入）
    cookie = os.environ.get("EASTMONEY_COOKIE", "")
    
    if not cookie:
        print("请输入东方财富cookie:")
        cookie = input().strip()
    
    # 分析持仓股
    print("\n开始分析东方财富持仓股...")
    result = plugin.analyze_eastmoney_portfolio(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

def analyze_tenjqka_watchlist():
    """分析同花顺自选股"""
    print("=" * 80)
    print("分析同花顺自选股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取同花顺cookie（从环境变量或手动输入）
    cookie = os.environ.get("TENJQKA_COOKIE", "")
    
    if not cookie:
        print("请输入同花顺cookie:")
        cookie = input().strip()
    
    # 分析自选股
    print("\n开始分析同花顺自选股...")
    result = plugin.analyze_tenjqka_watchlist(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

def analyze_tenjqka_portfolio():
    """分析同花顺持仓股"""
    print("=" * 80)
    print("分析同花顺持仓股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取同花顺cookie（从环境变量或手动输入）
    cookie = os.environ.get("TENJQKA_COOKIE", "")
    
    if not cookie:
        print("请输入同花顺cookie:")
        cookie = input().strip()
    
    # 分析持仓股
    print("\n开始分析同花顺持仓股...")
    result = plugin.analyze_tenjqka_portfolio(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

def analyze_longbridge_watchlist():
    """分析长桥自选股"""
    print("=" * 80)
    print("分析长桥自选股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取长桥cookie（从环境变量或手动输入）
    cookie = os.environ.get("LONGBRIDGE_COOKIE", "")
    
    if not cookie:
        print("请输入长桥cookie:")
        cookie = input().strip()
    
    # 分析自选股
    print("\n开始分析长桥自选股...")
    result = plugin.analyze_longbridge_watchlist(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

def analyze_longbridge_portfolio():
    """分析长桥持仓股"""
    print("=" * 80)
    print("分析长桥持仓股")
    print("=" * 80)
    
    # 加载配置
    config = load_config("config.yaml")
    
    # 创建插件
    plugin = StockListAnalysisPlugin("stock_list_analysis", {"enabled": True})
    
    # 初始化插件
    if not plugin.initialize():
        print("❌ 插件初始化失败")
        return
    
    # 获取长桥cookie（从环境变量或手动输入）
    cookie = os.environ.get("LONGBRIDGE_COOKIE", "")
    
    if not cookie:
        print("请输入长桥cookie:")
        cookie = input().strip()
    
    # 分析持仓股
    print("\n开始分析长桥持仓股...")
    result = plugin.analyze_longbridge_portfolio(cookie=cookie, config=config)
    
    if result.get("success", False):
        print("\n✅ 分析完成！")
        
        # 生成报告
        report = plugin.generate_report(result)
        print("\n" + "=" * 80)
        print("分析报告:")
        print("=" * 80)
        print(report)
        
        # 导出结果
        export_result = plugin.export_results(result, "csv")
        print(f"\n{export_result}")
    else:
        print(f"\n❌ 分析失败: {result.get('message', '未知错误')}")

if __name__ == "__main__":
    print("请选择要分析的内容:")
    print("1. 东方财富自选股")
    print("2. 东方财富持仓股")
    print("3. 同花顺自选股")
    print("4. 同花顺持仓股")
    print("5. 长桥自选股")
    print("6. 长桥持仓股")
    
    choice = input("请输入选项 (1-6): ").strip()
    
    if choice == "1":
        analyze_eastmoney_watchlist()
    elif choice == "2":
        analyze_eastmoney_portfolio()
    elif choice == "3":
        analyze_tenjqka_watchlist()
    elif choice == "4":
        analyze_tenjqka_portfolio()
    elif choice == "5":
        analyze_longbridge_watchlist()
    elif choice == "6":
        analyze_longbridge_portfolio()
    else:
        print("无效选项")
