# -*- coding: utf-8 -*-
"""
滚动股票池 HTML 页面生成器

生成自包含的静态 HTML 页面，展示 10 日滚动股票池。
无外部依赖（CSS/JS 全部内联）。
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("stock_selector.pool_html")


def generate_pool_html(pool_data: List[Dict]) -> str:
    """
    生成自包含的静态 HTML 页面。

    Args:
        pool_data: get_pool_top_n() 的返回值

    Returns:
        HTML 字符串
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    json_str = json.dumps(pool_data, ensure_ascii=False, default=str)

    html = _HTML_TEMPLATE.replace("__UPDATE_TIME__", now).replace("__JSON_DATA__", json_str)
    return html


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>选股狙击 - 滚动股票池</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
    background: #f5f5f5; color: #333; padding: 20px;
  }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  .subtitle { color: #666; font-size: 0.85em; margin-bottom: 16px; }
  .summary { background: #fff; border-radius: 8px; padding: 12px 16px;
             margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .summary span { margin-right: 20px; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  th { background: #f0f0f0; padding: 10px 8px; text-align: left; font-size: 0.85em;
       cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { background: #e5e5e5; }
  th::after { content: " \25B4\25BE"; font-size: 0.7em; color: #aaa; }
  th.sort-asc::after { content: " \25B4"; color: #333; }
  th.sort-desc::after { content: " \25BE"; color: #333; }
  td { padding: 8px; border-top: 1px solid #eee; font-size: 0.9em; }
  tr:hover { background: #fafafa; }
  .signal-buyable { color: #22c55e; font-weight: bold; }
  .signal-watch { color: #eab308; font-weight: bold; }
  .signal-avoid { color: #ef4444; font-weight: bold; }
  .footer { text-align: center; color: #999; font-size: 0.8em; margin-top: 20px; }
  @media (max-width: 600px) {
    body { padding: 8px; }
    td, th { padding: 6px 4px; font-size: 0.8em; }
    .hide-mobile { display: none; }
  }
</style>
</head>
<body>
<h1>📊 选股狙击 · 滚动股票池</h1>
<p class="subtitle">10日滚动窗口，每日自动更新</p>
<div class="summary" id="summary"></div>
<table id="pool-table">
<thead><tr>
  <th data-sort="rank" class="sort-desc">#</th>
  <th data-sort="signal">信号</th>
  <th data-sort="name">名称</th>
  <th data-sort="code">代码</th>
  <th data-sort="price" class="hide-mobile">价格</th>
  <th data-sort="amount">成交额(亿)</th>
  <th data-sort="gain" class="hide-mobile">涨幅%</th>
  <th data-sort="sector" class="hide-mobile">板块</th>
  <th>理由</th>
</tr></thead>
<tbody id="pool-body"></tbody>
</table>
<p class="footer">数据来源: stock-selector strategy · 更新时间: __UPDATE_TIME__</p>
<script>
var stockPoolData = __JSON_DATA__;

(function() {
  function render(items) {
    var tbody = document.getElementById('pool-body');
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var s = items[i];
      var cls = '';
      if (s.signal === '可介入') cls = 'signal-buyable';
      else if (s.signal === '观望') cls = 'signal-watch';
      else if (s.signal === '回避') cls = 'signal-avoid';
      html += '<tr>' +
        '<td>' + (i + 1) + '</td>' +
        '<td class="' + cls + '">' + (s.signal || '—') + '</td>' +
        '<td>' + (s.name || '') + '</td>' +
        '<td>' + (s.code || '') + '</td>' +
        '<td class="hide-mobile">' + (s.price || 0) + '</td>' +
        '<td>' + (s.amount_yi || 0) + '</td>' +
        '<td class="hide-mobile">' + (s.gain_pct || 0) + '</td>' +
        '<td class="hide-mobile">' + (s.sector || '') + '</td>' +
        '<td style="font-size:0.85em;color:#666;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (s.signal_reason || '') + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
    var buyable = items.filter(function(x) { return x.signal === '可介入'; }).length;
    var watch = items.filter(function(x) { return x.signal === '观望'; }).length;
    var avoid = items.filter(function(x) { return x.signal === '回避'; }).length;
    document.getElementById('summary').innerHTML =
      '<span>📈 总数: <b>' + items.length + '</b> 只</span>' +
      '<span>🟢 可介入: <b>' + buyable + '</b></span>' +
      '<span>🟡 观望: <b>' + watch + '</b></span>' +
      '<span>🔴 回避: <b>' + avoid + '</b></span>';
  }

  render(stockPoolData);

  var ths = document.querySelectorAll('th[data-sort]');
  for (var t = 0; t < ths.length; t++) {
    (function(th) {
      th.addEventListener('click', function() {
        var key = th.getAttribute('data-sort');
        var asc = th.classList.contains('sort-desc');
        for (var x = 0; x < ths.length; x++) {
          ths[x].classList.remove('sort-asc', 'sort-desc');
        }
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');
        var sorted = stockPoolData.slice().sort(function(a, b) {
          var va = a[key], vb = b[key];
          if (key === 'rank') { va = stockPoolData.indexOf(a); vb = stockPoolData.indexOf(b); }
          if (typeof va === 'string') return asc ? (vb || '').localeCompare(va || '') : (va || '').localeCompare(vb || '');
          return asc ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
        });
        render(sorted);
      });
    })(ths[t]);
  }
})();
</script>
</body>
</html>"""
