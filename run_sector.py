# -*- coding: utf-8 -*-
"""
板块周K筛选独立入口

用法:
    python run_sector.py
    python run_sector.py --config config.yaml

独立运行板块筛选，结果写入 sector_results.json 供主流程读取。
"""

import argparse
import json
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from screener.utils import load_config
from screener.sector import filter_sector_weekly, fetch_top_sectors_by_gain
from screener.feishu import send_feishu_sector

logger = logging.getLogger("stock_selector.run_sector")

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "sector_results.json")


def run(config_path: str = "config.yaml"):
    cfg = load_config(config_path)
    logger.info("=" * 55)
    logger.info("  板块周K筛选启动")
    logger.info("=" * 55)
    sectors = filter_sector_weekly(cfg)
    top_sectors = fetch_top_sectors_by_gain(top=5)

    if sectors or top_sectors:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(sectors),
                "sectors": sectors,
                "top_sectors": top_sectors,
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"板块结果已写入 {RESULTS_FILE}，周K筛选 {len(sectors)} 个，涨幅前5 {len(top_sectors)} 个")
    else:
        logger.warning("板块筛选无结果")
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": 0,
                "sectors": [],
                "top_sectors": [],
            }, f, ensure_ascii=False, indent=2)

    send_feishu_sector(sectors, cfg)
    return sectors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="板块周K筛选")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    run(config_path=args.config)
