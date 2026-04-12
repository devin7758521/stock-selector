# -*- coding: utf-8 -*-
"""
基本面分析插件

获取 ROE、PE、PB 等财务数据，为 LLM 分析提供参考
"""

from typing import Dict, Optional
import pandas as pd
from screener.core.plugin import Plugin
from screener.datasources import fetch_financial_data


class FundamentalAnalysisPlugin(Plugin):
    """基本面分析插件"""
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
    
    def process(self, result: Dict, df: pd.DataFrame, config: Dict) -> Optional[Dict]:
        """获取基本面数据"""
        try:
            code = result['code']
            self.logger.info(f"[基本面分析] 开始获取 {code} 数据")
            financial_data = fetch_financial_data(code)
            self.logger.info(f"[基本面分析] {code} 原始数据: {financial_data}")

            if financial_data:
                roe = financial_data.get('roe', 0)
                pe = financial_data.get('pe', 0)
                pb = financial_data.get('pb', 0)
                eps = financial_data.get('eps', 0)
                revenue_growth = financial_data.get('revenue_growth', 0)
                
                # 计算基本面评分
                score = self.calculate_fundamental_score(roe, pe, pb, eps, revenue_growth)
                
                return {
                    'fundamental_analysis': {
                        'roe': roe,
                        'pe': pe,
                        'pb': pb,
                        'eps': eps,
                        'revenue_growth': revenue_growth,
                        'score': score
                    }
                }
        except Exception as e:
            self.logger.debug(f"获取基本面数据失败: {e}")
        return None
    
    def calculate_fundamental_score(self, roe, pe, pb, eps, revenue_growth):
        """计算基本面评分（0-100）"""
        score = 0
        if roe > 15:
            score += 25
        elif roe > 10:
            score += 20
        elif roe > 5:
            score += 15
        
        if 5 < pe < 20:
            score += 20
        elif pe < 30:
            score += 15
        
        if pb < 3:
            score += 15
        elif pb < 5:
            score += 10
        
        if eps > 0.5:
            score += 20
        elif eps > 0:
            score += 10
        
        if revenue_growth > 30:
            score += 20
        elif revenue_growth > 15:
            score += 15
        elif revenue_growth > 5:
            score += 10
        
        return min(score, 100)
    
    def format_output(self, result: Dict) -> str:
        """格式化输出"""
        if 'fundamental_analysis' in result:
            fa = result['fundamental_analysis']
            return f"基本面: ROE={fa['roe']:.2f}%, PE={fa['pe']:.1f}, PB={fa['pb']:.2f}, 评分={fa['score']}"
        return ""
