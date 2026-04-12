# -*- coding: utf-8 -*-
"""
测试选股流程中的插件执行
"""

import logging
from screener.core import StockSelector

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

def test_stock_processing():
    """测试股票处理过程中的插件执行"""
    print("=== 测试股票处理 ===")
    
    # 创建选股器
    selector = StockSelector("config.yaml")
    
    # 测试处理一只股票
    test_stock = ("600036", "招商银行")
    code, name = test_stock
    
    print(f"\n测试处理股票: {name} ({code})")
    result = selector.process_stock(code, name)
    
    if result:
        print("\n=== 处理结果 ===")
        print(f"股票: {result['name']} ({result['code']})")
        print(f"价格: {result['price']}")
        print(f"偏离: {result['vol_deviation_pct']}%")
        print(f"日成交额: {result['daily_amount_yi']}亿")
        
        # 检查插件结果
        if 'ai_analysis' in result:
            print("\n=== AI分析结果 ===")
            print(f"AI信号: {result.get('ai_buy_signal')}")
            print(f"AI评分: {result.get('ai_signal_score')}")
            print(f"AI评级: {result.get('ai_star_display')}")
        
        if 'llm_analysis' in result:
            print("\n=== LLM分析结果 ===")
            print(f"LLM建议: {result.get('llm_operation_advice')}")
            print(f"情绪分: {result.get('llm_sentiment_score')}")
            print(f"置信度: {result.get('llm_confidence_level')}")
            print(f"评级: {'★' * result.get('llm_stars', 0)}{'☆' * (5 - result.get('llm_stars', 0))}")
            print(f"模型: {result.get('llm_model_used')}")
        
        if 'technical_analysis' in result:
            print("\n=== 技术分析结果 ===")
            ta = result['technical_analysis']
            print(f"MACD: {ta['macd']['value']:.2f}")
            print(f"KDJ: ({ta['kdj']['k']:.1f}, {ta['kdj']['d']:.1f}, {ta['kdj']['j']:.1f})")
            print(f"RSI: {ta['rsi']:.1f}")
        
        if 'fundamental_analysis' in result:
            print("\n=== 基本面分析结果 ===")
            fa = result['fundamental_analysis']
            print(f"ROE: {fa['roe']:.2f}%")
            print(f"PE: {fa['pe']:.1f}")
            print(f"PB: {fa['pb']:.2f}")
            print(f"评分: {fa['score']}")
    else:
        print("处理失败")

if __name__ == "__main__":
    test_stock_processing()
