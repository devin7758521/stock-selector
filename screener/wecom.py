"""
wecom.py
========
企业微信机器人推送，发送 text 格式消息。
webhook_url 从 config 或环境变量 WECOM_WEBHOOK_URL 读取。
"""

import os
import logging
from typing import List, Dict
from datetime import datetime

import requests

logger = logging.getLogger("stock_selector.wecom")


def _get_feature_status(cfg: dict) -> str:
    """获取功能模块状态"""
    lines = ["【功能状态】"]
    
    llm_api_key = os.environ.get("DEEPSEEK_API_KEY", "") or cfg.get("plugins", {}).get("llm_analysis", {}).get("llm", {}).get("api_key", "")
    if llm_api_key:
        lines.append("✅ LLM分析: 已配置")
    else:
        lines.append("⚠️ LLM分析: 未配置（基础分析模式）")
    
    lines.append("📰 新闻搜索: 东方财富/新浪财经/同花顺/雪球（免费源）")
    
    return "\n".join(lines)


def send_wecom_start(cfg: dict) -> bool:
    """
    发送启动通知
    
    Args:
        cfg: 完整 config dict
        
    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("wecom", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.debug("未配置企业微信 webhook_url，跳过启动推送")
        return False
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    feature_status = _get_feature_status(cfg)
    
    content = f"""🚀 stock selector 选股系统启动

启动时间: {now}
系统状态: 开始选股...

{feature_status}

请稍候，选股完成后将推送结果。"""
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") == 0:
            logger.info("企业微信启动通知推送成功")
            return True
        else:
            logger.error(f"企业微信启动通知推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"企业微信启动通知推送异常: {e}")
        return False


def send_wecom(results: List[Dict], cfg: dict) -> bool:
    """
    发送选股结果通知
    
    Args:
        results: 选股结果列表
        cfg: 完整 config dict
        
    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("wecom", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.warning("未配置企业微信 webhook_url，跳过推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")
    feature_status = _get_feature_status(cfg)

    if not results:
        content = f"📊 选股播报 {today}\n\n今日无符合条件的标的。\n\n{feature_status}"
    else:
        top_results = results[:10]
        content_lines = [f"📊 选股播报 {today}", f"共 {len(results)} 只\n", feature_status, ""]
        
        for r in top_results:
            stock_line = f"{r['name']}（{r['code']}）"
            content_lines.append(stock_line)
            
            if 'price' in r:
                content_lines.append(f"价格: {r['price']}")
            
            if 'vol_deviation_pct' in r:
                content_lines.append(f"偏离: {r['vol_deviation_pct']}%")
            
            if 'ai_buy_signal' in r:
                content_lines.append(f"AI信号: {r['ai_buy_signal']}")
            
            if 'llm_stars' in r:
                content_lines.append(f"LLM评级: {r['llm_stars']}星")

            if 'llm_operation_advice' in r:
                content_lines.append(f"建议: {r['llm_operation_advice']}")

            if 'llm_news_success' in r:
                if r['llm_news_success']:
                    content_lines.append("📰 新闻: 已获取")
                    if 'llm_news_summary' in r and r['llm_news_summary']:
                        summary = r['llm_news_summary'][:100]
                        if len(r['llm_news_summary']) > 100:
                            summary += "..."
                        content_lines.append(f"   {summary}")
                else:
                    content_lines.append("📰 新闻: 未获取到")

            if 'llm_star_reason' in r:
                reason = r['llm_star_reason']
                if '；' in reason:
                    parts = reason.split('；')
                    clean_parts = []
                    for p in parts:
                        if '加权总分' in p or '×50%' in p or '×30%' in p or '×20%' in p:
                            continue
                        if p.strip():
                            clean_parts.append(p.strip())
                    if clean_parts:
                        reason = '；'.join(clean_parts)
                    else:
                        reason = ''
                if reason:
                    content_lines.append(f"理由: {reason}")

            content_lines.append("")
        
        content = "\n".join(content_lines)
        
    payload = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") == 0:
            logger.info(f"企业微信推送成功，共 {len(results)} 只标的")
            return True
        else:
            logger.error(f"企业微信推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"企业微信推送异常: {e}")
        return False
