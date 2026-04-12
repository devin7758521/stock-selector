"""
screener - stock selector 选股核心模块

模块结构：
  calendar.py    - A股真实交易日历，日K→周K聚合
  datasources.py - 多数据源轮换（8个数据源，多线程安全分级）
  filter.py      - 两步筛选（静态过滤 + 指标计算）
  wecom.py       - 企业微信推送
  utils.py       - 配置加载、限速、退避重试

对外接口（供 main.py 及未来 AI 分析模块调用）：
  from screener.datasources import fetch_stock_list, fetch_daily_kline, fetch_spot_data
  from screener.filter import static_filter, calc_indicators
  from screener.calendar import resample_weekly_by_calendar, get_trade_dates
  from screener.wecom import send_wecom
  from screener.utils import load_config
"""

