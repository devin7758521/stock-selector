# -*- coding: utf-8 -*-
"""
ETF周K筛选独立入口

用法:
    python run_etf.py
    python run_etf.py --config config.yaml

独立运行ETF筛选，结果写入 etf_results.json 供主流程读取。
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
from screener.etf import filter_etf_weekly
from screener.feishu import send_feishu_etf

logger = logging.getLogger("stock_selector.run_etf")

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "etf_results.json")


def run(config_path: str = "config.yaml"):
    cfg = load_config(config_path)
    logger.info("=" * 55)
    logger.info("  ETF周K筛选启动")
    logger.info("=" * 55)
    etfs = filter_etf_weekly(cfg)

    if etfs:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(etfs),
                "etfs": etfs,
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"ETF结果已写入 {RESULTS_FILE}，共 {len(etfs)} 只")
    else:
        logger.warning("ETF筛选无结果")
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": 0,
                "etfs": [],
            }, f, ensure_ascii=False, indent=2)

    send_feishu_etf(etfs, cfg)
    return etfs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETF周K筛选")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    run(config_path=args.config)
