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
from screener.sector import filter_sector_weekly
from screener.feishu import send_feishu, send_feishu_card, send_feishu_start
from .plugin import PluginManager

logger = logging.getLogger("stock_selector.selector")

# 全市场 LLM 五星最多保留数量（与 AI 插件五星上限一致）
_MAX_LLM_FIVE_STAR = 2


def _apply_llm_five_star_cap(results: List[Dict], max_five: int = _MAX_LLM_FIVE_STAR) -> None:
    """按当前列表顺序保留前 max_five 只五星，其余降为四星并改写理由前缀。"""
    if not results:
        return
    kept = 0
    for r in results:
        if r.get("llm_stars") == 5:
            kept += 1
            if kept > max_five:
                r["llm_stars"] = 4
                prev = (r.get("llm_star_reason") or "").strip()
                r["llm_star_reason"] = (
                    f"【五星限{max_five}只】按当日排序仅前{max_five}只保留五星，本票降为四星。"
                    f"原评判：{prev}"
                )


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
        plugins_cfg = self.config.get("plugins", {})
        for plugin_name, plugin_config in plugins_cfg.items():
            if plugin_config.get("enabled", False):
                try:
                    self.plugin_manager.load_plugin(plugin_name, plugin_config)
                    logger.info(f"加载插件: {plugin_name}")
                except Exception as e:
                    logger.warning(f"加载插件 {plugin_name} 失败: {e}")

    def _load_or_filter_sectors(self):
        """优先读取 sector_results.json，否则实时筛选板块"""
        import json
        import os
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sector_results.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sectors = data.get("sectors", [])
                if sectors:
                    from datetime import datetime
                    saved_date = data.get("date", "")[:10]
                    today = datetime.now().strftime("%Y-%m-%d")
                    if saved_date == today:
                        logger.info(f"从 sector_results.json 加载 {len(sectors)} 个板块（{saved_date}）")
                        return sectors
                    else:
                        logger.info(f"sector_results.json 日期{saved_date}非今日，重新筛选")
            except Exception as e:
                logger.debug(f"读取 sector_results.json 失败: {e}")

        logger.info("实时筛选板块...")
        return filter_sector_weekly(self.config)
    
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
                    logger.info(f"插件 {plugin.name} 处理 {code} 成功，返回字段: {list(plugin_result.keys())}")
                else:
                    logger.warning(f"插件 {plugin.name} 处理 {code} 返回空")
            except Exception as e:
                logger.warning(f"插件 {plugin.name} 处理 {code} 失败: {e}")
        
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
        send_feishu_start(self.config)
        
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
        
        # Step 3.5: 板块周K筛选
        logger.info("Step 3.5: 板块周K筛选...")
        self.sector_results = self._load_or_filter_sectors()
        if self.sector_results:
            sector_names = [s["name"] for s in self.sector_results[:10]]
            logger.info(f"强势板块: {', '.join(sector_names)}")
            llm_plugin = self.plugin_manager.get_plugin('llm_analysis')
            if llm_plugin:
                llm_plugin.sector_results = self.sector_results
                if hasattr(llm_plugin, 'analyzer') and llm_plugin.analyzer:
                    llm_plugin.analyzer.sector_results = self.sector_results
                    logger.info(f"已将{len(self.sector_results)}个强势板块传递给LLM分析器")
        else:
            logger.warning("板块筛选无结果，后续板块联动权重为0")
        
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
            key=lambda x: (x.get("llm_stars", 0), x.get("llm_weighted_score", x.get("weighted_score", 0))),
            reverse=True,
        )

        _apply_llm_five_star_cap(sorted_results, _MAX_LLM_FIVE_STAR)
        sorted_results = sorted(
            sorted_results,
            key=lambda x: (x.get("llm_stars", 0), x.get("llm_weighted_score", x.get("weighted_score", 0))),
            reverse=True,
        )

        # Step 5.5: LLM综合推理（对所有股票）
        logger.info("Step 5.5: LLM综合推理...")
        llm_plugin = self.plugin_manager.get_plugin('llm_analysis')
        if llm_plugin and hasattr(llm_plugin, 'rank_stocks'):
            try:
                ranked_results = llm_plugin.rank_stocks(sorted_results, top_n=10)
                logger.info(f"LLM综合推理完成，共 {len(ranked_results)} 只")
            except Exception as e:
                logger.warning(f"LLM综合推理失败: {e}")
                ranked_results = sorted_results
        else:
            logger.warning("LLM插件不支持推理筛选")
            ranked_results = sorted_results

        # Step 6: 飞书推送
        logger.info("Step 6: 推送飞书...")
        sector_res = getattr(self, 'sector_results', None)
        send_feishu(ranked_results, self.config, sector_results=sector_res)

        return ranked_results
