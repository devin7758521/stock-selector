#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python approximation of Adaptive RSI + Volume Profile + MTF MACD + MACD Leader V2."""
from __future__ import annotations
import os, sys, math
from datetime import datetime, time
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_market_calendars as mcal
import requests

NY=ZoneInfo("America/New_York")
TICKERS={"AAPL":"苹果","MSFT":"微软","NVDA":"英伟达","AMZN":"亚马逊","META":"Meta","GOOGL":"谷歌","TSLA":"特斯拉","KO":"可口可乐"}

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def adaptive_rsi(c,n=14,sigma=3.0):
    a=c.to_numpy(float); out=np.full(len(a),np.nan)
    w=[math.exp(-((i-n/2)**2)/(2*sigma**2)) for i in range(1,n+1)]
    for k in range(n,len(a)):
        g=l=0.0
        for i,wi in enumerate(w,1):
            d=a[k-i+1]-a[k-i]; g+=max(d,0)*wi; l+=max(-d,0)*wi
        out[k]=100 if l==0 else 100-100/(1+g/sum(w))
    return pd.Series(out,index=c.index)
def macd(c):
    d=ema(c,12)-ema(c,26); s=ema(d,9); return d,s,d-s
def fmt(x,n=2):
    try: return f"{float(x):.{n}f}" if np.isfinite(float(x)) else "暂无"
    except (TypeError,ValueError): return "暂无"
def resample(df,n):
    return df.resample(f"{n}min",label="left",closed="left").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna(subset=["Close"])

def analyze(ticker,name,today):
    tk=yf.Ticker(ticker)
    daily=tk.history(period="6mo",interval="1d",auto_adjust=False,actions=False)
    bars=tk.history(period="5d",interval="5m",prepost=True,auto_adjust=False,actions=False)
    if daily is None or len(daily)<60: raise RuntimeError("日线历史不足")
    if bars is None or bars.empty: raise RuntimeError("5分钟行情不可用")
    ix=pd.to_datetime(bars.index)
    if ix.tz is None: ix=ix.tz_localize("UTC")
    bars.index=ix.tz_convert(NY); bars=bars.dropna(subset=["Close"])
    sess=bars[bars.index.date==today]; pre=sess[[t<time(9,30) for t in sess.index.time]]
    pp=float(pre.Close.iloc[-1]) if len(pre) else float("nan")
    pc=float(daily.Close.dropna().iloc[-1]); gap=(pp/pc-1)*100 if np.isfinite(pp) and pc else float("nan")
    c=bars.Close; r=adaptive_rsi(c); rma=r.rolling(9).mean(); e9=ema(c,9); e20=ema(c,20)
    hlc=(bars.High+bars.Low+bars.Close)/3
    keys=pd.Series(bars.index.date,index=bars.index)
    vwap=(hlc*bars.Volume).groupby(keys).cumsum()/bars.Volume.groupby(keys).cumsum().replace(0,np.nan)
    prev=c.shift(); tr=pd.concat([bars.High-bars.Low,(bars.High-prev).abs(),(bars.Low-prev).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=.01,min_periods=100,adjust=False).mean()
    bull=(r>20)&(r.shift()<=20); bear=(r<80)&(r.shift()>=80)
    ll=bars.Low.shift().rolling(20).min(); hh=bars.High.shift().rolling(20).max()
    rl=r.shift().rolling(20).min(); rh=r.shift().rolling(20).max()
    bd=bool(bars.Low.iloc[-1]<ll.iloc[-1] and r.iloc[-1]>rl.iloc[-1]) if pd.notna(ll.iloc[-1]) and pd.notna(rl.iloc[-1]) else False
    sd=bool(bars.High.iloc[-1]>hh.iloc[-1] and r.iloc[-1]<rh.iloc[-1]) if pd.notna(hh.iloc[-1]) and pd.notna(rh.iloc[-1]) else False
    mtf={}
    for n in (10,15,30):
        f=resample(bars,n); d,s,h=macd(f.Close); cross="—"
        if len(f)>1 and pd.notna(d.iloc[-2]) and pd.notna(s.iloc[-2]):
            if d.iloc[-1]>s.iloc[-1] and d.iloc[-2]<=s.iloc[-2]: cross="金叉"
            elif d.iloc[-1]<s.iloc[-1] and d.iloc[-2]>=s.iloc[-2]: cross="死叉"
        mtf[n]={"bull":bool(d.iloc[-1]>s.iloc[-1]),"cross":cross,"weak":bool(h.iloc[-1]<h.iloc[-2] and h.iloc[-1]>0) if len(h)>1 else False}
    sema=ema(c,12); lema=ema(c,26); leader=(sema+ema(c-sema,12))-(lema+ema(c-lema,26))
    # 新增提醒层，不改动原有指标公式/参数
    leader_green=((leader>=0)&(leader.shift(1)<0))
    rsi_cross_up=((r>rma)&(r.shift(1)<=rma.shift(1)))
    leader_green_alert=bool(leader_green.reindex(pre.index).fillna(False).any())
    rsi_cross_alert=bool(rsi_cross_up.reindex(pre.index).fillna(False).any())
    vp=bars.tail(200); lo=float(vp.Low.min()); hi=float(vp.High.max()); poc=val=vah=float("nan")
    if hi>lo:
        levels=np.linspace(lo,hi,200); vols=np.zeros(200)
        for row in vp.itertuples(): vols[(levels>=row.Low)&(levels<row.High)]+=float(row.Volume or 0)
        if vols.sum()>0:
            ixp=int(np.argmax(vols)); poc=float(levels[ixp]); left=right=ixp; total=vols[ixp]; target=vols.sum()*.68
            while total<target and (left>0 or right<199):
                up=vols[right+1] if right<199 else -1; dn=vols[left-1] if left>0 else -1
                if up>=dn and right<199: right+=1; total+=vols[right]
                elif left>0: left-=1; total+=vols[left]
                else: break
            val=float(levels[left]); vah=float(levels[right])
    rv=float(r.iloc[-1]) if pd.notna(r.iloc[-1]) else float("nan")
    score=(15 if rv>=80 else 10 if rv>=70 else 5 if rv>=65 else 0)+(25 if sd else 0)
    score+=sum(w for n,w in ((10,5),(15,7),(30,8)) if not mtf[n]["bull"])
    score+=sum(5 for n in (10,15,30) if mtf[n]["weak"])
    score+=sum(w for n,w in ((10,8),(15,10),(30,12)) if mtf[n]["cross"]=="死叉")
    score+=15 if len(bull)>1 and bool(bull.iloc[-2]) else 0
    score+=5 if rv>70 and mtf[15]["weak"] else 0; score=min(score,100)
    risk="极高风险" if score>=70 else "高风险" if score>=50 else "注意" if score>=30 else "低风险"
    # 买入观察排名：优先双提醒、趋势站上均线/VWAP、多周期MACD偏多、风险较低
    trend_ok=bool(c.iloc[-1]>e9.iloc[-1] and c.iloc[-1]>e20.iloc[-1] and c.iloc[-1]>vwap.iloc[-1])
    mtf_bull=sum(1 for n in (10,15,30) if mtf[n]["bull"])
    alert_count=int(leader_green_alert)+int(rsi_cross_alert)
    rank_score=alert_count*25+mtf_bull*8+(10 if trend_ok else 0)+(8 if bd else 0)-score*.6
    if rv>=75: rank_score-=12
    if np.isfinite(gap) and gap>3: rank_score-=8
    if np.isfinite(gap) and gap < -2: rank_score-=8
    buy_watch=bool(alert_count>0 and trend_ok and mtf_bull>=2 and score<50 and 45<=rv<=72)
    return dict(ticker=ticker,name=name,close=pc,pre=pp,gap=gap,rsi=rv,rsi_ma=rma.iloc[-1],ema9=e9.iloc[-1],ema20=e20.iloc[-1],vwap=vwap.iloc[-1],
      bull_div=bd,bear_div=sd,bull_trigger=bool(bull.iloc[-1]),bear_trigger=bool(bear.iloc[-1]),bull_stop=bars.Low.iloc[-1]-atr.iloc[-1]*3,bear_stop=bars.High.iloc[-1]+atr.iloc[-1]*3,
      mtf=mtf,leader=leader.iloc[-1],leader_state="多头" if leader.iloc[-1]>=0 else "空头",leader_momentum="增强" if leader.iloc[-1]>leader.iloc[-2] else "减弱",
      poc=poc,val=val,vah=vah,score=score,risk=risk,leader_green_alert=leader_green_alert,rsi_cross_alert=rsi_cross_alert,alert_count=alert_count,trend_ok=trend_ok,mtf_bull=mtf_bull,rank_score=rank_score,buy_watch=buy_watch)

def render(rs,now,errors):
    eligible=sorted([x for x in rs if x["buy_watch"]],key=lambda x:x["rank_score"],reverse=True)
    out=[f"📌 美股盘前买入观察排名｜{now:%Y-%m-%d %H:%M ET}","扫描：AAPL MSFT NVDA AMZN META GOOGL TSLA KO",""]
    if eligible:
        for i,x in enumerate(eligible[:5],1):
            signals=[]
            if x["leader_green_alert"]: signals.append("MACD红转绿")
            if x["rsi_cross_alert"]: signals.append("RSI蓝线上穿黄线")
            out.append(f"{i}. {x['ticker']} {x['name']}｜观察价 {fmt(x['pre'])}｜盘前涨跌 {fmt(x['gap'])}%")
            out.append(f"   信号：{' + '.join(signals)}｜多周期MACD {x['mtf_bull']}/3｜TOP RISK {x['score']}/100（{x['risk']}）")
            out.append(f"   风控参考：EMA9 {fmt(x['ema9'])}｜EMA20 {fmt(x['ema20'])}｜VWAP {fmt(x['vwap'])}｜ATR止损参考 {fmt(x['bull_stop'])}")
    else:
        out.append("当前没有同时满足提醒、趋势、多周期MACD和风险过滤的标的。今天不强行推荐买入。")
    if errors:
        out.append(f"数据不完整：{len(errors)}只股票获取失败，排名可能不完整。")
    out.append("这是盘前观察名单，不是保证盈利的买入指令；开盘后需确认价格仍站在VWAP/均线之上，跌破趋势条件则放弃。")
    return "\n".join(out)

def main():
    now=datetime.now(NY); today=now.date()
    if mcal.get_calendar("NYSE").schedule(start_date=today,end_date=today).empty:
        print(f"NYSE 今日休市（{today}），跳过扫描。"); return 0
    results=[]; errors=[]
    for ticker,name in TICKERS.items():
        try: results.append(analyze(ticker,name,today))
        except Exception as e: errors.append(f"{ticker}: {e}"); print(f"ERROR {ticker}: {e}",file=sys.stderr)
    if not results: raise RuntimeError("8只股票均未能取得有效数据，扫描失败。")
    report=render(results,now,errors); print("\n"+report)
    webhook=os.getenv("FEISHU_WEBHOOK_URL","").strip()
    if webhook:
        response=requests.post(webhook,json={"msg_type":"text","content":{"text":report}},timeout=20); response.raise_for_status()
        body=response.json()
        if body.get("code",0) not in (0,None) or body.get("StatusCode",0) not in (0,None): raise RuntimeError(f"飞书 webhook 返回异常：{body}")
        print("Feishu notification sent.")
    else: print("FEISHU_WEBHOOK_URL 未配置，报告仅保留在 Actions 日志中。")
    return 0
if __name__=="__main__": raise SystemExit(main())
