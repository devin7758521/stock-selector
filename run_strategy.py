# -*- coding: utf-8 -*-
"""
A股选股策略独立入口（Top-Down 龙头策略）

用法:
    python run_strategy.py
    python run_strategy.py --config config.yaml

执行流程:
    1. 大盘环境分析 → 评分 + 仓位建议
    2. 主线板块识别 → Top3 板块（涨停数+成交额+涨幅综合评分）
    3. 板块内龙头选股 → 每个板块2-3只龙头
    4. 买卖信号 + 仓位参考
    5. 结果写入 strategy_results.json
    6. 飞书推送

与 run_etf.py / run_sector.py 并发运行，互不依赖。
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
from screener.market_env import analyze_market_env
from screener.sector_leader import identify_leading_sectors, pick_leader_stocks
from screener.feishu_strategy import send_feishu_strategy

logger = logging.getLogger("stock_selector.run_strategy")

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "strategy_results.json")


def _to_json_safe(obj):
    """递归转换 numpy 类型为 Python 原生类型，确保 JSON 可序列化"""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    try:
        import numpy as np
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except ImportError:
        pass
    return obj


def run(config_path: str = "config.yaml") -> dict:
    cfg = load_config(config_path)

    logger.info("=" * 55)
    logger.info("  A股选股策略（Top-Down龙头策略）启动")
    logger.info("=" * 55)

    # ═══════════════════════════════════════════════════
    # Step 1: 大盘环境分析
    # ═══════════════════════════════════════════════════
    logger.info("Step 1/5: 大盘环境分析...")
    env = analyze_market_env(days=120)
    logger.info(f"  大盘评分: {env['score']}/100, 情绪: {env['sentiment']}, 建议仓位: {env['position_pct']}%")
    logger.info(f"  判断: {env['market_breadth']}")

    # ═══════════════════════════════════════════════════
    # Step 2: 主线板块识别
    # ═══════════════════════════════════════════════════
    logger.info("Step 2/5: 主线板块识别...")
    leading_sectors = identify_leading_sectors(top_n=3)

    # ═══════════════════════════════════════════════════
    # Step 3: 板块内龙头选股
    # ═══════════════════════════════════════════════════
    logger.info("Step 3/5: 板块内龙头选股...")
    all_picks = []
    for sector in leading_sectors:
        sector_name = sector["name"]
        sector_code = sector.get("code", "")
        if not sector_code:
            logger.warning(f"  {sector_name}: 无板块代码，跳过")
            continue

        leaders = pick_leader_stocks(sector_name, sector_code, top_n=3)
        sector["leader_stocks"] = leaders
        all_picks.extend(leaders)

    logger.info(f"  共选出 {len(all_picks)} 只龙头股（{len(leading_sectors)} 个板块）")

    # ═══════════════════════════════════════════════════
    # Step 4: 仓位建议
    # ═══════════════════════════════════════════════════
    logger.info("Step 4/5: 仓位建议...")
    base_position = env["position_pct"]

    # 微调：如果无符合条件的龙头，降低仓位
    buyable = [s for s in all_picks if s.get("signal") == "可介入"]
    if not buyable:
        base_position = min(base_position, 10)
        logger.info("  无「可介入」标的，仓位降至10%观望")

    position_advice = {
        "total_pct": base_position,
        "per_stock_pct": min(20, base_position // max(len(buyable), 1)),
        "buyable_count": len(buyable),
        "note": (
            "龙头明确，可积极配置"
            if base_position >= 40
            else "轻仓试探，等待确认"
            if base_position >= 15
            else "市场偏弱，观望为主"
        ),
    }
    logger.info(f"  总仓位{base_position}%，单票{position_advice['per_stock_pct']}%，可介入{len(buyable)}只")

    # ═══════════════════════════════════════════════════
    # Step 5: 写入结果 + 飞书推送
    # ═══════════════════════════════════════════════════
    logger.info("Step 5/5: 写入结果 + 飞书推送...")

    result = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_env": env,
        "leading_sectors": leading_sectors,
        "position_advice": position_advice,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(result), f, ensure_ascii=False, indent=2)
    logger.info(f"  策略结果已写入 {RESULTS_FILE}")

    # 飞书推送
    try:
        send_feishu_strategy(env, leading_sectors, position_advice, cfg)
    except Exception as e:
        logger.warning(f"飞书推送异常: {e}")

    logger.info("=" * 55)
    logger.info(f"  策略执行完成: 大盘{env['sentiment']} | {len(leading_sectors)}主线板块 | {len(all_picks)}只龙头")
    logger.info("=" * 55)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A股选股策略 Top-Down龙头策略")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    run(config_path=args.config)
