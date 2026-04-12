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


def _llm_configured(cfg: dict) -> bool:
    """是否配置了任一 LLM Key（环境变量或 config 扁平/嵌套）。"""
    if os.environ.get("DEEPSEEK_API_KEY", "").strip() or os.environ.get(
        "GEMINI_API_KEY", ""
    ).strip():
        return True
    la = cfg.get("plugins", {}).get("llm_analysis") or {}
    if isinstance(la, dict):
        if str(la.get("api_key", "")).strip():
            return True
        nested = la.get("llm") or {}
        if isinstance(nested, dict) and str(nested.get("api_key", "")).strip():
            return True
    return False


def _get_feature_status(cfg: dict) -> str:
    """获取功能模块状态"""
    lines = ["【功能状态】"]
    
    if _llm_configured(cfg):
        lines.append("✅ LLM分析: 已配置")
    else:
        lines.append("⚠️ LLM分析: 未配置（基础分析模式，需 DEEPSEEK_API_KEY 或 GEMINI_API_KEY）")
    
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
                ls = r["llm_stars"]
                if ls is not None and ls <= 0:
                    content_lines.append("LLM评级: 无星（综合分低于内部门槛）")
                else:
                    content_lines.append(f"LLM评级: {ls}星")

            if 'llm_operation_advice' in r:
                content_lines.append(f"建议: {r['llm_operation_advice']}")

            def _one_line(key: str, label: str, limit: int = 160) -> None:
                v = r.get(key)
                if not v or not str(v).strip():
                    return
                s = str(v).replace("\n", " ").strip()
                if len(s) > limit:
                    s = s[: limit - 1] + "…"
                content_lines.append(f"{label}: {s}")

            _one_line("llm_technical_detail", "技术", 180)
            _one_line("llm_fundamental_detail", "基本面", 180)
            _one_line("llm_news_detail", "消息面", 160)

            if 'llm_news_success' in r:
                if r['llm_news_success']:
                    content_lines.append("📰 新闻源: 已抓取")
                    if r.get('llm_news_summary'):
                        ns = str(r['llm_news_summary']).replace("\n", " ").strip()
                        lim = 220 if r.get('llm_stars') == 5 else 140
                        if len(ns) > lim:
                            ns = ns[: lim - 1] + "…"
                        content_lines.append(f"   摘要: {ns}")
                else:
                    content_lines.append("📰 新闻源: 未获取")

            if r.get('llm_star_reason'):
                reason = str(r['llm_star_reason']).strip()
                lim = 900 if r.get('llm_stars') == 5 else 480
                if len(reason) > lim:
                    reason = reason[: lim - 1] + "…"
                content_lines.append(f"打星理由: {reason}")

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
