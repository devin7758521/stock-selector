# -*- coding: utf-8 -*-
"""
LLM 分析插件

Copyright (c) 2026 stock selector. All rights reserved.
"""

import sys
import os
import logging
from typing import Dict, Any, Optional

from screener.core.plugin import Plugin
from .analyzer import LLMAnalyzer
from .search_service import SearchService

logger = logging.getLogger("stock_selector.plugin.llm_analysis")


class LLMAnalsysisPlugin(Plugin):
    """
    LLM 分析插件
    集成 stock selector 的 AI 分析和新闻搜索功能
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化插件
        
        Args:
            name: 插件名称
            config: 插件配置
        """
        super().__init__(name, config)
        self.analyzer = None
        self.search_service = None
    
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            是否初始化成功
        """
        try:
            # 初始化 LLM 分析器
            self.analyzer = LLMAnalyzer()
            
            # 初始化搜索服务
            self.search_service = SearchService()
            
            logger.info("LLM 分析插件初始化成功")
            return True
        except Exception as e:
            logger.error(f"LLM 分析插件初始化失败: {e}")
            return False
    
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
        try:
            code = stock_data["code"]
            name = stock_data.get("name", f"股票{code}")
            
            # 构建分析上下文
            context = self._build_context(stock_data, df)
            
            # 搜索新闻
            news_context = self._search_news(code, name)
            
            # 执行 AI 分析
            result = self.analyzer.analyze(context, news_context)
            
            # 构建结果
            return {
                "llm_sentiment_score": result.sentiment_score,
                "llm_trend_prediction": result.trend_prediction,
                "llm_operation_advice": result.operation_advice,
                "llm_confidence_level": result.confidence_level,
                "llm_analysis_summary": result.analysis_summary,
                "llm_news_summary": result.news_summary,
                "llm_risk_warning": result.risk_warning,
                "llm_buy_reason": result.buy_reason,
                "llm_model_used": result.model_used,
                "llm_success": result.success,
                "llm_error_message": result.error_message,
                "llm_stars": result.stars,
                "llm_star_reason": result.star_reason
            }
        except Exception as e:
            logger.debug(f"LLM 分析失败: {e}")
            return {
                "llm_sentiment_score": 50,
                "llm_trend_prediction": "N/A",
                "llm_operation_advice": "N/A",
                "llm_confidence_level": "N/A",
                "llm_analysis_summary": "分析失败",
                "llm_news_summary": "N/A",
                "llm_risk_warning": "N/A",
                "llm_buy_reason": "N/A",
                "llm_model_used": "N/A",
                "llm_success": False,
                "llm_error_message": str(e),
                "llm_stars": 3,
                "llm_star_reason": "分析失败，无法给出打星理由"
            }
    
    def format_output(self, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        格式化输出
        
        Args:
            stock_data: 股票数据
            
        Returns:
            格式化的输出字符串
        """
        sentiment_score = stock_data.get('llm_sentiment_score', 50)
        operation_advice = stock_data.get('llm_operation_advice', 'N/A')
        confidence = stock_data.get('llm_confidence_level', 'N/A')
        stars = stock_data.get('llm_stars', 3)
        
        return f"LLM建议={operation_advice}  情绪分={sentiment_score}  置信度={confidence}  评级={'★' * stars}{'☆' * (5 - stars)}"
    
    def format_detailed_output(self, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        格式化详细输出
        
        Args:
            stock_data: 股票数据
            
        Returns:
            格式化的详细输出字符串
        """
        sentiment_score = stock_data.get('llm_sentiment_score', 50)
        operation_advice = stock_data.get('llm_operation_advice', 'N/A')
        confidence = stock_data.get('llm_confidence_level', 'N/A')
        stars = stock_data.get('llm_stars', 3)
        star_reason = stock_data.get('llm_star_reason', 'N/A')
        analysis_summary = stock_data.get('llm_analysis_summary', 'N/A')
        news_summary = stock_data.get('llm_news_summary', 'N/A')
        risk_warning = stock_data.get('llm_risk_warning', 'N/A')
        buy_reason = stock_data.get('llm_buy_reason', 'N/A')
        model_used = stock_data.get('llm_model_used', 'N/A')
        success = stock_data.get('llm_success', False)
        error_message = stock_data.get('llm_error_message', 'N/A')
        
        output = f"LLM 详细分析报告\n"
        output += f"==================================\n"
        output += f"评级: {'★' * stars}{'☆' * (5 - stars)}\n"
        output += f"打星理由: {star_reason}\n"
        output += f"情绪分: {sentiment_score}\n"
        output += f"操作建议: {operation_advice}\n"
        output += f"置信度: {confidence}\n"
        output += f"分析摘要: {analysis_summary}\n"
        output += f"新闻摘要: {news_summary}\n"
        output += f"风险警告: {risk_warning}\n"
        output += f"买入理由: {buy_reason}\n"
        output += f"使用模型: {model_used}\n"
        if not success:
            output += f"错误信息: {error_message}\n"
        output += "=================================="
        
        return output
    
    def _build_context(self, stock_data: Dict[str, Any], df: Any) -> Dict[str, Any]:
        """
        构建分析上下文
        
        Args:
            stock_data: 股票数据
            df: 股票K线数据
            
        Returns:
            分析上下文
        """
        context = {
            "code": stock_data["code"],
            "stock_name": stock_data.get("name", f"股票{stock_data['code']}"),
            "today": {
                "close": float(df['close'].iloc[-1]) if not df.empty else 0,
                "open": float(df['open'].iloc[-1]) if not df.empty else 0,
                "high": float(df['high'].iloc[-1]) if not df.empty else 0,
                "low": float(df['low'].iloc[-1]) if not df.empty else 0,
                "volume": float(df['volume'].iloc[-1]) if not df.empty else 0,
                "amount": float(df['amount'].iloc[-1]) if not df.empty else 0
            }
        }
        
        # 添加技术指标（来自技术分析插件）
        if 'technical_analysis' in stock_data:
            context["technical"] = stock_data['technical_analysis']
        elif not df.empty:
            # 计算MA作为备选
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            
            context["technical"] = {
                "ma5": float(df['ma5'].iloc[-1]),
                "ma10": float(df['ma10'].iloc[-1]),
                "ma20": float(df['ma20'].iloc[-1]),
                "latest_price": float(df['close'].iloc[-1])
            }
        
        # 添加基本面分析数据
        if 'fundamental_analysis' in stock_data:
            context["fundamental"] = stock_data['fundamental_analysis']
        
        # 添加量能分析数据
        if 'vol_deviation_pct' in stock_data:
            context["volume_analysis"] = {
                "vol_deviation_pct": stock_data['vol_deviation_pct'],
                "daily_amount_yi": stock_data.get('daily_amount_yi', 0)
            }
        
        return context
    
    def _search_news(self, code: str, name: str) -> Optional[str]:
        """
        搜索股票相关新闻
        
        Args:
            code: 股票代码
            name: 股票名称
            
        Returns:
            新闻上下文
        """
        try:
            if not self.search_service:
                return None
            
            query = f"{name} {code} 股票 新闻 公告"
            response = self.search_service.search(query, max_results=5, days=7)
            
            if response.success and response.results:
                logger.info(f"搜索到 {len(response.results)} 条新闻: {query}")
                return response.to_context(max_results=5)
            else:
                logger.debug(f"搜索新闻失败: {response.error_message}")
            
            return None
        except Exception as e:
            logger.debug(f"搜索新闻失败: {e}")
            return None
    
    def cleanup(self):
        """
        清理插件资源
        """
        pass
