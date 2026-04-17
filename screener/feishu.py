"""
feishu.py
=========
飞书机器人推送，支持 text 消息和 interactive 卡片消息。
webhook_url 从 config 或环境变量 FEISHU_WEBHOOK_URL 读取。
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

import requests

logger = logging.getLogger("stock_selector.feishu")


def _llm_configured(cfg: dict) -> bool:
    """是否配置了任一 LLM Key"""
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


def _akshare_news_status() -> str:
    """检查 AkShare 新闻状态"""
    try:
        import akshare as ak
        return "✅ AkShare新闻: 已配置"
    except ImportError:
        return "⚠️ AkShare新闻: 未安装（pip install akshare）"
    except Exception:
        return "⚠️ AkShare新闻: 获取状态失败"


def _tavily_status() -> str:
    """检查 Tavily 状态"""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if key:
        return "✅ Tavily宏观: 已配置"
    return "⚠️ Tavily宏观: 未配置（TAVILY_API_KEY）"


def _get_feature_status(cfg: dict) -> str:
    """获取功能模块状态"""
    lines = ["【功能状态】"]

    if _llm_configured(cfg):
        model = cfg.get("plugins", {}).get("llm_analysis", {}).get("model") or \
                cfg.get("plugins", {}).get("llm_analysis", {}).get("llm", {}).get("model") or \
                os.environ.get("LLM_MODEL", "deepseek")
        lines.append(f"✅ LLM分析: 已配置（{model}）")
    else:
        lines.append("⚠️ LLM分析: 未配置（基础分析模式）")

    lines.append(_akshare_news_status())
    lines.append(_tavily_status())

    return "\n".join(lines)


def send_feishu_start(cfg: dict) -> bool:
    """
    发送启动通知

    Args:
        cfg: 完整 config dict

    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.debug("未配置飞书 webhook_url，跳过启动推送")
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    feature_status = _get_feature_status(cfg)

    content = f"""🚀 stock selector 选股系统启动

启动时间: {now}
系统状态: 开始选股...

{feature_status}

请稍候，选股完成后将推送结果。"""

    payload = {
        "msg_type": "text",
        "content": {"text": content}
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            logger.info("飞书启动通知推送成功")
            return True
        else:
            logger.error(f"飞书启动通知推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"飞书启动通知推送异常: {e}")
        return False


def send_feishu_sector(sectors: List[Dict], cfg: dict) -> bool:
    """
    发送板块筛选结果通知

    Args:
        sectors: 板块筛选结果列表
        cfg: 完整 config dict

    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.warning("未配置飞书 webhook_url，跳过推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")

    content_lines = [
        f"📊 板块播报 {today}",
        ""
    ]

    if not sectors:
        content_lines.append("今日无符合条件的强势板块。")
    else:
        content_lines.append(f"🔥 强势板块（{len(sectors)}个通过周K筛选）")
        for i, s in enumerate(sectors[:15], 1):
            trend = s.get("sector_trend", "")
            dev = s.get("vol_deviation_pct", 0)
            amt = s.get("daily_amount_yi", 0)
            trend_emoji = "📈" if "上行" in trend else "📊" if "整理" in trend else "📉"
            content_lines.append(f"  {i}. {trend_emoji} {s['name']}｜{trend}｜偏离{dev}%｜{amt}亿")

    message = "\n".join(content_lines)
    payload = {"msg_type": "text", "content": {"text": message}}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"[feishu] 板块播报推送成功，共 {len(sectors)} 个板块")
            return True
        else:
            logger.warning(f"[feishu] 推送失败: {resp.status_code}")
    except Exception as e:
        logger.warning(f"[feishu] 推送异常: {e}")
    return False


def send_feishu_etf(etfs: List[Dict], cfg: dict) -> bool:
    """
    发送ETF筛选结果通知

    Args:
        etfs: ETF筛选结果列表
        cfg: 完整 config dict

    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.warning("未配置飞书 webhook_url，跳过推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")

    content_lines = [
        f"📊 ETF播报 {today}",
        ""
    ]

    if not etfs:
        content_lines.append("今日无符合条件的强势ETF。")
    else:
        content_lines.append(f"🔥 强势ETF（{len(etfs)}只通过周K筛选）")
        for i, e in enumerate(etfs[:15], 1):
            trend = e.get("etf_trend", "")
            dev = e.get("vol_deviation_pct", 0)
            amt = e.get("daily_amount_yi", 0)
            idx_name = e.get("index_name", "")
            trend_icon = "📈" if "上行" in trend else "📊" if "整理" in trend else "📉"
            content_lines.append(f"  {i}. {trend_icon} {e['name']}({e['code']})｜{idx_name}｜{trend}｜偏离{dev}%｜{amt}亿")

    message = "\n".join(content_lines)
    payload = {"msg_type": "text", "content": {"text": message}}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"[feishu] ETF播报推送成功，共 {len(etfs)} 只ETF")
            return True
        else:
            logger.warning(f"[feishu] 推送失败: {resp.status_code}")
    except Exception as e:
        logger.warning(f"[feishu] 推送异常: {e}")
    return False


def send_feishu(results: List[Dict], cfg: dict, sector_results: Optional[List[Dict]] = None) -> bool:
    """
    发送选股结果通知（板块+Top10合并为一条消息）

    Args:
        results: 选股结果列表
        cfg: 完整 config dict
        sector_results: 板块筛选结果（可选）

    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.warning("未配置飞书 webhook_url，跳过推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")
    feature_status = _get_feature_status(cfg)

    content_lines = [
        f"📊 选股播报 {today}",
        ""
    ]

    if sector_results:
        content_lines.append(f"🔥 强势板块（{len(sector_results)}个通过周K筛选）")
        for i, s in enumerate(sector_results[:15], 1):
            trend = s.get("sector_trend", "")
            dev = s.get("vol_deviation_pct", 0)
            amt = s.get("daily_amount_yi", 0)
            trend_emoji = "📈" if "上行" in trend else "📊" if "整理" in trend else "📉"
            content_lines.append(f"  {i}.{trend_emoji}{s['name']}｜{trend}｜偏离{dev}%｜{amt}亿")
        content_lines.append("")
        content_lines.append("─" * 30)
        content_lines.append("")

    if not results:
        content_lines.append("今日无符合条件的个股标的。")
        content_lines.append("")
        content_lines.append(feature_status)
        content = "\n".join(content_lines)
        payload = {
            "msg_type": "text",
            "content": {"text": content}
        }
    else:
        top_results = results[:10]
        content_lines.append(f"⭐ Top {len(top_results)} 个股（共{len(results)}只入选）")
        content_lines.append("")
        content_lines.append(feature_status)
        content_lines.append("")

        for i, r in enumerate(top_results, 1):
            stock_line = f"{i}. ▶ {r['name']}（{r['code']}）"
            content_lines.append(stock_line)

            if 'price' in r:
                content_lines.append(f"  价格: {r['price']}")

            if 'vol_deviation_pct' in r:
                content_lines.append(f"  偏离: {r['vol_deviation_pct']}%")

            if 'ai_buy_signal' in r:
                content_lines.append(f"  AI信号: {r['ai_buy_signal']}")

            if 'llm_stars' in r:
                ls = r["llm_stars"]
                if ls is not None and ls <= 0:
                    content_lines.append("  LLM评级: 无星")
                else:
                    stars_str = "⭐" * ls if ls else ""
                    content_lines.append(f"  LLM评级: {ls}星 {stars_str}")

            if 'llm_operation_advice' in r:
                content_lines.append(f"  建议: {r['llm_operation_advice']}")

            def _one_line(key: str, label: str, limit: int = 200) -> None:
                v = r.get(key)
                if not v or not str(v).strip():
                    return
                s = str(v).replace("\n", " ").strip()
                if len(s) > limit:
                    s = s[: limit - 1] + "…"
                content_lines.append(f"  {label}: {s}")

            _one_line("llm_technical_detail", "技术", 200)
            _one_line("llm_news_detail", "消息面", 180)

            if 'llm_news_success' in r:
                if r['llm_news_success']:
                    content_lines.append("  📰 新闻: 已获取")
                    if r.get('llm_news_summary'):
                        ns = str(r['llm_news_summary']).replace("\n", " ").strip()
                        lim = 280 if r.get('llm_stars') == 5 else 180
                        if len(ns) > lim:
                            ns = ns[: lim - 1] + "…"
                        content_lines.append(f"     摘要: {ns}")
                else:
                    content_lines.append("  📰 新闻: 未获取（请配置 AKNEWS_API_KEY 或检查网络）")

            if r.get('llm_star_reason'):
                reason = str(r['llm_star_reason']).strip()
                lim = 1200 if r.get('llm_stars') == 5 else 600
                if len(reason) > lim:
                    reason = reason[: lim - 1] + "…"
                content_lines.append(f"  打星理由: {reason}")

            content_lines.append("")

        content = "\n".join(content_lines)

        payload = {
            "msg_type": "text",
            "content": {"text": content}
        }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            logger.info(f"飞书推送成功，共 {len(results)} 只标的")
            return True
        else:
            logger.error(f"飞书推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
        return False


def send_feishu_card(results: List[Dict], cfg: dict, sector_results: Optional[List[Dict]] = None) -> bool:
    """
    发送飞书卡片消息（富文本格式），板块+Top10合并推送

    Args:
        results: 选股结果列表
        cfg: 完整 config dict
        sector_results: 板块筛选结果（可选）

    Returns:
        是否推送成功
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "").strip()
    if not webhook_url:
        logger.warning("未配置飞书 webhook_url，跳过卡片推送")
        return False

    today = datetime.today().strftime("%Y-%m-%d")

    all_elements = []

    header = {
        "title": {"tag": "plain_text", "content": f"📊 选股播报 {today}"},
        "template": "purple"
    }
    all_elements.append({"tag": "card", "card": {"header": header}})

    feature_status_text = _get_feature_status(cfg).replace("\n", "\n\n")
    all_elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": feature_status_text
        }
    })
    all_elements.append({"tag": "hr"})

    if sector_results:
        sector_tag = {
            "tag": "el_tag",
            "text": f"🔥 强势板块 {len(sector_results)}个",
            "color": "yellow"
        }
        all_elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔥 强势板块（{len(sector_results)}个通过周K筛选）**"
            }
        })

        sector_items = []
        for s in sector_results[:15]:
            trend = s.get("sector_trend", "")
            dev = s.get("vol_deviation_pct", 0)
            amt = s.get("daily_amount_yi", 0)
            trend_icon = "📈" if "上行" in trend else "📊" if "整理" in trend else "📉"
            sector_items.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{trend_icon} **{s['name']}**｜{trend}｜偏离{dev}%｜{amt}亿"
                }
            })

        if sector_items:
            all_elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": ""},
                "elements": sector_items
            })
        all_elements.append({"tag": "hr"})

    if not results:
        all_elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "**⭐ 今日无符合条件的个股标的。**"
            }
        })
    else:
        top_results = results[:10]
        all_elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**⭐ Top {len(top_results)} 个股（共{len(results)}只入选）**"
            }
        })

        for i, r in enumerate(top_results, 1):
            stars = r.get('llm_stars', 0)
            stars_str = "⭐" * stars if stars else ""

            name_tag_color = "red" if stars == 5 else "orange" if stars == 4 else "blue" if stars == 3 else "grey"

            stock_lines = [
                f"**{i}. ▶ {r['name']}（{r['code']}）**"
            ]

            if 'price' in r:
                stock_lines.append(f"价格: **{r['price']}**")
            if 'vol_deviation_pct' in r:
                stock_lines.append(f"偏离: **{r['vol_deviation_pct']}%**")
            if 'ai_buy_signal' in r:
                stock_lines.append(f"AI信号: {r['ai_buy_signal']}")
            if stars:
                stock_lines.append(f"LLM评级: **{stars}星** {stars_str}")
            if 'llm_operation_advice' in r:
                advice = r['llm_operation_advice']
                advice_icon = "🟢" if "买入" in advice or "增持" in advice else "🔴" if "卖出" in advice or "减持" in advice else "🟡"
                stock_lines.append(f"建议: {advice_icon} **{advice}**")

            tech = r.get('llm_technical_detail', '')
            if tech:
                tech_brief = tech.replace("\n", " ").strip()[:150]
                stock_lines.append(f"`技术`: {tech_brief}")

            news_d = r.get('llm_news_detail', '')
            if news_d:
                news_brief = news_d.replace("\n", " ").strip()[:150]
                stock_lines.append(f"`消息面`: {news_brief}")

            if r.get('llm_news_success') and r.get('llm_news_summary'):
                ns = str(r['llm_news_summary']).replace("\n", " ").strip()
                lim = 280 if stars == 5 else 180
                if len(ns) > lim:
                    ns = ns[:lim - 1] + "…"
                stock_lines.append(f"`📰摘要`: {ns}")
            elif r.get('llm_news_success') == False:
                stock_lines.append("`📰`: 未获取")

            reason = r.get('llm_star_reason', '')
            if reason:
                reason_brief = reason.replace("\n", " ").strip()
                lim = 800 if stars == 5 else 400
                if len(reason_brief) > lim:
                    reason_brief = reason_brief[:lim - 1] + "…"
                stock_lines.append(f"`打星理由`: {reason_brief}")

            content_text = "\n".join(stock_lines)

            star_tag = None
            if stars == 5:
                star_tag = {"tag": "el_tag", "text": "⭐五星", "color": "red"}
            elif stars == 4:
                star_tag = {"tag": "el_tag", "text": "四星", "color": "orange"}
            elif stars == 3:
                star_tag = {"tag": "el_tag", "text": "三星", "color": "blue"}

            title_parts = [f"**{i}. ▶ {r['name']}（{r['code']}）**"]
            if star_tag:
                title_parts.append(star_tag)

            stock_div = {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content_text
                }
            }

            all_elements.append(stock_div)

            if i < len(top_results):
                all_elements.append({"tag": "hr"})

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 选股播报 {today}  共{len(results)}只"},
                "template": "purple"
            },
            "elements": all_elements
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            logger.info(f"飞书卡片推送成功，共 {len(results)} 只标的")
            return True
        else:
            logger.error(f"飞书卡片推送失败: {data}")
            return False
    except Exception as e:
        logger.error(f"飞书卡片推送异常: {e}")
        return False
