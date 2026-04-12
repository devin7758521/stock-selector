# 企业微信推送配置说明

## 功能说明

JusticePlutus 选股系统支持企业微信机器人推送，可以在以下时机发送通知：

1. **启动通知**：系统启动时发送
2. **结果通知**：选股完成后发送结果

## 配置步骤

### 1. 创建企业微信机器人

1. 在企业微信群聊中，点击右上角 `...` -> `群机器人` -> `添加机器人`
2. 设置机器人名称，例如：`JusticePlutus选股助手`
3. 复制生成的 Webhook 地址

### 2. 配置 Webhook URL

在 `config.yaml` 中添加配置：

```yaml
wecom:
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
```

或者通过环境变量设置：

```bash
export WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"
```

### 3. 推送消息格式

#### 启动通知

```
🚀 JusticePlutus 选股系统启动

启动时间: 2026-04-12 09:00:00
系统状态: 开始选股...

请稍候，选股完成后将推送结果。
```

#### 结果通知

```
📊 选股播报 2026-04-12，共 10 只

昊华科技（600378）
凯盛科技（600552）
骆驼股份（601311）
...
```

## 测试推送

配置完成后，运行测试脚本验证推送功能：

```bash
python test_single_stock.py
```

查看日志输出，确认推送状态：
- `企业微信启动通知推送成功` - 启动通知推送成功
- `企业微信推送成功，共 X 只标的` - 结果通知推送成功
- `未配置企业微信 webhook_url，跳过推送` - 未配置webhook，跳过推送

## 注意事项

1. **Webhook URL 安全**：不要将包含真实 webhook_url 的配置文件上传到公开仓库
2. **推送频率**：企业微信机器人有频率限制，建议合理使用
3. **消息格式**：当前使用 text 格式，简洁明了
4. **错误处理**：推送失败不影响选股流程，系统会继续执行

## 高级配置

### 自定义推送内容

如需自定义推送内容，可以修改 `screener/wecom.py` 中的消息格式：

```python
# 启动通知
content = f"""🚀 JusticePlutus 选股系统启动

启动时间: {now}
系统状态: 开始选股...

请稍候，选股完成后将推送结果。"""

# 结果通知
lines = [f"📊 选股播报 {today}，共 {len(results)} 只\n"]
for r in results:
    lines.append(f"{r['name']}（{r['code']}）")
```

### 添加更多推送渠道

如需添加其他推送渠道（如钉钉、飞书等），可以参考 `wecom.py` 的实现方式。
