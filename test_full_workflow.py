# -*- coding: utf-8 -*-
"""
测试完整的选股流程

验证：
1. 插件加载和初始化
2. 完整的选股流程
3. 插件执行和结果输出
4. 企业微信推送（如果配置）
"""

import logging
import time
from screener.core import StockSelector

# 设置详细日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def test_full_screening_workflow():
    """测试完整的选股流程"""
    print("=" * 80)
    print("测试完整的选股流程")
    print("=" * 80)
    
    start_time = time.time()
    
    try:
        # 创建选股器
        selector = StockSelector("config.yaml")
        
        print("\n1. 插件加载状态:")
        active_plugins = selector.plugin_manager.get_active_plugins()
        print(f"   激活的插件: {len(active_plugins)} 个")
        for plugin in active_plugins:
            print(f"   - {plugin.name}")
        
        print("\n2. 开始选股...")
        print("   这可能需要几分钟时间...")
        
        # 执行选股
        results = selector.run()
        
        elapsed_time = time.time() - start_time
        
        print(f"\n3. 选股完成!")
        print(f"   用时: {elapsed_time:.2f} 秒")
        print(f"   入选股票: {len(results)} 只")
        
        if results:
            print("\n4. 选股结果详情:")
            for i, stock in enumerate(results, 1):
                print(f"\n   [{i}] {stock['name']} ({stock['code']})")
                print(f"      价格: {stock['price']} 元")
                print(f"      偏离: {stock['vol_deviation_pct']}%")
                print(f"      日成交额: {stock['daily_amount_yi']} 亿")
                
                # 检查插件结果
                if 'ai_analysis' in stock:
                    print(f"      AI评级: {stock.get('ai_star_display', 'N/A')}")
                
                if 'llm_analysis' in stock:
                    stars = stock.get('llm_stars', 0)
                    print(f"      LLM评级: {'★' * stars}{'☆' * (5 - stars)}")
                    print(f"      LLM建议: {stock.get('llm_operation_advice', 'N/A')}")
                
                if 'technical_analysis' in stock:
                    ta = stock['technical_analysis']
                    print(f"      MACD: {ta['macd']['value']:.2f}")
                    print(f"      RSI: {ta['rsi']:.1f}")
                
                if 'fundamental_analysis' in stock:
                    fa = stock['fundamental_analysis']
                    print(f"      ROE: {fa['roe']:.2f}%")
                    print(f"      PE: {fa['pe']:.1f}")
                    print(f"      基本面评分: {fa['score']}")
        else:
            print("\n4. 没有符合条件的股票")
        
        print("\n5. 测试完成!")
        print("=" * 80)
        
        return results
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 清理测试文档
        try:
            from cleanup_test import cleanup_test_files
            print("\n清理测试文档...")
            cleanup_test_files()
        except Exception as e:
            print(f"清理测试文档失败: {e}")

if __name__ == "__main__":
    test_full_screening_workflow()
