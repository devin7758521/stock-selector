# -*- coding: utf-8 -*-
"""
主窗口UI

遵循MVC架构，UI只负责显示，不包含业务逻辑
"""

from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QTextEdit, QSplitter, QGroupBox, QProgressBar, QHeaderView,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class MainWindow(QMainWindow):
    """
    主窗口
    
    遵循MVC架构：
    - View只负责显示
    - 通过signal与controller通信
    - 不直接调用业务逻辑
    """
    
    # Signals - UI向Controller发送的信号
    start_screening_requested = pyqtSignal()
    stop_screening_requested = pyqtSignal()
    stock_selected = pyqtSignal(str, str)  # code, name
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JusticePlutus - A股周K线选股系统")
        self.setGeometry(100, 100, 1400, 900)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI布局"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addLayout(toolbar)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 主内容区域（分割器）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：选股结果表格
        left_panel = self._create_results_table()
        splitter.addWidget(left_panel)
        
        # 右侧：详情面板
        right_panel = self._create_detail_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([900, 500])
        
        main_layout.addWidget(splitter, stretch=1)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)
    
    def _create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        layout = QHBoxLayout()
        
        # 开始选股按钮
        self.start_btn = QPushButton("🚀 开始选股")
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_btn)
        
        # 停止按钮
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self.stop_btn)
        
        # 弹性空间
        layout.addStretch()
        
        # 统计信息
        self.stats_label = QLabel("共筛选 0 只股票")
        self.stats_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(self.stats_label)
        
        return layout
    
    def _create_results_table(self) -> QWidget:
        """创建选股结果表格"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title = QLabel("📊 选股结果")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "股票代码", "股票名称", "价格", "成交额(亿)",
            "周K均线", "量能偏离%", "AI评级", "LLM评级"
        ])
        
        # 设置表格属性
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        
        # 设置列宽
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        # 连接选择信号
        self.results_table.itemClicked.connect(self._on_table_item_clicked)
        
        layout.addWidget(self.results_table)
        
        return widget
    
    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title = QLabel("📈 详细分析")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 技术指标组
        tech_group = QGroupBox("技术指标分析")
        tech_layout = QVBoxLayout(tech_group)
        self.tech_text = QTextEdit()
        self.tech_text.setReadOnly(True)
        self.tech_text.setMaximumHeight(150)
        tech_layout.addWidget(self.tech_text)
        layout.addWidget(tech_group)
        
        # 基本面组
        fund_group = QGroupBox("基本面分析")
        fund_layout = QVBoxLayout(fund_group)
        self.fund_text = QTextEdit()
        self.fund_text.setReadOnly(True)
        self.fund_text.setMaximumHeight(150)
        fund_layout.addWidget(self.fund_text)
        layout.addWidget(fund_group)
        
        # LLM分析组
        llm_group = QGroupBox("LLM 智能分析")
        llm_layout = QVBoxLayout(llm_group)
        self.llm_text = QTextEdit()
        self.llm_text.setReadOnly(True)
        llm_layout.addWidget(self.llm_text)
        layout.addWidget(llm_group, stretch=1)
        
        return widget
    
    def _on_start_clicked(self):
        """开始选股按钮点击"""
        self.start_screening_requested.emit()
    
    def _on_stop_clicked(self):
        """停止选股按钮点击"""
        self.stop_screening_requested.emit()
    
    def _on_table_item_clicked(self, item: QTableWidgetItem):
        """表格项点击"""
        row = item.row()
        code_item = self.results_table.item(row, 0)
        name_item = self.results_table.item(row, 1)
        
        if code_item and name_item:
            code = code_item.text()
            name = name_item.text()
            self.stock_selected.emit(code, name)
    
    # ========== Public API - Controller调用这些方法更新UI ==========
    
    def update_results(self, results: List[Dict]):
        """更新选股结果表格"""
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(result.get('code', '')))
            self.results_table.setItem(row, 1, QTableWidgetItem(result.get('name', '')))
            self.results_table.setItem(row, 2, QTableWidgetItem(f"{result.get('price', 0):.2f}"))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{result.get('daily_amount_yi', 0):.2f}"))
            self.results_table.setItem(row, 4, QTableWidgetItem(f"{result.get('ma25_weekly', 0):.2f}"))
            self.results_table.setItem(row, 5, QTableWidgetItem(f"{result.get('vol_deviation_pct', 0):.2f}%"))
            
            # AI评级
            ai_rating = result.get('ai_star_display', '')
            self.results_table.setItem(row, 6, QTableWidgetItem(ai_rating))
            
            # LLM评级
            llm_rating = result.get('llm_star_display', '')
            self.results_table.setItem(row, 7, QTableWidgetItem(llm_rating))
        
        self.stats_label.setText(f"共筛选 {len(results)} 只股票")
    
    def update_detail(self, result: Dict):
        """更新详情面板"""
        # 技术指标
        tech_info = self._format_technical_info(result)
        self.tech_text.setPlainText(tech_info)
        
        # 基本面
        fund_info = self._format_fundamental_info(result)
        self.fund_text.setPlainText(fund_info)
        
        # LLM分析
        llm_info = self._format_llm_info(result)
        self.llm_text.setPlainText(llm_info)
    
    def _format_technical_info(self, result: Dict) -> str:
        """格式化技术指标信息"""
        info = []
        info.append(f"股票代码: {result.get('code', 'N/A')}")
        info.append(f"股票名称: {result.get('name', 'N/A')}")
        info.append(f"当前价格: {result.get('price', 0):.2f} 元")
        info.append(f"成交额: {result.get('daily_amount_yi', 0):.2f} 亿")
        info.append(f"周K均线: {result.get('ma25_weekly', 0):.2f}")
        info.append(f"量能偏离: {result.get('vol_deviation_pct', 0):.2f}%")
        
        if 'technical_analysis' in result:
            ta = result['technical_analysis']
            info.append("\n技术指标:")
            info.append(f"  MACD: {ta['macd']['value']:.2f}")
            info.append(f"  KDJ: ({ta['kdj']['k']:.1f}, {ta['kdj']['d']:.1f}, {ta['kdj']['j']:.1f})")
            info.append(f"  RSI: {ta['rsi']:.1f}")
        
        return '\n'.join(info)
    
    def _format_fundamental_info(self, result: Dict) -> str:
        """格式化基本面信息"""
        info = []
        
        if 'fundamental_analysis' in result:
            fa = result['fundamental_analysis']
            info.append(f"ROE: {fa['roe']:.2f}%")
            info.append(f"PE: {fa['pe']:.1f}")
            info.append(f"PB: {fa['pb']:.2f}")
            info.append(f"EPS: {fa['eps']:.2f}")
            info.append(f"营收增长率: {fa['revenue_growth']:.2f}%")
            info.append(f"\n基本面评分: {fa['score']}/100")
        else:
            info.append("暂无基本面数据")
        
        return '\n'.join(info)
    
    def _format_llm_info(self, result: Dict) -> str:
        """格式化LLM分析信息"""
        info = []
        
        if 'llm_analysis' in result:
            llm = result['llm_analysis']
            info.append(f"情绪分: {llm.get('sentiment_score', 0)}")
            info.append(f"评级: {llm.get('star_rating', 0)} 星")
            info.append(f"趋势预测: {llm.get('trend_prediction', 'N/A')}")
            info.append(f"操作建议: {llm.get('operation_advice', 'N/A')}")
            info.append(f"\n打星理由:\n{llm.get('star_reason', 'N/A')}")
        else:
            info.append("暂无LLM分析数据")
        
        return '\n'.join(info)
    
    def set_screening_state(self, is_running: bool):
        """设置选股状态"""
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        self.progress_bar.setVisible(is_running)
        
        if is_running:
            self.status_label.setText("正在选股...")
        else:
            self.status_label.setText("选股完成")
    
    def update_progress(self, current: int, total: int):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在处理: {current}/{total}")
    
    def show_error(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)
        self.status_label.setText(f"错误: {message}")
    
    def show_info(self, message: str):
        """显示信息消息"""
        QMessageBox.information(self, "信息", message)
