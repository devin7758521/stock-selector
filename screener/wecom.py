"""
wecom.py
========
企业微信机器人推送，发送 text 格式消息。
webhook_url 从 config 或环境变量 WECOM_WEBHOOK_URL 读取。
"""

import logging
from typing import List, Dict
from datetime import datetime

import requests

logger = logging.getLogger("stock_selector.wecom")


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
    
    content = f"""🚀 stock selector 选股系统启动

启动时间: {now}
系统状态: 开始选股...

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

    if not results:
        content = f"📊 选股播报 {today}\n\n今日无符合条件的标的。"
    else:
        # 只推送前10只股票
        top_results = results[:10]
        lines = [f"📊 选股播报 {today}", f"共 {len(results)} 只\n"]
        for r in top_results:
            # 基础信息
            stock_line = f"{r['name']}（{r['code']}）"
            lines.append(stock_line)
            
            # 添加价格
            if 'price' in r:
                lines.append(f"价格: {r['price']}")
            
            # 添加偏离
            if 'vol_deviation_pct' in r:
                lines.append(f"偏离: {r['vol_deviation_pct']}%")
            
            # 添加AI信号
            if 'ai_buy_signal' in r:
                lines.append(f"AI信号: {r['ai_buy_signal']}")
            
            # 添加LLM评级
            if 'llm_stars' in r:
                stars = r['llm_stars']
                lines.append(f"LLM评级: {stars}星")

            # 添加建议
            if 'llm_operation_advice' in r:
                lines.append(f"建议: {r['llm_operation_advice']}")

            # 添加理由（提取核心分析结论）
            if 'llm_star_reason' in r:
                reason = r['llm_star_reason']
                # 去掉评分计算部分，保留核心结论
                # 格式：二星评级，谨慎参与；加权总分50.2分（LLM:50.5×50% + AI:50×30% + 技术:...）；...
                if '；' in reason:
                    parts = reason.split('；')
                    clean_parts = []
                    for p in parts:
                        # 跳过评分计算部分
                        if '加权总分' in p or '×50%' in p or '×30%' in p or '×20%' in p:
                            continue
                        if p.strip():
                            clean_parts.append(p.strip())
                    if clean_parts:
                        reason = '；'.join(clean_parts)
                    else:
                        reason = ''
                if reason:
                    lines.append(f"理由: {reason}")

            # 空行分隔
            lines.append("")
        
        content = "\n".join(lines)

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
