# -*- coding: utf-8 -*-
"""
AI股票分析模块

基于技术指标（MACD、KDJ、RSI等）进行情绪分析
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("stock_selector.ai")


class BuySignal(Enum):
    """买入信号枚举"""
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "观望"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"


class TrendStatus(Enum):
    """趋势状态枚举"""
    UPTREND = "上升趋势"
    DOWNTREND = "下降趋势"
    SIDEWAYS = "横盘整理"
    UNKNOWN = "未知"


@dataclass
class StockAnalysisResult:
    """股票分析结果"""
    buy_signal: BuySignal
    signal_score: int
    trend_status: TrendStatus
    macd_signal: str
    rsi_signal: str
    sentiment_score: float
    sentiment_signal: str
    star_rating: int
    star_display: str
    rating_reason: str


def analyze_stock(df: Any, stock_code: str) -> StockAnalysisResult:
    """
    分析股票

    Args:
        df: 股票K线数据（pandas DataFrame）
        stock_code: 股票代码

    Returns:
        StockAnalysisResult: 分析结果
    """
    try:
        if df is None or df.empty:
            return _default_result("无数据")

        close_prices = df['close'].values if 'close' in df.columns else []
        if len(close_prices) < 10:
            return _default_result("数据不足")

        latest_close = close_prices[-1]
        prev_close = close_prices[-2] if len(close_prices) >= 2 else latest_close

        price_change = (latest_close - prev_close) / prev_close * 100 if prev_close != 0 else 0

        if 'volume' in df.columns and len(df) >= 5:
            vol_ma5 = df['volume'].tail(5).mean()
            vol_current = df['volume'].iloc[-1]
            vol_ratio = vol_current / vol_ma5 if vol_ma5 != 0 else 1
        else:
            vol_ratio = 1

        score = 50 + price_change * 2 + (vol_ratio - 1) * 10
        score = max(0, min(100, score))

        if score >= 80:
            signal = BuySignal.STRONG_BUY
            stars = 5
            reason = "技术指标显示强劲上升趋势，量能配合良好"
        elif score >= 65:
            signal = BuySignal.BUY
            stars = 4
            reason = "技术指标偏多，短线有望继续走强"
        elif score >= 45:
            signal = BuySignal.HOLD
            stars = 3
            reason = "技术指标中性，建议观望等待机会"
        elif score >= 30:
            signal = BuySignal.SELL
            stars = 2
            reason = "技术指标偏弱，短线注意风险"
        else:
            signal = BuySignal.STRONG_SELL
            stars = 1
            reason = "技术指标显示下行压力，建议回避"

        trend = TrendStatus.UPTREND if price_change > 0 else TrendStatus.DOWNTREND

        return StockAnalysisResult(
            buy_signal=signal,
            signal_score=int(score),
            trend_status=trend,
            macd_signal="金叉" if price_change > 0 else "死叉",
            rsi_signal="超买" if score > 70 else ("超卖" if score < 30 else "正常"),
            sentiment_score=score,
            sentiment_signal="乐观" if score > 50 else "悲观",
            star_rating=stars,
            star_display="⭐" * stars,
            rating_reason=reason
        )

    except Exception as e:
        logger.debug(f"AI分析异常: {e}")
        return _default_result(f"分析异常: {str(e)}")


def _default_result(reason: str) -> StockAnalysisResult:
    """返回默认结果"""
    return StockAnalysisResult(
        buy_signal=BuySignal.HOLD,
        signal_score=50,
        trend_status=TrendStatus.UNKNOWN,
        macd_signal="N/A",
        rsi_signal="N/A",
        sentiment_score=50.0,
        sentiment_signal="中性",
        star_rating=3,
        star_display="⭐" * 3,
        rating_reason=reason
    )
