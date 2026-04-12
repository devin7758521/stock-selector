# -*- coding: utf-8 -*-
"""
测试单只股票的完整分析流程
"""

import logging
from screener.core import StockSelector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def test_single_stock():
    """测试单只股票的完整分析"""
    print("=" * 80)
    print("测试单只股票的完整分析流程")
    print("=" * 80)
    
    try:
        selector = StockSelector("config.yaml")
        
        # 测试松炀资源
        code = "603863"
        name = "松炀资源"
        
        print(f"\n测试股票: {name} ({code})")
        
        # 处理单只股票
        result = selector.process_stock(code, name)
        
        if result:
            print("\n✅ 股票处理成功！")
            print(f"\n基本信息:")
            print(f"  价格: {result.get('price', 'N/A')}")
            print(f"  偏离: {result.get('vol_deviation_pct', 'N/A')}%")
            print(f"  日成交额: {result.get('daily_amount_yi', 'N/A')}亿")
            
            # 检查技术分析
            if 'technical_analysis' in result:
                ta = result['technical_analysis']
                print(f"\n技术分析:")
                print(f"  MACD: {ta.get('macd', {}).get('value', 'N/A')}")
                print(f"  RSI: {ta.get('rsi', 'N/A')}")
                print(f"  KDJ: {ta.get('kdj', 'N/A')}")
            else:
                print("\n⚠️  未找到技术分析数据")
            
            # 检查基本面分析
            if 'fundamental_analysis' in result:
                fa = result['fundamental_analysis']
                print(f"\n基本面分析:")
                print(f"  ROE: {fa.get('roe', 'N/A')}")
                print(f"  PE: {fa.get('pe', 'N/A')}")
                print(f"  PB: {fa.get('pb', 'N/A')}")
                print(f"  评分: {fa.get('score', 'N/A')}")
            else:
                print("\n⚠️  未找到基本面分析数据")
            
            # 检查LLM分析
            if 'llm_stars' in result:
                print(f"\nLLM分析:")
                print(f"  星级: {'★' * result['llm_stars']}{'☆' * (5 - result['llm_stars'])}")
                print(f"  加权分: {result.get('llm_weighted_score', 'N/A')}")
                print(f"  操作建议: {result.get('llm_operation_advice', 'N/A')}")
                
                # 推荐理由
                if 'llm_recommendation_reason' in result:
                    print(f"\n推荐理由:")
                    print(result['llm_recommendation_reason'])
            else:
                print("\n⚠️  未找到LLM分析数据")
            
        else:
            print("\n❌ 股票处理失败")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理测试文档
        try:
            from cleanup_test import cleanup_test_files
            print("\n清理测试文档...")
            cleanup_test_files()
        except Exception as e:
            print(f"清理测试文档失败: {e}")

if __name__ == "__main__":
    test_single_stock()
