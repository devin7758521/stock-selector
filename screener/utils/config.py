import os
import yaml
from pathlib import Path

def load_config(path: str = "config.yaml") -> dict:
    """
    加载 config.yaml，同时用环境变量覆盖（GitHub Actions Secrets 注入方式）。
    环境变量优先级高于 yaml 文件。
    """
    cfg_path = Path(path)
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # 确保必要 key 存在
    cfg.setdefault("datasources", {})
    cfg.setdefault("screener", {})
    cfg.setdefault("request", {})
    cfg.setdefault("wecom", {})
    cfg.setdefault("feishu", {})
    cfg.setdefault("plugins", {
        "llm_analysis": {"enabled": True},
        "ai_analysis": {"enabled": True},
        "stock_list_analysis": {"enabled": True},
        "technical_analysis": {"enabled": True},
        "fundamental_analysis": {"enabled": True},
    })

    # 环境变量覆盖（适配 GitHub Actions Secrets）
    env_map = {
        "TUSHARE_TOKEN":       ("datasources", "tushare_token"),
        "JQ_USERNAME":         ("datasources", "joinquant_username"),
        "JQ_PASSWORD":         ("datasources", "joinquant_password"),
        "MAIRUI_TOKEN":        ("datasources", "mairui_token"),
        "WECOM_WEBHOOK_URL":   ("wecom", "webhook_url"),
        "FEISHU_WEBHOOK_URL":   ("feishu", "webhook_url"),
    }
    for env_key, (section, field) in env_map.items():
        val = os.environ.get(env_key, "").strip()
        if val:
            cfg[section][field] = val

    return cfg
