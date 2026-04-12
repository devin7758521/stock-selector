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

logger = logging.getLogger("justice.wecom")


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
    
    content = f"""🚀 JusticePlutus 选股系统启动

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
        lines = [f"📊 选股播报 {today}，共 {len(results)} 只\n"]
        for r in results:
            # 基础信息
            stock_line = f"{r['name']}（{r['code']}）"
            
            # 添加价格、偏离、日成交额
            if 'price' in r:
                stock_line += f"  价格={r['price']}"
            if 'deviation' in r:
                stock_line += f"  偏离={r['deviation']:.2f}%"
            if 'daily_amount_yi' in r:
                stock_line += f"  日成交额={r['daily_amount_yi']}亿"
            
            # 添加技术指标
            if 'tech_indicators' in r:
                tech = r['tech_indicators']
                stock_line += f"  技术指标: MACD={tech.get('MACD', 'N/A')}, KDJ=({tech.get('KDJ', {}).get('K', 'N/A')},{tech.get('KDJ', {}).get('D', 'N/A')},{tech.get('KDJ', {}).get('J', 'N/A')}), RSI={tech.get('RSI', 'N/A'):.1f}"
            
            # 添加 AI 信号和评分
            if 'ai_signal' in r:
                stock_line += f"  AI信号={r['ai_signal']}"
            if 'ai_score' in r:
                stock_line += f"  AI评分={r['ai_score']}"
            if 'ai_rating' in r:
                stock_line += f"  评级={r['ai_rating']}"
            if 'ai_sentiment' in r:
                stock_line += f"  情绪={r['ai_sentiment']}"
            
            # 添加 LLM 评级信息
            if 'llm_stars' in r:
                stars = r['llm_stars']
                stock_line += f"  LLM评级={'★' * stars}{'☆' * (5 - stars)}({stars}星)"
            if 'llm_operation_advice' in r:
                advice = r['llm_operation_advice']
                stock_line += f"  建议={advice}"
            if 'llm_confidence_level' in r:
                confidence = r['llm_confidence_level']
                stock_line += f"  置信度={confidence}"
            
            # 添加加权分和理由
            if 'weighted_score' in r:
                stock_line += f"  加权分={r['weighted_score']:.1f}"
            if 'reason' in r:
                stock_line += f"  理由={r['reason']}"
            
            lines.append(stock_line)
            
            # 添加 LLM 深度分析报告
            if 'llm_analysis_summary' in r:
                lines.append("")
                lines.append("================================================================================")
                lines.append("【LLM深度分析报告】")
                lines.append("================================================================================")
                lines.append("")
                lines.append(f"股票: {r['name']} ({r['code']})")
                lines.append("")
                
                if 'llm_stars' in r:
                    stars = r['llm_stars']
                    lines.append(f"【综合评级】{'★' * stars}{'☆' * (5 - stars)} ({stars}星) - 加权总分: {r.get('weighted_score', 'N/A'):.1f}")
                
                lines.append("")
                lines.append("【推荐理由】")
                if 'llm_analysis_summary' in r:
                    lines.append(r['llm_analysis_summary'])
                
                lines.append("")
                if 'llm_operation_advice' in r:
                    lines.append(f"【操作建议】{r['llm_operation_advice']}（置信度: {r.get('llm_confidence_level', 'N/A')}）")
                if 'llm_trend_prediction' in r:
                    lines.append(f"【趋势预测】{r['llm_trend_prediction']}")
                
                lines.append("")
                lines.append("【风险提示】")
                lines.append("投资有风险，入市需谨慎")
                lines.append("")
                lines.append("================================================================================")
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
