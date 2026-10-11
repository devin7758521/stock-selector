#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US pre-market scanner for the Magnificent Seven plus Coca-Cola."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
import pandas_market_calendars as mcal
import requests

NY = ZoneInfo("America/New_York")
TICKERS = {
    "AAPL": "苹果",
    "MSFT": "微软",
    "NVDA": "英伟达",
    "AMZN": "亚马逊",
    "META": "Meta",
    "GOOGL": "谷歌",
    "TSLA": "特斯拉",
    "KO": "可口可乐",
}


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    value = 100 - (100 / (1 + rs))
    return float(value.iloc[-1]) if len(value) and pd.notna(value.iloc[-1]) else float("nan")


def fmt(value, digits=2, suffix=""):
    return f"{value:.{digits}f}{suffix}" if pd.notna(value) else "暂无"


def analyze(ticker: str, name: str, today):
    tk = yf.Ticker(ticker)
    daily = tk.history(period="6mo", interval="1d", auto_adjust=True, actions=False)
    if daily is None or daily.empty or len(daily) < 30:
        raise RuntimeError(f"{ticker}: 日线数据不足")

    close = daily["Close"].dropna()
    volume = daily["Volume"].dropna()
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    rsi_value = rsi(close)
    last_close = float(close.iloc[-1])

    intraday = tk.history(period="1d", interval="5m", prepost=True, auto_adjust=True)
    premarket_price = float("nan")
    premarket_time = None
    premarket_volume = 0
    if intraday is not None and not intraday.empty:
        idx = pd.to_datetime(intraday.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        local_idx = idx.tz_convert(NY)
        today_mask = [stamp.date() == today for stamp in local_idx]
        before_open_mask = [stamp.time() < datetime.strptime("09:30", "%H:%M").time() for stamp in local_idx]
        rows = intraday.loc[[a and b for a, b in zip(today_mask, before_open_mask)]]
        if not rows.empty:
            premarket_price = float(rows["Close"].dropna().iloc[-1])
            premarket_volume = int(rows["Volume"].fillna(0).sum())
            premarket_time = local_idx[[a and b for a, b in zip(today_mask, before_open_mask)]][-1].strftime("%H:%M ET")

    gap = ((premarket_price / last_close) - 1) * 100 if pd.notna(premarket_price) and last_close else float("nan")
    trend = "多头排列" if ema9.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1] else (
        "空头排列" if ema9.iloc[-1] < ema20.iloc[-1] < ema50.iloc[-1] else "均线交错"
    )
    macd_trend = "MACD柱正值" if hist.iloc[-1] > 0 else "MACD柱负值"
    if pd.notna(gap) and gap >= 1.0:
        gap_signal = "盘前明显高开"
    elif pd.notna(gap) and gap <= -1.0:
        gap_signal = "盘前明显低开"
    elif pd.notna(gap):
        gap_signal = "盘前波动较小"
    else:
        gap_signal = "盘前价格暂不可用"

    if pd.notna(rsi_value) and rsi_value >= 70:
        rsi_note = "偏热"
    elif pd.notna(rsi_value) and rsi_value <= 30:
        rsi_note = "偏弱/超卖区"
    else:
        rsi_note = "中性区"

    return {
        "ticker": ticker, "name": name, "close": last_close,
        "premarket": premarket_price, "gap": gap, "premarket_time": premarket_time,
        "rsi": rsi_value, "trend": trend, "macd": macd_trend,
        "rsi_note": rsi_note, "gap_signal": gap_signal,
        "ema9": float(ema9.iloc[-1]), "ema20": float(ema20.iloc[-1]),
        "ema50": float(ema50.iloc[-1]), "macd_hist": float(hist.iloc[-1]),
        "premarket_volume": premarket_volume,
        "avg_volume20": float(volume.tail(20).mean()) if len(volume) >= 20 else float("nan"),
    }


def render(results, now):
    lines = [
        f"📊 美股盘前扫描｜{now.strftime('%Y-%m-%d %H:%M ET')}",
        "范围：七朵金花 + 可口可乐（KO）",
        "说明：盘前价格可能延迟或缺失；技术指标基于最近日线收盘数据。",
        "",
    ]
    ranked = sorted(results, key=lambda x: (pd.notna(x["gap"]), x["gap"] if pd.notna(x["gap"]) else -999), reverse=True)
    for r in ranked:
        gap_text = fmt(r["gap"], 2, "%")
        pre_text = fmt(r["premarket"])
        rsi_text = fmt(r["rsi"], 1)
        lines.append(
            f"{r['ticker']} {r['name']}｜盘前 {pre_text}｜前收 {fmt(r['close'])}｜跳空 {gap_text}\n"
            f"  {r['gap_signal']}；RSI14 {rsi_text}（{r['rsi_note']}）；{r['trend']}；{r['macd']}"
        )
    lines += [
        "",
        "阅读提示：这是一份盘前观察清单，不是自动买卖指令。开盘后价格、成交量和消息都可能改变信号。",
    ]
    return "\n".join(lines)


def main():
    now = datetime.now(NY)
    today = now.date()
    calendar = mcal.get_calendar("NYSE")
    if calendar.schedule(start_date=today, end_date=today).empty:
        print(f"NYSE 今日休市（{today}），跳过扫描。")
        return 0

    results, errors = [], []
    for ticker, name in TICKERS.items():
        try:
            result = analyze(ticker, name, today)
            results.append(result)
            print(f"OK {ticker}: close={result['close']:.2f}, premarket={result['premarket']}")
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
            print(f"ERROR {ticker}: {exc}", file=sys.stderr)

    if not results:
        raise RuntimeError("8 只股票均未能取得有效数据，扫描失败。")

    report = render(results, now)
    if errors:
        report += "\n\n⚠️ 数据获取失败：\n" + "\n".join(errors)

    print("\n" + report)
    webhook = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if webhook:
        response = requests.post(
            webhook,
            json={"msg_type": "text", "content": {"text": report}},
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code", 0) not in (0, None) or body.get("StatusCode", 0) not in (0, None):
            raise RuntimeError(f"飞书 webhook 返回异常：{body}")
        print("Feishu notification sent.")
    else:
        print("FEISHU_WEBHOOK_URL 未配置，报告仅保留在 Actions 日志中。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
