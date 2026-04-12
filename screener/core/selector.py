# -*- coding: utf-8 -*-
"""
核心选股器
"""

import logging
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from screener.utils import load_config
from screener.datasources import fetch_stock_list, fetch_daily_kline, fetch_spot_data
from screener.filter import static_filter, calc_indicators, print_stats
from screener.wecom import send_wecom, send_wecom_start
from .plugin import PluginManager

logger = logging.getLogger("stock_selector.selector")


class StockSelector:
    """
    股票选股器
    
    封装完整的选股流程，支持插件扩展
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化选股器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        self.plugin_manager = PluginManager()
        self._initialize_plugins()
    
    def _initialize_plugins(self):
        """
        初始化插件
        """
        # 从配置中加载插件
        plugin_config = self.config.get("plugins", {})
        for plugin_name, plugin_config in plugin_config.items():
            if plugin_config.get("enabled", False):
                try:
                    self.plugin_manager.load_plugin(plugin_name, plugin_config)
                    logger.info(f"加载插件: {plugin_name}")
                except Exception as e:
                    logger.warning(f"加载插件 {plugin_name} 失败: {e}")
    
    def process_stock(self, code: str, name: str) -> Optional[Dict]:
        """
        处理单只股票
        
        Args:
            code: 股票代码
            name: 股票名称
            
        Returns:
            股票分析结果
        """
        df = fetch_daily_kline(code, self.config)
        if df is None:
            return None
        
        indicators = calc_indicators(df, self.config)
        if indicators is None:
            return None
        
        result = {"code": code, "name": name, **indicators}
        
        # 应用插件
        for plugin in self.plugin_manager.get_active_plugins():
            try:
                plugin_result = plugin.process(result, df, self.config)
                if plugin_result:
                    result.update(plugin_result)
            except Exception as e:
                logger.debug(f"插件 {plugin.name} 处理 {code} 失败: {e}")
        
        return result
    
    def run(self) -> List[Dict]:
        """
        执行选股流程
        
        Returns:
            选股结果列表
        """
        req_cfg = self.config.get("request", {})
        max_workers = req_cfg.get("max_workers", 3)
        
        logger.info("=" * 55)
        logger.info("  stock selector 选股启动")
        logger.info("=" * 55)
        
        # Step 0: 发送启动通知
        logger.info("Step 0: 发送启动通知...")
        send_wecom_start(self.config)
        
        # Step 1: 获取股票列表
        logger.info("Step 1: 获取全量股票列表...")
        stock_df = fetch_stock_list(self.config)
        if stock_df is None or stock_df.empty:
            logger.error("获取股票列表失败，程序退出")
            return []
        
        # Step 2: 获取实时行情快照（用于预筛价格+成交额）
        logger.info("Step 2: 获取实时行情快照...")
        spot_df = fetch_spot_data(self.config)
        
        # Step 3: 静态过滤
        logger.info("Step 3: 静态规则过滤...")
        filtered_df = static_filter(stock_df, self.config, spot_df=spot_df)
        stock_list = list(zip(filtered_df["code"], filtered_df["name"]))
        logger.info(f"待下载行情的股票: {len(stock_list)} 只")
        
        # Step 4: 并发下载 + 指标筛选
        logger.info(f"Step 4: 并发处理（线程数={max_workers}）...")
        results: List[Dict] = []
        failed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self.process_stock, code, name): (code, name)
                for code, name in stock_list
            }
            for future in tqdm(
                as_completed(future_map),
                total=len(future_map),
                desc="选股进度",
                ncols=80,
            ):
                code, name = future_map[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"  ✓ 入选: {name}（{code}）")
                except Exception as e:
                    failed += 1
                    logger.debug(f"  ✗ {code} 处理异常: {e}")
        
        # 输出漏斗统计（帮助诊断每步过滤了多少）
        print_stats()
        
        # 限制五星股票最多两个
        five_star_count = 0
        for stock in results:
            if stock.get('ai_star_rating', 0) == 5:
                if five_star_count < 2:
                    five_star_count += 1
                else:
                    # 超过两个五星，降级为四星
                    stock['ai_star_rating'] = 4
                    stock['ai_star_display'] = "⭐" * 4
                    # 更新评级理由
                    if 'ai_rating_reason' in stock:
                        stock['ai_rating_reason'] = stock['ai_rating_reason'] + "；由于五星股票数量限制，降级为四星"
        
        # 输出结果
        logger.info("=" * 55)
        logger.info(f"筛选完成: 入选 {len(results)} 只 / 跳过失败 {failed} 只")
        logger.info("=" * 55)
        
        if results:
            for r in results:
                # 构建输出信息
                output_parts = [
                    f"  {r['name']}（{r['code']}）",
                    f"  价格={r['price']}",
                    f"  偏离={r['vol_deviation_pct']}%",
                    f"  日成交额={r['daily_amount_yi']}亿"
                ]
                
                # 添加插件输出
                for plugin in self.plugin_manager.get_active_plugins():
                    try:
                        plugin_output = plugin.format_output(r)
                        if plugin_output:
                            output_parts.append(f"  {plugin_output}")
                    except Exception as e:
                        logger.debug(f"插件 {plugin.name} 格式化输出失败: {e}")
                
                logger.info("".join(output_parts))
                
                # 输出LLM详细分析报告
                llm_plugin = self.plugin_manager.get_plugin('llm_analysis')
                if llm_plugin and hasattr(llm_plugin, 'format_detailed_output'):
                    try:
                        detailed_output = llm_plugin.format_detailed_output(r)
                        logger.info("\n" + detailed_output)
                    except Exception as e:
                        logger.debug(f"LLM详细输出失败: {e}")
        
        # Step 5: 按照 LLM 评星和加权分排序
        logger.info("Step 5: 按照 LLM 评星和加权分排序...")
        sorted_results = sorted(
            results, 
            key=lambda x: (x.get('llm_stars', 0), x.get('weighted_score', 0)), 
            reverse=True
        )
        
        # Step 6: 企业微信推送
        logger.info("Step 6: 推送企业微信...")
        send_wecom(sorted_results, self.config)
        
        return results
