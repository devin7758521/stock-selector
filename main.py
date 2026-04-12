"""
main.py
=======
stock selector 选股主入口

运行方式：
    python main.py
    python main.py --config config.yaml

GitHub Actions 中：
    - 将 token 设置在 Secrets（TUSHARE_TOKEN / JQ_USERNAME 等）
    - 将企业微信 webhook 设置在 Secrets（WECOM_WEBHOOK_URL）
    - 直接 python main.py 即可

Copyright (c) 2026 stock selector. All rights reserved.
"""

import argparse
import logging

# 设置日志级别为DEBUG，以便查看详细的成交额信息
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from screener.core import StockSelector

logger = logging.getLogger("stock_selector.main")


def run(config_path: str = "config.yaml"):
    """
    运行选股
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        选股结果
    """
    selector = StockSelector(config_path)
    return selector.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="stock selector 选股")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()
    run(config_path=args.config)

