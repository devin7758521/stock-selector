# -*- coding: utf-8 -*-
"""
后台工作线程

遵循PyQt6最佳实践：
- 不在主线程执行耗时操作
- 使用QThread进行后台处理
- 通过signal传递结果
"""

from typing import List, Dict
from PyQt6.QtCore import QThread, pyqtSignal


class ScreeningWorker(QThread):
    """
    选股工作线程
    
    在后台执行选股，避免阻塞UI
    """
    
    # Signals - 向UI发送信号
    progress_updated = pyqtSignal(int, int)  # current, total
    stock_found = pyqtSignal(dict)  # 单只股票结果
    screening_finished = pyqtSignal(list)  # 所有结果
    error_occurred = pyqtSignal(str)  # 错误信息
    
    def __init__(self, selector):
        super().__init__()
        self._selector = selector
        self._is_running = True
    
    def run(self):
        """执行选股"""
        try:
            results = []
            
            # 获取股票列表
            from screener.datasources import fetch_stock_list
            stock_list = fetch_stock_list(self._selector.config)
            
            if not stock_list:
                self.error_occurred.emit("无法获取股票列表")
                return
            
            total = len(stock_list)
            
            # 遍历股票
            for idx, (code, name) in enumerate(stock_list):
                if not self._is_running:
                    break
                
                # 更新进度
                self.progress_updated.emit(idx + 1, total)
                
                # 处理单只股票
                result = self._selector.process_stock(code, name)
                
                if result:
                    results.append(result)
                    # 发送单只股票结果
                    self.stock_found.emit(result)
            
            # 发送所有结果
            self.screening_finished.emit(results)
            
        except Exception as e:
            self.error_occurred.emit(f"选股过程出错: {str(e)}")
    
    def stop(self):
        """停止选股"""
        self._is_running = False
