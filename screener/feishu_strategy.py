# -*- coding: utf-8 -*-
"""
策略飞书推送模块（独立于 feishu.py，不修改现有文件）

推送 Top-Down 龙头策略的分析结果：
  大盘环境 → 主线板块 → 龙头股推荐 → 仓位建议
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("stock_selector.feishu_strategy")


def _get_webhook(cfg: dict) -> str:
    return (cfg.get("feishu", {}) or {}).get("webhook_url", "").strip()


def _post_text(webhook: str, content: str) -> bool:
    """发送 text 消息到飞书"""
    try:
        resp = requests.post(
            webhook,
            json={"msg_type": "text", "content": {"text": content}},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            return True
        logger.warning(f"飞书推送失败: {data}")
    except Exception as e:
        logger.warning(f"飞书推送异常: {e}")
    return False


def send_feishu_strategy(
    env: Dict,
    leading_sectors: List[Dict],
    position_advice: Dict,
    cfg: dict,
    pool: Optional[List[Dict]] = None,
) -> bool:
    """
    发送策略分析结果到飞书

    Args:
        env: market_env.analyze_market_env() 的输出
        leading_sectors: identify_leading_sectors() 的输出
        position_advice: 仓位建议 dict
        cfg: 完整 config
        pool: 滚动股票池（10日窗口 top15）

    Returns:
        是否推送成功
    """
    webhook = _get_webhook(cfg)
    if not webhook:
        logger.debug("未配置飞书 webhook_url，跳过策略推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")

    lines = [
        f"🎯 A股选股策略（龙头战法）{today}",
        "",
    ]

    # ── 一、大盘环境 ────────────────────────────
    score = env["score"]
    sentiment = env["sentiment"]
    emoji = "🟢" if sentiment == "乐观" else "🟡" if sentiment in ("中性", "谨慎") else "🔴"
    lines.append(f"{'─' * 32}")
    lines.append(f"一、大盘环境  {emoji} {sentiment}（{score}/100）")
    lines.append(f"{'─' * 32}")
    lines.append(f"  {env['summary']}")
    lines.append(f"  市场宽度: {env['market_breadth']}")

    indices = env.get("indices", {})
    for name, info in indices.items():
        if info.get("error"):
            lines.append(f"  {name}: {info['error']}")
            continue
        close = info.get("close", 0)
        gain = info.get("daily_gain_pct", 0)
        sign = "+" if gain >= 0 else ""
        ma5_str = "✅" if info.get("above_ma25") else "❌"
        ma10_str = "✅" if info.get("above_ma60") else "❌"
        vol_str = info.get("vol_trend", "—")
        lines.append(
            f"  {name}: {close} ({sign}{gain}%) "
            f"| MA25{ma5_str} MA60{ma10_str} | 量能:{vol_str}"
        )

    if env.get("warning"):
        lines.append(f"  ⚠️ {env['warning']}")
    lines.append("")

    # ── 二、主线板块 ────────────────────────────
    lines.append(f"{'─' * 32}")
    lines.append(f"二、主线板块 Top{len(leading_sectors)}")
    lines.append(f"{'─' * 32}")

    for s in leading_sectors:
        rank = s["rank"]
        zt = s.get("limit_up_count", 0)
        score_s = s.get("score", 0)
        gain = s.get("gain_pct", 0)
        amt = s.get("amount_yi", 0)
        sign = "+" if gain >= 0 else ""
        lines.append(
            f"  {rank}. {s['name']}  "
            f"评分{score_s} | {zt}只涨停 | {sign}{gain}% | 成交{amt}亿"
        )

        # 龙头股
        leaders = s.get("leader_stocks", [])
        if leaders:
            for ls in leaders:
                signal = ls.get("signal", "—")
                sig_emoji = "🟢" if signal == "可介入" else "🟡" if signal == "观望" else "🔴"
                price = ls.get("price", 0)
                gain_ls = ls.get("gain_pct", 0)
                sign_ls = "+" if gain_ls >= 0 else ""
                lines.append(
                    f"      {sig_emoji} {ls['name']}({ls['code']}) "
                    f"¥{price} ({sign_ls}{gain_ls}%) 成交{ls.get('amount_yi',0)}亿"
                )
                lines.append(f"         {ls.get('signal_reason', '')}")
        else:
            lines.append("      （无符合条件的龙头股）")
        lines.append("")
    lines.append("")

    # ── 2.5、滚动股票池 ────────────────────────────
    if pool:
        lines.append(f"{'─' * 32}")
        lines.append(f"2.5、滚动股票池 Top{len(pool)}（10日窗口）")
        lines.append(f"{'─' * 32}")
        for i, p in enumerate(pool, 1):
            signal = p.get("signal", "—")
            sig_emoji = "🟢" if signal == "可介入" else "🟡" if signal == "观望" else "🔴"
            lines.append(
                f"  {i}. {sig_emoji} {p['name']}({p['code']}) "
                f"¥{p.get('price', 0)} ({p.get('amount_yi', 0)}亿) {signal}"
            )
        lines.append("")

    # ── 三、仓位建议 ────────────────────────────
    lines.append(f"{'─' * 32}")
    lines.append(f"三、仓位建议")
    lines.append(f"{'─' * 32}")
    lines.append(f"  总仓位: {position_advice['total_pct']}%")
    lines.append(f"  单票上限: {position_advice['per_stock_pct']}%")
    lines.append(f"  可介入标的: {position_advice['buyable_count']}只")
    lines.append(f"  策略: {position_advice['note']}")
    lines.append("")

    # ── 四、关键规则提醒 ────────────────────────────
    lines.append(f"{'─' * 32}")
    lines.append(f"四、操作纪律")
    lines.append(f"{'─' * 32}")
    lines.append("  🛑 止损: 跌破关键位3-5%即走")
    lines.append("  ✅ 止盈: 冲高量能跟不上减仓 | 题材退潮先跑")
    lines.append("  📊 复盘: 今天最强板块是谁？龙头为什么强？")
    lines.append("  💡 核心: 板块强 + 个股强 + 量能配合 + 回调不破位 = 值得关注")
    lines.append("")

    message = "\n".join(lines)
    ok = _post_text(webhook, message)
    if ok:
        logger.info("策略飞书推送成功")
    return ok
