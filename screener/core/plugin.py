# -*- coding: utf-8 -*-
"""
插件管理模块
"""

import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger("stock_selector.plugin")


class Plugin(ABC):
    """
    插件基类
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化插件
        
        Args:
            name: 插件名称
            config: 插件配置
        """
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)
        self.logger = logging.getLogger(f"stock_selector.plugin.{name}")
    
    @abstractmethod
    def process(self, stock_data: Dict[str, Any], df: Any, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理股票数据
        
        Args:
            stock_data: 股票数据
            df: 股票K线数据
            config: 全局配置
            
        Returns:
            处理后的结果
        """
        pass
    
    def format_output(self, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        格式化输出
        
        Args:
            stock_data: 股票数据
            
        Returns:
            格式化的输出字符串
        """
        return None
    
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            是否初始化成功
        """
        return True
    
    def cleanup(self):
        """
        清理插件资源
        """
        pass


class PluginManager:
    """
    插件管理器
    """
    
    def __init__(self):
        """
        初始化插件管理器
        """
        self.plugins: Dict[str, Plugin] = {}
    
    def load_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        加载插件
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            
        Returns:
            是否加载成功
        """
        try:
            # 这里可以根据插件名称动态导入插件
            # 暂时支持内置插件
            if plugin_name == "ai_analysis":
                from screener.ai.stock_analyzer import analyze_stock
                
                class AIAnalysisPlugin(Plugin):
                    """AI分析插件"""
                    
                    def process(self, stock_data: Dict[str, Any], df: Any, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                        try:
                            ai_result = analyze_stock(df, stock_data["code"])
                            return {
                                "ai_buy_signal": ai_result.buy_signal.value,
                                "ai_signal_score": ai_result.signal_score,
                                "ai_trend_status": ai_result.trend_status.value,
                                "ai_macd_signal": ai_result.macd_signal,
                                "ai_rsi_signal": ai_result.rsi_signal,
                                "ai_sentiment_score": ai_result.sentiment_score,
                                "ai_sentiment_signal": ai_result.sentiment_signal,
                                "ai_star_rating": ai_result.star_rating,
                                "ai_star_display": ai_result.star_display,
                                "ai_rating_reason": ai_result.rating_reason
                            }
                        except Exception as e:
                            logger.debug(f"AI分析失败: {e}")
                            return {
                                "ai_buy_signal": "N/A",
                                "ai_signal_score": 0,
                                "ai_trend_status": "N/A",
                                "ai_macd_signal": "N/A",
                                "ai_rsi_signal": "N/A",
                                "ai_sentiment_score": 50.0,
                                "ai_sentiment_signal": "N/A",
                                "ai_star_rating": 0,
                                "ai_star_display": "",
                                "ai_rating_reason": "N/A"
                            }
                    
                    def format_output(self, stock_data: Dict[str, Any]) -> Optional[str]:
                        star_display = stock_data.get('ai_star_display', '')
                        sentiment = stock_data.get('ai_sentiment_signal', 'N/A')
                        return f"AI信号={stock_data.get('ai_buy_signal', 'N/A')}  AI评分={stock_data.get('ai_signal_score', 0)}  评级={star_display}  情绪={sentiment}"
                
                plugin = AIAnalysisPlugin(plugin_name, config)
                if plugin.initialize():
                    self.plugins[plugin_name] = plugin
                    return True
            
            elif plugin_name == "llm_analysis":
                from screener.plugins.llm_analysis.plugin_enhanced import LLMAnalsysisPlugin
                plugin = LLMAnalsysisPlugin(plugin_name, config)
                if plugin.initialize():
                    self.plugins[plugin_name] = plugin
                    return True
            elif plugin_name == "stock_list_analysis":
                from screener.plugins.stock_list_analysis import StockListAnalysisPlugin
                plugin = StockListAnalysisPlugin(plugin_name, config)
                if plugin.initialize():
                    self.plugins[plugin_name] = plugin
                    return True
            elif plugin_name == "technical_analysis":
                from screener.plugins.technical_analysis.plugin import TechnicalAnalysisPlugin
                plugin = TechnicalAnalysisPlugin(plugin_name, config)
                if plugin.initialize():
                    self.plugins[plugin_name] = plugin
                    return True
            elif plugin_name == "fundamental_analysis":
                from screener.plugins.fundamental_analysis.plugin import FundamentalAnalysisPlugin
                plugin = FundamentalAnalysisPlugin(plugin_name, config)
                if plugin.initialize():
                    self.plugins[plugin_name] = plugin
                    return True
            
            # 可以添加更多内置插件
            
        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 失败: {e}")
        
        return False
    
    def get_active_plugins(self) -> List[Plugin]:
        """
        获取所有激活的插件
        
        Returns:
            激活的插件列表
        """
        return [plugin for plugin in self.plugins.values() if plugin.enabled]
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        获取指定插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件实例
        """
        return self.plugins.get(plugin_name)
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否卸载成功
        """
        if plugin_name in self.plugins:
            try:
                self.plugins[plugin_name].cleanup()
                del self.plugins[plugin_name]
                return True
            except Exception as e:
                logger.error(f"卸载插件 {plugin_name} 失败: {e}")
        return False
    
    def clear_plugins(self):
        """
        清空所有插件
        """
        for plugin in self.plugins.values():
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"清理插件 {plugin.name} 失败: {e}")
        self.plugins.clear()
