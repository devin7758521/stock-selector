# -*- coding: utf-8 -*-
"""
LLM 分析插件（增强版）

集成多维度分析：
1. 技术面分析
2. 基本面分析
3. 消息面分析
4. 政策面分析
5. 市场环境分析

权重机制：LLM(50%) > AI(30%) > 技术指标(20%)

Copyright (c) 2026 stock selector. All rights reserved.
"""

import sys
import os
import logging
from typing import Dict, Any, Optional

from screener.core.plugin import Plugin
from .analyzer_enhanced import EnhancedLLMAnalyzer
from .search_service import SearchService

logger = logging.getLogger("stock_selector.plugin.llm_analysis")


class LLMAnalysisPlugin(Plugin):
    """
    LLM 分析插件（增强版）
    
    功能：
    1. 多维度综合分析
    2. 权重机制：LLM > AI > 技术指标
    3. 国内外财经政治形势分析
    4. 详细的推理过程和打星理由
    5. 预留真正的LLM API接口
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
            # 获取LLM配置（环境变量优先）
            llm_config = self.config.get('llm', {})
            model = llm_config.get('model') or os.environ.get('LLM_MODEL', 'deepseek')

            # 根据模型选择对应的API Key
            if "gemini" in model.lower():
                api_key = llm_config.get('api_key') or os.environ.get('GEMINI_API_KEY', '')
            else:
                api_key = llm_config.get('api_key') or os.environ.get('DEEPSEEK_API_KEY', '')

            # 获取Tavily API Key（可选，用于更精准的AI搜索）
            tavily_keys = []
            tavily_key = os.environ.get('TAVILY_API_KEY', '')
            if tavily_key:
                tavily_keys = [k.strip() for k in tavily_key.split(',') if k.strip()]
            
            # 初始化增强版LLM分析器
            self.analyzer = EnhancedLLMAnalyzer(api_key=api_key, model=model)

            # 初始化搜索服务
            self.search_service = SearchService(tavily_keys=tavily_keys if tavily_keys else None)

            logger.info(f"LLM 分析插件初始化成功（模型: {model}）")
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
            
            logger.info(f"开始LLM分析: {name} ({code})")
            
            # 构建分析上下文
            context = self._build_context(stock_data, df)
            
            # 搜索新闻
            news_context = self._search_news(code, name)
            
            # AI 插件把字段写在 stock_data 顶层，这里组装成 dict 供增强分析器使用
            ai_analysis = stock_data.get('ai_analysis')
            if ai_analysis is None and "ai_signal_score" in stock_data:
                ai_analysis = {
                    "ai_signal_score": stock_data.get("ai_signal_score", 50),
                    "ai_buy_signal": stock_data.get("ai_buy_signal", "N/A"),
                    "ai_trend_status": stock_data.get("ai_trend_status", "N/A"),
                    "ai_rating_reason": stock_data.get("ai_rating_reason", "N/A"),
                }

            # 若配置顺序有误或技术插件失败，用 K 线就地补算一层（与技术分析插件一致）
            technical_analysis = stock_data.get("technical_analysis")
            if not technical_analysis and df is not None and not getattr(df, "empty", True):
                from screener.plugins.technical_analysis.plugin import TechnicalAnalysisPlugin

                _ta_patch = TechnicalAnalysisPlugin("_inline_", {}).process(
                    stock_data, df, config
                )
                if _ta_patch and _ta_patch.get("technical_analysis"):
                    technical_analysis = _ta_patch["technical_analysis"]

            fundamental_analysis = stock_data.get("fundamental_analysis")
            
            # 执行增强版LLM分析
            result = self.analyzer.analyze(
                context=context,
                news_context=news_context,
                ai_analysis=ai_analysis,
                technical_analysis=technical_analysis,
                fundamental_analysis=fundamental_analysis
            )
            
            news_success = bool(news_context)
            
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
                "llm_star_reason": result.star_reason,
                "llm_news_success": news_success,
                
                # 新增：详细分析维度
                "llm_technical_detail": result.technical_analysis_detail,
                "llm_fundamental_detail": result.fundamental_analysis_detail,
                "llm_news_detail": result.news_analysis_detail,
                "llm_policy_detail": result.policy_analysis_detail,
                "llm_market_detail": result.market_environment_analysis,
                
                # 新增：推荐理由（综合推理后的结论）
                "llm_recommendation_reason": result.recommendation_reason,
                
                # 新增：权重计算
                "llm_weighted_score": result.weighted_score,
                "llm_weight": result.llm_weight,
                "ai_weight": result.ai_weight,
                "technical_weight": result.technical_weight
            }
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}", exc_info=True)
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
                "llm_star_reason": "分析失败，无法给出打星理由",
                "llm_technical_detail": "N/A",
                "llm_fundamental_detail": "N/A",
                "llm_news_detail": "N/A",
                "llm_policy_detail": "N/A",
                "llm_market_detail": "N/A",
                "llm_recommendation_reason": "分析失败",
                "llm_weighted_score": 50.0
            }
    
    def format_output(self, stock_data: Dict[str, Any]) -> Optional[str]:
        """
        格式化输出（增强版）
        
        Args:
            stock_data: 股票数据
            
        Returns:
            格式化的输出字符串
        """
        output_parts = []
        
        # 基本评级
        stars = stock_data.get('llm_stars', 3)
        star_display = '★' * stars + '☆' * (5 - stars)
        operation_advice = stock_data.get('llm_operation_advice', 'N/A')
        confidence = stock_data.get('llm_confidence_level', 'N/A')
        weighted_score = stock_data.get('llm_weighted_score', 50.0)
        
        output_parts.append(f"LLM评级={star_display}({stars}星)")
        output_parts.append(f"建议={operation_advice}")
        output_parts.append(f"置信度={confidence}")
        output_parts.append(f"加权分={weighted_score:.1f}")
        
        # 打星理由
        star_reason = stock_data.get('llm_star_reason', '')
        if star_reason:
            output_parts.append(f"理由={star_reason}")
        
        return "  ".join(output_parts)
    
    def format_detailed_output(self, stock_data: Dict[str, Any]) -> str:
        """
        格式化详细输出
        
        Args:
            stock_data: 股票数据
            
        Returns:
            详细的分析报告
        """
        lines = []
        lines.append("=" * 80)
        lines.append("【LLM深度分析报告】")
        lines.append("=" * 80)
        
        # 基本信息
        name = stock_data.get('name', '未知')
        code = stock_data.get('code', '未知')
        lines.append(f"\n股票: {name} ({code})")
        
        # 综合评级
        stars = stock_data.get('llm_stars', 3)
        star_display = '★' * stars + '☆' * (5 - stars)
        weighted_score = stock_data.get('llm_weighted_score', 50.0)
        lines.append(f"\n【综合评级】{star_display} ({stars}星) - 加权总分: {weighted_score:.1f}")
        
        # 推荐理由（综合推理后的结论）
        recommendation_reason = stock_data.get('llm_recommendation_reason', '')
        if recommendation_reason:
            lines.append(f"\n【推荐理由】\n{recommendation_reason}")
        
        # 操作建议
        operation_advice = stock_data.get('llm_operation_advice', 'N/A')
        confidence = stock_data.get('llm_confidence_level', 'N/A')
        trend = stock_data.get('llm_trend_prediction', 'N/A')
        lines.append(f"\n【操作建议】{operation_advice}（置信度: {confidence}）")
        lines.append(f"【趋势预测】{trend}")
        
        # 风险警告
        risk_warning = stock_data.get('llm_risk_warning', '')
        if risk_warning:
            lines.append(f"\n【风险提示】\n{risk_warning}")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)
    
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
