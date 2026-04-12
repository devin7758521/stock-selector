# -*- coding: utf-8 -*-
"""
选股控制器

遵循MVC架构：
- Controller负责协调Model和View
- 通过signal/slot机制通信
- 不直接操作UI控件
"""

from typing import Optional, Dict, List
from PyQt6.QtCore import QObject, pyqtSignal

from screener.core import StockSelector
from .worker import ScreeningWorker


class StockScreenerController(QObject):
    """
    选股控制器
    
    职责：
    1. 连接UI和业务逻辑
    2. 管理后台工作线程
    3. 处理选股结果
    4. 管理缓存
    """
    
    # Signals - 向UI发送信号
    results_updated = pyqtSignal(list)
    detail_updated = pyqtSignal(dict)
    screening_started = pyqtSignal()
    screening_stopped = pyqtSignal()
    progress_updated = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config_path: str = "config.yaml"):
        super().__init__()
        
        # Model
        self._selector = StockSelector(config_path)
        
        # Worker
        self._worker: Optional[ScreeningWorker] = None
        
        # Cache
        self._results: List[Dict] = []
        self._current_stock: Optional[Dict] = None
    
    def connect_view(self, view):
        """
        连接视图
        
        Args:
            view: MainWindow实例
        """
        # 连接View的信号到Controller的slot
        view.start_screening_requested.connect(self.start_screening)
        view.stop_screening_requested.connect(self.stop_screening)
        view.stock_selected.connect(self.on_stock_selected)
        
        # 连接Controller的信号到View的slot
        self.results_updated.connect(view.update_results)
        self.detail_updated.connect(view.update_detail)
        self.screening_started.connect(lambda: view.set_screening_state(True))
        self.screening_stopped.connect(lambda: view.set_screening_state(False))
        self.progress_updated.connect(view.update_progress)
        self.error_occurred.connect(view.show_error)
    
    def start_screening(self):
        """开始选股"""
        # 清空之前的结果
        self._results.clear()
        
        # 创建工作线程
        self._worker = ScreeningWorker(self._selector)
        
        # 连接worker信号
        self._worker.progress_updated.connect(self.progress_updated.emit)
        self._worker.stock_found.connect(self._on_stock_found)
        self._worker.screening_finished.connect(self._on_screening_finished)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        
        # 启动线程
        self._worker.start()
        
        # 发送开始信号
        self.screening_started.emit()
    
    def stop_screening(self):
        """停止选股"""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()
        
        # 发送停止信号
        self.screening_stopped.emit()
    
    def on_stock_selected(self, code: str, name: str):
        """
        股票被选中
        
        Args:
            code: 股票代码
            name: 股票名称
        """
        # 从缓存中查找
        for result in self._results:
            if result.get('code') == code:
                self._current_stock = result
                self.detail_updated.emit(result)
                break
    
    def _on_stock_found(self, result: Dict):
        """发现符合条件的股票"""
        self._results.append(result)
    
    def _on_screening_finished(self, results: List[Dict]):
        """选股完成"""
        self._results = results
        self.results_updated.emit(results)
        self.screening_stopped.emit()
    
    def get_results(self) -> List[Dict]:
        """获取选股结果"""
        return self._results.copy()
    
    def get_current_stock(self) -> Optional[Dict]:
        """获取当前选中的股票"""
        return self._current_stock.copy() if self._current_stock else None
