# 东方财富、同花顺、长桥配置示例

## 功能说明

本配置文件用于设置东方财富、同花顺、长桥相关参数，包括：
- 各平台API配置
- 自选股和持仓股分析设置
- Cookie管理

## 配置示例

```yaml
# 东方财富配置
eastmoney:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: "your_cookie_here"  # 不推荐直接在配置文件中存储
  
  # 分析设置
  analysis:
    watchlist: true  # 是否分析自选股
    portfolio: true   # 是否分析持仓股
    export_format: "csv"  # 导出格式: csv 或 json
    generate_report: true  # 是否生成分析报告
    max_stocks: 50  # 最大分析股票数量

# 同花顺配置
tenjqka:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: "your_cookie_here"  # 不推荐直接在配置文件中存储

# 长桥配置
longbridge:
  # Cookie 配置（推荐通过环境变量设置）
  # cookie: "your_cookie_here"  # 不推荐直接在配置文件中存储

# 插件配置
plugins:
  stock_list_analysis:
    enabled: true  # 启用股票列表分析插件
    broker_integration: true  # 启用券商集成
```

## Cookie获取方法

### 东方财富
1. 登录东方财富网站 (https://www.eastmoney.com/)
2. 打开浏览器开发者工具（F12）
3. 切换到 "Network" 标签
4. 刷新页面，找到一个请求
5. 在 "Headers" 中找到 "Cookie" 字段
6. 复制整个Cookie值

### 同花顺
1. 登录同花顺网站 (https://www.10jqka.com.cn/)
2. 打开浏览器开发者工具（F12）
3. 切换到 "Network" 标签
4. 刷新页面，找到一个请求
5. 在 "Headers" 中找到 "Cookie" 字段
6. 复制整个Cookie值

### 长桥
1. 登录长桥网站 (https://www.longbridgeapp.com/)
2. 打开浏览器开发者工具（F12）
3. 切换到 "Network" 标签
4. 刷新页面，找到一个请求
5. 在 "Headers" 中找到 "Cookie" 字段
6. 复制整个Cookie值

## 安全使用建议

1. **环境变量设置**（推荐）：
   ```bash
   # Windows
   set EASTMONEY_COOKIE=your_eastmoney_cookie_here
   set TENJQKA_COOKIE=your_tenjqka_cookie_here
   set LONGBRIDGE_COOKIE=your_longbridge_cookie_here
   
   # Linux/Mac
   export EASTMONEY_COOKIE=your_eastmoney_cookie_here
   export TENJQKA_COOKIE=your_tenjqka_cookie_here
   export LONGBRIDGE_COOKIE=your_longbridge_cookie_here
   ```

2. **GitHub Actions**：
   - 在仓库设置 → Secrets and variables → Actions
   - 添加 EASTMONEY_COOKIE、TENJQKA_COOKIE、LONGBRIDGE_COOKIE 密钥

3. **本地文件**（不推荐）：
   - 创建 .env 文件
   - 添加相关Cookie
   - 将 .env 文件添加到 .gitignore

## 使用示例

```bash
# 分析券商自选股和持仓股
python analyze_eastmoney.py

# 或者通过环境变量设置Cookie
set EASTMONEY_COOKIE=your_cookie_here && python analyze_eastmoney.py
```

## 注意事项

1. **Cookie有效期**：各平台Cookie通常有一定有效期，过期后需要重新获取
2. **安全保护**：不要将Cookie上传到公开仓库
3. **请求频率**：不要频繁请求，避免账号被限制
4. **错误处理**：如果获取失败，会自动降级为手动输入股票代码
5. **平台差异**：不同平台的API接口可能会有变化，需要定期更新

## 故障排除

- **Cookie无效**：重新获取对应平台的Cookie
- **获取失败**：检查网络连接，确保已登录对应平台
- **分析失败**：检查股票代码是否正确，数据源是否可用
- **API变化**：如果接口失效，需要更新对应平台的API实现
