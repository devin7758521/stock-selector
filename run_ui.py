# -*- coding: utf-8 -*-
"""
JusticePlutus UI 主入口

启动PyQt6桌面应用
"""

import sys
import argparse
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from ui.controller import StockScreenerController


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="JusticePlutus A股选股系统")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("JusticePlutus")
    app.setApplicationVersion("1.0.0")
    
    # 设置高DPI支持
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
    # 加载样式表
    style_path = Path(__file__).parent / "ui" / "styles" / "dark_theme.qss"
    if not style_path.exists():
        # 尝试相对路径
        style_path = Path("ui/styles/dark_theme.qss")
    
    if style_path.exists():
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    else:
        print(f"警告: 样式表文件不存在: {style_path}")
    
    # 创建MVC组件
    view = MainWindow()
    controller = StockScreenerController(args.config)
    
    # 连接View和Controller
    controller.connect_view(view)
    
    # 显示窗口
    view.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
