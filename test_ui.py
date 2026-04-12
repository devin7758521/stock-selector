# -*- coding: utf-8 -*-
"""
测试UI是否能正常启动
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def test_ui():
    """测试UI"""
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.setWindowTitle("JusticePlutus - 测试")
    
    # 显示窗口
    window.show()
    
    # 测试更新结果
    test_results = [
        {
            'code': '600036',
            'name': '招商银行',
            'price': 35.50,
            'daily_amount_yi': 21.30,
            'ma25_weekly': 34.20,
            'vol_deviation_pct': 2.5,
            'ai_star_display': '⭐⭐⭐⭐',
            'llm_star_display': '⭐⭐⭐⭐⭐',
            'technical_analysis': {
                'macd': {'value': 0.5},
                'kdj': {'k': 60.5, 'd': 55.2, 'j': 71.1},
                'rsi': 65.3
            },
            'fundamental_analysis': {
                'roe': 15.2,
                'pe': 6.5,
                'pb': 0.9,
                'eps': 5.46,
                'revenue_growth': 8.5,
                'score': 75
            },
            'llm_analysis': {
                'sentiment_score': 85,
                'star_rating': 5,
                'trend_prediction': '看涨',
                'operation_advice': '买入',
                'star_reason': '基本面优秀，技术指标良好，市场情绪积极'
            }
        }
    ]
    
    window.update_results(test_results)
    window.update_detail(test_results[0])
    
    print("UI测试成功！")
    print("窗口已显示，请检查UI是否正常")
    
    # 运行应用（不退出）
    # sys.exit(app.exec())
    
    # 直接退出（仅测试）
    app.quit()

if __name__ == "__main__":
    test_ui()
