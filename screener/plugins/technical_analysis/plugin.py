# -*- coding: utf-8 -*-
"""
技术指标分析插件

计算 MACD、KDJ、RSI 等技术指标，为 LLM 分析提供参考
"""

from typing import Dict, Optional
import pandas as pd
from screener.core.plugin import Plugin


class TechnicalAnalysisPlugin(Plugin):
    """技术指标分析插件"""
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
    
    def process(self, result: Dict, df: pd.DataFrame, config: Dict) -> Optional[Dict]:
        """计算技术指标"""
        try:
            code = result['code']
            self.logger.info(f"[技术分析] 开始计算 {code} 技术指标")
            # 计算 MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            
            # 计算 KDJ
            low = df['low'].rolling(9).min()
            high = df['high'].rolling(9).max()
            rsv = (df['close'] - low) / (high - low) * 100
            k = rsv.ewm(alpha=1/3).mean()
            d = k.ewm(alpha=1/3).mean()
            j = 3 * k - 2 * d
            
            # 计算 RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return {
                'technical_analysis': {
                    'macd': {
                        'value': float(macd.iloc[-1]),
                        'signal': float(signal.iloc[-1]),
                        'histogram': float(macd.iloc[-1] - signal.iloc[-1])
                    },
                    'kdj': {
                        'k': float(k.iloc[-1]),
                        'd': float(d.iloc[-1]),
                        'j': float(j.iloc[-1])
                    },
                    'rsi': float(rsi.iloc[-1])
                }
            }
        except Exception as e:
            self.logger.debug(f"计算技术指标失败: {e}")
            return None
    
    def format_output(self, result: Dict) -> str:
        """格式化输出"""
        if 'technical_analysis' in result:
            ta = result['technical_analysis']
            return f"技术指标: MACD={ta['macd']['value']:.2f}, KDJ=({ta['kdj']['k']:.1f},{ta['kdj']['d']:.1f},{ta['kdj']['j']:.1f}), RSI={ta['rsi']:.1f}"
        return ""
