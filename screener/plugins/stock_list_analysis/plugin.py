# -*- coding: utf-8 -*-
"""
股票列表分析插件

Copyright (c) 2026 stock selector. All rights reserved.
"""

import sys
import os
import logging
import pandas as pd
from typing import List, Dict, Any, Optional

from screener.core.plugin import Plugin
from screener.datasources import fetch_daily_kline, fetch_stock_list
from screener.ai.stock_analyzer import analyze_stock
from screener.plugins.llm_analysis.plugin import LLMAnalysisPlugin
from screener.eastmoney_utils import get_eastmoney_watchlist, get_eastmoney_portfolio, get_tenjqka_watchlist, get_tenjqka_portfolio, get_longbridge_watchlist, get_longbridge_portfolio

logger = logging.getLogger("stock_selector.plugins.stock_list_analysis")


class StockListAnalysisPlugin(Plugin):
    """股票列表分析插件"""
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.llm_plugin = None
        self.enabled = config.get("enabled", True)
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            # 初始化 LLM 分析插件
            self.llm_plugin = LLMAnalysisPlugin("llm_analysis", {"enabled": True})
            self.llm_plugin.initialize()
            
            logger.info("股票列表分析插件初始化成功")
            return True
        except Exception as e:
            logger.error(f"股票列表分析插件初始化失败: {e}")
            return False
    
    def process(self, stock_data: Dict[str, Any], df: Any, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理股票数据（符合基类要求）"""
        # 这里保持基类接口兼容，实际功能通过 analyze_stock_list 方法实现
        return {"success": True, "message": "请使用 analyze_stock_list 方法分析股票列表"}
    
    def analyze_stock_list(self, stock_codes: List[str], config: dict = None) -> Dict[str, Any]:
        """分析股票列表"""
        if not self.enabled:
            return {"success": False, "message": "插件未启用"}
        
        results = {}
        star_rated_stocks = []
        
        # 获取股票名称映射
        stock_name_map = {}
        stock_list_df = fetch_stock_list(config or {})
        if stock_list_df is not None:
            for _, row in stock_list_df.iterrows():
                stock_name_map[row["code"]] = row["name"]
        
        for code in stock_codes:
            try:
                # 获取真实股票名称
                stock_name = stock_name_map.get(code, f"股票{code}")
                logger.info(f"分析股票: {code} ({stock_name})")
                
                # 获取股票数据
                stock_data = {"code": code, "name": stock_name}
                df = fetch_daily_kline(code, config or {})
                
                if df is None or df.empty:
                    logger.warning(f"获取股票 {code} ({stock_name}) 数据失败")
                    results[code] = {
                        "success": False,
                        "message": "获取数据失败"
                    }
                    continue
                
                # AI 分析
                ai_result = analyze_stock(df, code)
                
                # LLM 分析
                llm_result = self.llm_plugin.process(stock_data, df, config or {})
                
                # 综合分析结果
                combined_result = self._combine_results(ai_result, llm_result)
                # 添加股票名称到结果中
                combined_result["name"] = stock_name
                
                # 提取打星评级
                if combined_result.get("star_rating", 0) > 0:
                    star_rated_stocks.append({
                        "code": code,
                        "name": stock_name,
                        "star_rating": combined_result["star_rating"],
                        "emotion_score": combined_result["emotion_score"]
                    })
                
                results[code] = combined_result
                
            except Exception as e:
                logger.error(f"分析股票 {code} 失败: {e}")
                results[code] = {
                    "success": False,
                    "message": str(e)
                }
        
        # 处理五星限制（最多两个五星）
        star_rated_stocks = self._handle_star_limit(star_rated_stocks)
        
        # 更新结果中的打星评级
        for stock in star_rated_stocks:
            if stock["code"] in results:
                results[stock["code"]]["star_rating"] = stock["star_rating"]
        
        return {
            "success": True,
            "results": results,
            "star_rated_stocks": star_rated_stocks
        }
    
    def analyze_eastmoney_watchlist(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析东方财富自选股
        
        Args:
            cookie: 东方财富cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析东方财富自选股")
        
        # 获取自选股列表
        watchlist = get_eastmoney_watchlist(cookie=cookie)
        
        if not watchlist:
            logger.warning("未获取到东方财富自选股")
            return {"success": False, "message": "未获取到自选股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in watchlist]
        logger.info(f"获取到自选股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def analyze_eastmoney_portfolio(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析东方财富持仓股
        
        Args:
            cookie: 东方财富cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析东方财富持仓股")
        
        # 获取持仓股列表
        portfolio = get_eastmoney_portfolio(cookie=cookie)
        
        if not portfolio:
            logger.warning("未获取到东方财富持仓股")
            return {"success": False, "message": "未获取到持仓股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in portfolio]
        logger.info(f"获取到持仓股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def analyze_tenjqka_watchlist(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析同花顺自选股
        
        Args:
            cookie: 同花顺cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析同花顺自选股")
        
        # 获取自选股列表
        watchlist = get_tenjqka_watchlist(cookie=cookie)
        
        if not watchlist:
            logger.warning("未获取到同花顺自选股")
            return {"success": False, "message": "未获取到自选股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in watchlist]
        logger.info(f"获取到自选股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def analyze_tenjqka_portfolio(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析同花顺持仓股
        
        Args:
            cookie: 同花顺cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析同花顺持仓股")
        
        # 获取持仓股列表
        portfolio = get_tenjqka_portfolio(cookie=cookie)
        
        if not portfolio:
            logger.warning("未获取到同花顺持仓股")
            return {"success": False, "message": "未获取到持仓股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in portfolio]
        logger.info(f"获取到持仓股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def analyze_longbridge_watchlist(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析长桥自选股
        
        Args:
            cookie: 长桥cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析长桥自选股")
        
        # 获取自选股列表
        watchlist = get_longbridge_watchlist(cookie=cookie)
        
        if not watchlist:
            logger.warning("未获取到长桥自选股")
            return {"success": False, "message": "未获取到自选股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in watchlist]
        logger.info(f"获取到自选股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def analyze_longbridge_portfolio(self, cookie: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        分析长桥持仓股
        
        Args:
            cookie: 长桥cookie
            config: 配置信息
            
        Returns:
            分析结果
        """
        logger.info("开始分析长桥持仓股")
        
        # 获取持仓股列表
        portfolio = get_longbridge_portfolio(cookie=cookie)
        
        if not portfolio:
            logger.warning("未获取到长桥持仓股")
            return {"success": False, "message": "未获取到持仓股"}
        
        # 提取股票代码
        stock_codes = [stock["code"] for stock in portfolio]
        logger.info(f"获取到持仓股: {len(stock_codes)} 只")
        
        # 分析股票列表
        return self.analyze_stock_list(stock_codes, config)
    
    def _combine_results(self, ai_result, llm_result: Dict[str, Any]) -> Dict[str, Any]:
        """综合 AI 分析和 LLM 分析结果"""
        # 将 AI 分析结果转换为字典
        ai_result_dict = ai_result.to_dict()
        
        combined = {
            "success": llm_result.get("success", False),
            "emotion_score": (ai_result_dict.get("sentiment_score", 50) + llm_result.get("emotion_score", 50)) / 2,
            "trend_prediction": llm_result.get("trend_prediction", ai_result_dict.get("trend_status", "震荡")),
            "operation_suggestion": llm_result.get("operation_suggestion", ai_result_dict.get("buy_signal", "持有")),
            "confidence": llm_result.get("confidence", "中"),
            "analysis_summary": llm_result.get("analysis_summary", ""),
            "news_summary": llm_result.get("news_summary", ""),
            "policy_impact": llm_result.get("policy_impact", ""),
            "risk_tips": llm_result.get("risk_tips", ""),
            "operation_reason": llm_result.get("operation_reason", ""),
            "used_model": llm_result.get("used_model", ""),
            "error_message": llm_result.get("error_message", "")
        }
        
        # 计算打星评级
        combined["star_rating"] = self._calculate_star_rating(combined["emotion_score"])
        
        return combined
    
    def _calculate_star_rating(self, emotion_score: float) -> int:
        """根据情绪分计算打星评级"""
        if emotion_score >= 90:
            return 5
        elif emotion_score >= 80:
            return 4
        elif emotion_score >= 70:
            return 3
        elif emotion_score >= 60:
            return 2
        elif emotion_score >= 50:
            return 1
        else:
            return 0
    
    def _handle_star_limit(self, star_rated_stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理五星限制，最多两个五星"""
        # 按打星评级和情绪分排序
        star_rated_stocks.sort(key=lambda x: (x["star_rating"], x["emotion_score"]), reverse=True)
        
        # 统计五星股票数量
        five_star_count = sum(1 for stock in star_rated_stocks if stock["star_rating"] == 5)
        
        # 如果五星股票超过两个，降级多余的五星股票
        if five_star_count > 2:
            five_star_stocks = [stock for stock in star_rated_stocks if stock["star_rating"] == 5]
            # 保留情绪分最高的两个五星股票，其余降级为四星
            for i, stock in enumerate(five_star_stocks[2:]):
                stock["star_rating"] = 4
        
        return star_rated_stocks
    
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成分析报告"""
        if not analysis_result.get("success", False):
            return "分析失败: " + analysis_result.get("message", "未知错误")
        
        results = analysis_result.get("results", {})
        star_rated_stocks = analysis_result.get("star_rated_stocks", [])
        
        report = []
        report.append("# 股票列表分析报告")
        report.append("")
        report.append(f"## 分析概览")
        report.append(f"- 分析股票数量: {len(results)}")
        report.append(f"- 成功分析: {sum(1 for r in results.values() if r.get('success', False))}")
        report.append(f"- 五星股票: {sum(1 for stock in star_rated_stocks if stock['star_rating'] == 5)}")
        report.append(f"- 四星股票: {sum(1 for stock in star_rated_stocks if stock['star_rating'] == 4)}")
        report.append(f"- 三星及以下股票: {sum(1 for stock in star_rated_stocks if stock['star_rating'] <= 3)}")
        report.append("")
        
        # 按打星评级排序显示
        star_rated_stocks.sort(key=lambda x: (x["star_rating"], x["emotion_score"]), reverse=True)
        
        for stock in star_rated_stocks:
            code = stock["code"]
            name = stock["name"]
            star_rating = stock["star_rating"]
            result = results.get(code, {})
            
            report.append(f"## {name} ({code}) - {'★' * star_rating}{'☆' * (5 - star_rating)}")
            report.append(f"- 情绪分: {result.get('emotion_score', 0):.1f}")
            report.append(f"- 趋势预测: {result.get('trend_prediction', '未知')}")
            report.append(f"- 操作建议: {result.get('operation_suggestion', '未知')}")
            report.append(f"- 置信度: {result.get('confidence', '未知')}")
            
            if result.get('analysis_summary', ''):
                report.append(f"- 分析摘要: {result.get('analysis_summary')}")
            
            if result.get('news_summary', ''):
                report.append(f"- 新闻摘要: {result.get('news_summary')}")
            
            if result.get('policy_impact', ''):
                report.append(f"- 政策影响: {result.get('policy_impact')}")
            
            if result.get('risk_tips', ''):
                report.append(f"- 风险提示: {result.get('risk_tips')}")
            
            if result.get('operation_reason', ''):
                report.append(f"- 操作理由: {result.get('operation_reason')}")
            
            report.append("")
        
        return "\n".join(report)
    
    def export_results(self, analysis_result: Dict[str, Any], format: str = "csv") -> str:
        """导出分析结果"""
        if not analysis_result.get("success", False):
            return "分析失败，无法导出结果"
        
        results = analysis_result.get("results", {})
        
        # 准备导出数据
        export_data = []
        for code, result in results.items():
            export_data.append({
                "股票代码": code,
                "股票名称": result.get("name", f"股票{code}"),
                "情绪分": result.get("emotion_score", 0),
                "打星评级": result.get("star_rating", 0),
                "趋势预测": result.get("trend_prediction", "未知"),
                "操作建议": result.get("operation_suggestion", "未知"),
                "置信度": result.get("confidence", "未知"),
                "分析摘要": result.get("analysis_summary", ""),
                "新闻摘要": result.get("news_summary", ""),
                "政策影响": result.get("policy_impact", ""),
                "风险提示": result.get("risk_tips", ""),
                "操作理由": result.get("operation_reason", ""),
                "使用模型": result.get("used_model", ""),
                "分析成功": result.get("success", False),
                "错误信息": result.get("error_message", "")
            })
        
        df = pd.DataFrame(export_data)
        
        if format == "csv":
            output_file = "stock_list_analysis_result.csv"
            df.to_csv(output_file, index=False, encoding="utf-8-sig")
        elif format == "json":
            output_file = "stock_list_analysis_result.json"
            df.to_json(output_file, orient="records", force_ascii=False, indent=2)
        else:
            return f"不支持的导出格式: {format}"
        
        return f"分析结果已导出到: {output_file}"