import sys 
import artdaq
import numpy as np
import os
import json
import datetime
import logging
import threading
import time
import pandas as pd  # 添加pandas库用于CSV处理
from queue import Queue
from collections import deque  # 添加 deque 导入，修复未定义错误
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QMenu, QAction, QToolBar, QDockWidget,
    QTreeWidget, QTreeWidgetItem, QMdiArea, QMdiSubWindow, QTextEdit, QVBoxLayout,
    QDialog, QMessageBox, QInputDialog, QListWidgetItem, QDialogButtonBox, QFileDialog,
    QWidget, QLabel, QHBoxLayout, QCheckBox, QComboBox, QGridLayout, QLineEdit, QFrame, QPushButton, QGroupBox, QSpinBox, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint
from PyQt5.QtGui import QIcon, QFont, QDoubleValidator 
import pyqtgraph as pg

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# 确保子目录在导入路径中
sys.path.append(os.path.dirname(__file__))

# 导入所需的模块
from models.project_item import ProjectItem
from windows.chart_window import ChartWindow
from windows.channel_chart_window import ChannelChartWindow
from windows.quadrant_detector_window import QuadrantDetectorWindow
from windows.csv_quadrant_detector_window import CSVQuadrantDetectorWindow
from windows.csv_channel_chart_window import CSVChannelChartWindow
from dialogs.add_channel_dialog import AddChannelDialog
from dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from dialogs.quadrant_detector_dialog import QuadrantDetectorDialog
from dialogs.csv_config_dialog import CSVConfigDialog
from dialogs.csv_edit_config_dialog import CSVEditConfigDialog
from dialogs.expression_chart_dialog import ExpressionChartDialog
from windows.expression_chart_window import ExpressionChartWindow
from windows.csv_expression_chart_window import CSVExpressionChartWindow


class ChannelPropertiesDialog(QDialog):
    """通道属性设置对话框"""
    def __init__(self, current_unit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("通道属性设置")
        self.setMinimumWidth(300)  # 设置最小宽度 防止用户拖动窗口过小
        self.current_unit = current_unit
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self) # 创建主布局
        
        # 创建表单布局
        form_layout = QFormLayout() # 创建表单布局
        
        # 电压单位选择
        self.voltage_unit_combo = QComboBox() # 创建下拉框
        self.voltage_unit_combo.addItems(["V", "mV", "uV"]) # 添加选项
        self.voltage_unit_combo.setCurrentText(self.current_unit) # 设置当前选中项
        form_layout.addRow("电压单位:", self.voltage_unit_combo) # 添加到表单布局
        
        layout.addLayout(form_layout)
        
        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_voltage_unit(self):
        """获取选择的电压单位"""
        return self.voltage_unit_combo.currentText()

class ExpressionPropertiesDialog(QDialog):
    """表达式图表属性设置对话框"""
    def __init__(self, current_unit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("表达式图表属性设置")
        self.setMinimumWidth(300)
        self.current_unit = current_unit
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 创建表单布局
        form_layout = QFormLayout()
        
        # 电压单位选择
        self.voltage_unit_combo = QComboBox()
        self.voltage_unit_combo.addItems(["V", "mV", "uV"])
        self.voltage_unit_combo.setCurrentText(self.current_unit)
        form_layout.addRow("电压单位:", self.voltage_unit_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_voltage_unit(self):
        """获取选择的电压单位"""
        return self.voltage_unit_combo.currentText()

class MainWindow(QMainWindow): # 继承QMainWindow类，是程序的主窗口
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tracer")
        self.resize(1920, 1080)
        self.setWindowIcon(QIcon("app_icon.png"))  # 设置应用图标
        self.ai_task = None
        self.ai_task_started = False
        
        # 工程数据管理
        self.project_name = "工程1"
        self.project_data = {
            "name": self.project_name,
            "channels": [],
            "charts": [],
            "algorithms": [],
            "csv_files": []  # 添加CSV文件数据存储
        }
        self.project_file_path = None
        self.project_modified = False
        self.userdata_path = os.path.join(os.path.expanduser("~"), "userdata")
        # 确保userdata路径存在
        if not os.path.exists(self.userdata_path):
            os.makedirs(self.userdata_path)

        # CSV数据管理
        self.csv_data = {}  # 用于存储导入的CSV数据

        # 工作模式设置
        self.current_mode = "模拟输入"  # 可选值："模拟输入" 或 "CSV"
        
        # 操作按钮字典 - 存储所有工具栏按钮
        self.toolbarActions = {}
        
        # ============ 菜单栏 =============
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        view_menu = menubar.addMenu("视图")
        help_menu = menubar.addMenu("帮助")

        
        # 文件菜单里的内容
        new_action = QAction("新建工程", self)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("打开工程", self)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)

        save_action = QAction("保存工程", self)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        export_action = QAction("导出工程", self)
        file_menu.addAction(export_action)

        close_action = QAction("关闭工程", self)
        close_action.triggered.connect(self.close_project)
        file_menu.addAction(close_action)
        
        toggle_dock_action = QAction("显示侧栏", self)
        toggle_dock_action.triggered.connect(self.show_dock)
        view_menu.addAction(toggle_dock_action)        # 帮助菜单项
        update_log_action = QAction("更新日志", self)
        update_log_action.triggered.connect(self.show_update_log)
        help_menu.addAction(update_log_action)
        
        operation_guide_action = QAction("操作指引", self)
        operation_guide_action.triggered.connect(self.show_operation_guide)
        help_menu.addAction(operation_guide_action)
        
        help_menu.addSeparator()  # 添加分隔线
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # ============ 工具栏 =============
        self.setupToolbar()
        
        # ============ 中心区域 (MDI) =============
        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)

        # ============ 侧栏 (DockWidget) =============
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderHidden(True)
        self.project_tree.itemDoubleClicked.connect(self.open_item_window)
        self.project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self.on_tree_right_click)
        # 设置多选模式
        self.project_tree.setSelectionMode(QTreeWidget.ExtendedSelection)

        # 顶层"工程"节点
        self.project_root = QTreeWidgetItem(["工程1"])
        self.project_tree.addTopLevelItem(self.project_root)

        # "通道"节点
        self.channels_item = QTreeWidgetItem(["通道"])
        self.project_root.addChild(self.channels_item)

        # "图表"节点
        self.charts_item = QTreeWidgetItem(["图表"])
        self.project_root.addChild(self.charts_item)

        # "算法"节点
        self.algo_item = QTreeWidgetItem(["算法"])
        self.project_root.addChild(self.algo_item)

        # "CSV"节点 - 新增
        self.csv_item = QTreeWidgetItem(["CSV"])
        self.project_root.addChild(self.csv_item)
        # 初始时隐藏CSV节点，直到有CSV文件导入
        self.csv_item.setHidden(True)

        # 展开顶层"工程"节点
        self.project_tree.expandItem(self.project_root)
        
        # 创建侧栏 DockWidget
        dock = QDockWidget("Projects", self)
        dock.setWidget(self.project_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.project_dock = dock

        # ============ 定时器 (如有需要刷新数据) =============
        self.timer = QTimer(self)
        # self.timer.timeout.connect(self.update_data)
        # self.timer.start(100)
        
        self.added_channels = set()
        
        # 初始化状态栏
        self.statusBar().showMessage("就绪", 3000)
    
    def setupToolbar(self):
        """创建和设置统一上下文工具栏"""
        # 创建主工具栏
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setIconSize(QSize(44, 44))
        self.addToolBar(self.toolbar)
        
        # 添加模式选择下拉框
        mode_label = QLabel("工作模式: ")
        self.toolbar.addWidget(mode_label)
        
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["模拟输入", "CSV"])
        self.mode_selector.setCurrentText(self.current_mode)
        self.mode_selector.currentTextChanged.connect(self.changeMode)
        self.mode_selector.setFixedWidth(120)
        self.toolbar.addWidget(self.mode_selector)
        
        self.toolbar.addSeparator()
        
        # 创建统一的智能按钮
        self.addSmartActions()
        
        # 添加帮助按钮
        help_action = QAction(QIcon("icon/help.png"), "帮助", self) # 相对路径地址
        help_action.triggered.connect(self.show_about)
        self.toolbar.addAction(help_action)

    def addSmartActions(self):
        # 智能添加通道按钮 - 根据模式自动选择功能
        add_channel_act = QAction(QIcon("icon/plus.png"), "添加通道/数据", self)
        add_channel_act.triggered.connect(self.smartAddChannel)
        self.toolbar.addAction(add_channel_act)
        
        # 智能四象限探测器按钮 - 根据模式自动选择功能
        add_quadrant_act = QAction(QIcon("icon/windows.png"), "四象限探测器", self)
        add_quadrant_act.triggered.connect(self.smartAddQuadrant)
        self.toolbar.addAction(add_quadrant_act)
        
        # 采集/播放按钮 - 只在模拟输入模式可用
        self.acquisition_act = QAction(QIcon("icon/finish-flag.png"), "启动采集", self)
        self.acquisition_act.triggered.connect(self.toggle_acquisition)
        self.toolbar.addAction(self.acquisition_act)
        
        # 分析/算法按钮 - 通用功能
        add_algorithm_act = QAction(QIcon("icon/sensor.png"), "添加算法", self)
        add_algorithm_act.triggered.connect(self.smartAddAlgorithm)
        self.toolbar.addAction(add_algorithm_act)
        
        # 添加表达式图表按钮 - 两种模式都可用
        expression_chart_act = QAction(QIcon("icon/code.png"), "表达式图表", self)
        expression_chart_act.triggered.connect(self.smartAddExpressionChart)
        self.toolbar.addAction(expression_chart_act)

    def smartAddChannel(self):
        """智能添加通道/数据源"""
        if self.current_mode == "模拟输入":
            self.add_channel()
        else:
            self.import_csv_file()

    def smartAddQuadrant(self):
        """智能添加四象限探测器"""
        if self.current_mode == "模拟输入":
            self.add_quadrant_detector()
        else:
            self.show_csv_quadrant_dialog()
    
    def smartAddExpressionChart(self):
        """智能添加表达式图表"""
        if self.current_mode == "模拟输入":
            self.add_expression_chart()
        else:
            self.add_csv_expression_chart()
    
    def add_expression_chart(self):
        """添加表达式图表 - 模拟输入模式"""
        if len(self.added_channels) == 0:
            QMessageBox.warning(self, "警告", "请先添加通道")
            return
            
        from dialogs.expression_chart_dialog import ExpressionChartDialog
        
        # 创建表达式图表配置对话框
        dlg = ExpressionChartDialog(parent=self, channels=list(self.added_channels))
        if dlg.exec_() == QDialog.Accepted:
            chart_config = dlg.get_chart_config()
            
            # 添加到项目树
            item = ProjectItem(chart_config["name"], item_type="expression_chart")
            item.expression_data = chart_config
            self.charts_item.addChild(item)
            self.project_tree.expandItem(self.charts_item)
              # 标记工程已修改
            self.project_modified = True
            
            self.statusBar().showMessage(f"已创建表达式图表: {chart_config['name']}", 5000)
    
    def add_csv_expression_chart(self):
        """添加CSV表达式图表"""
        # 获取当前选中的CSV文件
        selected_csv = self.get_selected_csv()
        if not selected_csv:
            QMessageBox.warning(self, "警告", "请先选择一个CSV文件")
            return
            
        if selected_csv not in self.csv_data:
            QMessageBox.warning(self, "警告", "CSV数据未找到")
            return
            
        csv_data = self.csv_data[selected_csv]["data"]
        available_channels = list(csv_data.columns)
        
        from dialogs.expression_chart_dialog import ExpressionChartDialog
        
        # 创建表达式图表配置对话框
        dlg = ExpressionChartDialog(parent=self, channels=available_channels)
        if dlg.exec_() == QDialog.Accepted:
            chart_config = dlg.get_chart_config()
            chart_config["is_from_csv"] = True
            chart_config["csv_id"] = selected_csv
            
            # 找到CSV文件的图表节点
            csv_item = None
            for i in range(self.csv_item.childCount()):
                item = self.csv_item.child(i)
                if os.path.splitext(item.text(0))[0] == selected_csv:
                    csv_item = item
                    break
            
            if csv_item:
                # 找到图表节点
                charts_item = None
                for i in range(csv_item.childCount()):
                    child = csv_item.child(i)
                    if child.text(0) == "图表":
                        charts_item = child
                        break
                
                # 添加表达式图表项
                if charts_item:
                    item = ProjectItem(chart_config["name"], item_type="expression_chart")
                    item.expression_data = chart_config
                    charts_item.addChild(item)
                    self.project_tree.expandItem(charts_item)
                else:
                    # 如果没找到图表节点，添加到主图表节点
                    item = ProjectItem(chart_config["name"], item_type="expression_chart")
                    item.expression_data = chart_config
                    self.charts_item.addChild(item)
            
            # 标记工程已修改
            self.project_modified = True
            
            self.statusBar().showMessage(f"已创建CSV表达式图表: {chart_config['name']}", 5000)
    
    def get_selected_csv(self):
        """获取当前选中的CSV文件ID"""
        # 这里简化处理，返回第一个可用的CSV文件
        if self.csv_data:
            return list(self.csv_data.keys())[0]
        return None
    
    def changeMode(self, mode):
        """改变工作模式"""
        old_mode = self.current_mode
        self.current_mode = mode
        
        # 根据模式更新界面
        if mode == "CSV":
            # 切换到CSV模式
            self.acquisition_act.setEnabled(False)
            self.statusBar().showMessage(f"已切换到 {mode} 模式", 3000)
        else:
            # 切换到模拟输入模式
            self.acquisition_act.setEnabled(True)
            self.statusBar().showMessage(f"已切换到 {mode} 模式", 3000)
        
        logging.info(f"工作模式从 '{old_mode}' 切换到 '{mode}'")

    def smartAddAlgorithm(self):
        """智能添加分析算法"""
        # 可以根据模式提供不同的算法功能
        QMessageBox.information(self, "功能提示", "算法功能开发中...")

    def add_quadrant_detector(self):
        """添加四象限探测器"""
        # 确保当前模式为模拟输入模式
        if self.current_mode != "模拟输入":
            self.changeMode("模拟输入")
            
        if len(self.added_channels) == 0:
            QMessageBox.warning(self, "警告", "请先添加至少4个通道")
            return
            
        from dialogs.quadrant_detector_dialog import QuadrantDetectorDialog
        
        # 检查是否选中了通道
        selected_items = self.project_tree.selectedItems()
        selected_channels = []
        
        # 从选中的项目中提取通道名称
        for item in selected_items:
            if isinstance(item, ProjectItem) and item.item_type == "channel":
                selected_channels.append(item.text(0))
        
        # 创建四象限探测器配置对话框
        dlg = QuadrantDetectorDialog(list(self.added_channels), parent=self, preselected_channels=selected_channels)
        if dlg.exec_() == QDialog.Accepted:
            detector_config = dlg.get_detector_config()
            
            # 添加到项目树
            item = ProjectItem(detector_config["name"], item_type="quadrant_detector")
            item.detector_data = detector_config
            self.charts_item.addChild(item)
            self.project_tree.expandItem(self.charts_item)
            
            # 标记工程已修改
            self.project_modified = True
            
            self.statusBar().showMessage(f"已创建四象限探测器: {detector_config['name']}", 5000)

    def show_csv_quadrant_dialog(self):
        """显示CSV四象限探测器配置对话框"""
        # 获取当前选中的CSV文件
        selected_csv = self.get_selected_csv()
        if not selected_csv:
            QMessageBox.warning(self, "警告", "请先选择一个CSV文件")
            return
            
        if selected_csv not in self.csv_data:
            QMessageBox.warning(self, "警告", "CSV数据未找到")
            return
            
        csv_data = self.csv_data[selected_csv]["data"]
        available_channels = list(csv_data.columns)
        
        if len(available_channels) < 4:
            QMessageBox.warning(self, "警告", "CSV文件至少需要4个通道数据")
            return
            
        from dialogs.quadrant_detector_dialog import QuadrantDetectorDialog
        
        # 创建四象限探测器配置对话框
        dlg = QuadrantDetectorDialog(available_channels, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            detector_config = dlg.get_detector_config()
            detector_config["is_from_csv"] = True
            detector_config["csv_id"] = selected_csv
            
            # 找到CSV文件的图表节点
            csv_item = None
            for i in range(self.csv_item.childCount()):
                item = self.csv_item.child(i)
                if os.path.splitext(item.text(0))[0] == selected_csv:
                    csv_item = item
                    break
            
            if csv_item:
                # 找到图表节点
                charts_item = None
                for i in range(csv_item.childCount()):
                    child = csv_item.child(i)
                    if child.text(0) == "图表":
                        charts_item = child
                        break
                
                # 添加四象限探测器项
                if charts_item:
                    item = ProjectItem(detector_config["name"], item_type="quadrant_detector")
                    item.detector_data = detector_config
                    charts_item.addChild(item)
                    self.project_tree.expandItem(charts_item)
                else:
                 # 如果没找到图表节点，添加到主图表节点
                    item = ProjectItem(detector_config["name"], item_type="quadrant_detector")
                    item.detector_data = detector_config
                    self.charts_item.addChild(item)
            
            # 标记工程已修改
            self.project_modified = True
            
            self.statusBar().showMessage(f"已创建CSV四象限探测器: {detector_config['name']}", 5000)

    def import_csv_file(self):
        """导入CSV文件 - CSV模式下的智能添加通道功能"""
        from dialogs.csv_config_dialog import CSVConfigDialog
        
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择CSV文件", 
            "",
            "CSV文件 (*.csv);;所有文件 (*)"
        )
        
        if not file_path:
            return
            
        # 创建CSV配置对话框
        config_dialog = CSVConfigDialog(file_path, self)
        if config_dialog.exec_() == QDialog.Accepted:
            config = config_dialog.get_config()
            
            try:
                # 读取CSV文件
                df = pd.read_csv(file_path, header=0 if config["has_header"] else None)
                
                # 如果没有列名，自动生成列名
                if not config["has_header"]:
                    df.columns = [f"通道{i+1}" for i in range(len(df.columns))]
                
                # 获取文件名（不含路径和扩展名）
                file_name = os.path.basename(file_path)
                csv_id = os.path.splitext(file_name)[0]
                
                # 检查是否已存在同名文件
                if csv_id in self.csv_data:
                    reply = QMessageBox.question(
                        self, '确认', f'CSV文件 "{csv_id}" 已存在，是否替换？',
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
                
                # 显示CSV节点
                self.csv_item.setHidden(False)
                
                # 创建或更新CSV文件项
                csv_file_item = None
                for i in range(self.csv_item.childCount()):
                    item = self.csv_item.child(i)
                    if item.text(0) == file_name:
                        csv_file_item = item
                        # 清除现有子项
                        while csv_file_item.childCount() > 0:
                            csv_file_item.removeChild(csv_file_item.child(0))
                        break
                
                if not csv_file_item:
                    csv_file_item = QTreeWidgetItem([file_name])
                    self.csv_item.addChild(csv_file_item)
                
                # 创建通道和图表节点
                csv_channels_item = QTreeWidgetItem(["通道"])
                csv_file_item.addChild(csv_channels_item)
                
                csv_charts_item = QTreeWidgetItem(["图表"])
                csv_file_item.addChild(csv_charts_item)
                
                # 存储数据
                self.csv_data[csv_id] = {
                    "data": df,
                    "config": config,
                    "channels": {}
                }
                
                # 将每个通道添加到通道节点下
                for column in df.columns:
                    channel_item = ProjectItem(column, item_type="csv_channel")
                    channel_item.csv_id = csv_id  # 存储CSV ID以便后续访问数据
                    channel_item.column_name = column  # 存储列名
                    csv_channels_item.addChild(channel_item)
                    
                    # 存储通道项引用
                    self.csv_data[csv_id]["channels"][column] = channel_item
                
                # 展开新添加的项
                self.project_tree.expandItem(self.csv_item)
                self.project_tree.expandItem(csv_file_item)
                self.project_tree.expandItem(csv_channels_item)
                
                # 更新项目数据
                csv_file_data = {
                    "file_name": file_name,
                    "path": file_path,
                    "config": config
                }
                
                # 添加到项目数据中
                if "csv_files" not in self.project_data:
                    self.project_data["csv_files"] = []
                
                # 检查是否已存在，如果存在则替换
                existing_index = -1
                for i, csv_file in enumerate(self.project_data["csv_files"]):
                    if csv_file["file_name"] == file_name:
                        existing_index = i
                        break
                
                if existing_index >= 0:
                    self.project_data["csv_files"][existing_index] = csv_file_data
                else:
                    self.project_data["csv_files"].append(csv_file_data)
                
                # 标记工程已修改
                self.project_modified = True
                
                self.statusBar().showMessage(f"已导入CSV文件: {file_name} ({len(df.columns)}个通道, {len(df)}行数据)", 5000)
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取CSV文件时出错: {str(e)}")

    # ============ 以上为GUI设计 =============
    # ============ 以下为自定义函数 =============
    # ============= 文件操作 =============

    # 新建工程
    def new_project(self):
        """
        新建工程时，询问是否保存当前工程
        """
        if self.project_modified:
            reply = QMessageBox.question(
                self, '确认', '当前工程已修改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        # 先清理现有的采集任务
        if self.ai_task is not None:
            if self.ai_task_started:
                try:
                    self.ai_task.stop()
                except:
                    pass
                self.ai_task_started = False
                self.acquisition_act.setText("启动采集")
                self.acquisition_act.setIcon(QIcon("start_icon.png"))
            try:
                self.ai_task.close()
            except:
                pass
            self.ai_task = None
        
        # 获取新工程名称
        name, ok = QInputDialog.getText(self, '新建工程', '请输入工程名称:')
        if ok and name:
            self.project_name = name
            self.project_data = {
                "name": name,
                "channels": [],
                "charts": [],
                "algorithms": []
            }
            self.project_file_path = None
            self.project_modified = False
            self.added_channels = set()
            
            # 更新界面
            self.project_tree.clear()
            self.project_root = QTreeWidgetItem([name])
            self.project_tree.addTopLevelItem(self.project_root)
            self.channels_item = QTreeWidgetItem(["通道"])
            self.project_root.addChild(self.channels_item)
            self.charts_item = QTreeWidgetItem(["图表"])
            self.project_root.addChild(self.charts_item)
            self.algo_item = QTreeWidgetItem(["算法"])
            self.project_root.addChild(self.algo_item)
            self.project_tree.expandItem(self.project_root)
            
            # 关闭所有打开的窗口
            self.mdi_area.closeAllSubWindows()
    
    # 保存工程
    def save_project(self):
        """
        保存工程到文件
        """
        # 如果没有指定文件路径，则首先询问保存路径
        if not self.project_file_path:
            # 构建默认文件名
            default_filename = f"{self.project_name}.json"
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "保存工程", 
                os.path.join(self.userdata_path, default_filename),
                "JSON文件 (*.json)"
            )
            
            if not file_path:
                return  # 用户取消了保存
            
            self.project_file_path = file_path
        
        # 更新工程数据
        self.update_project_data()
        
        # 保存到文件
        try:
            with open(self.project_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.project_data, f, ensure_ascii=False, indent=2)
            self.project_modified = False
            # 使用状态栏替代消息框
            self.statusBar().showMessage(f"工程已保存到: {self.project_file_path}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存工程时出错: {str(e)}")

    # 更新工程数据
    def update_project_data(self):
        """
        从界面更新工程数据
        """
        # 收集通道数据
        channels = []
        for i in range(self.channels_item.childCount()):
            channel_item = self.channels_item.child(i)
            if isinstance(channel_item, ProjectItem) and channel_item.item_type == "channel":
                channels.append(channel_item.text(0))
        
        # 收集图表数据
        charts = []
        # 收集四象限探测器数据
        quadrant_detectors = []
        # 收集表达式图表数据
        expression_charts = []
        
        for i in range(self.charts_item.childCount()):
            chart_item = self.charts_item.child(i)
            if isinstance(chart_item, ProjectItem):
                if chart_item.item_type == "chart":
                    charts.append(chart_item.text(0))
                elif chart_item.item_type == "quadrant_detector" and hasattr(chart_item, 'detector_data'):
                    quadrant_detectors.append(chart_item.detector_data)
                elif chart_item.item_type == "expression_chart" and hasattr(chart_item, 'expression_data'):
                    expression_charts.append(chart_item.expression_data)
        
        # 收集算法数据
        algorithms = []
        for i in range(self.algo_item.childCount()):
            algo_item = self.algo_item.child(i)
            if isinstance(algo_item, ProjectItem) and algo_item.item_type == "algorithm":
                algorithms.append(algo_item.text(0))
        
        # 更新工程数据
        self.project_data["name"] = self.project_name
        self.project_data["channels"] = channels
        self.project_data["charts"] = charts
        self.project_data["algorithms"] = algorithms
        self.project_data["quadrant_detectors"] = quadrant_detectors
        self.project_data["expression_charts"] = expression_charts
        # 注意：CSV文件数据已在导入时添加到project_data中

    # 打开工程
    def open_project(self):
        """
        打开已有的工程
        """
        if self.project_modified:
            reply = QMessageBox.question(
                self, '确认', '当前工程已修改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        # 让用户选择工程文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "打开工程", 
            self.userdata_path,
            "JSON文件 (*.json)"
        )
        
        if file_path:
            self.load_project(file_path)
    
    # 加载工程
    def load_project(self, file_path):
        """
        从文件加载工程
        """
        try:
            # 先清理现有的采集任务
            if self.ai_task is not None:
                if self.ai_task_started:
                    try:
                        self.ai_task.stop()
                    except:
                        pass
                    self.ai_task_started = False
                    self.acquisition_act.setText("启动采集")
                    self.acquisition_act.setIcon(QIcon("start_icon.png"))
                try:
                    self.ai_task.close()
                except:
                    pass
                self.ai_task = None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                self.project_data = json.load(f)
            
            self.project_name = self.project_data.get("name", "未命名工程")
            self.project_file_path = file_path
            self.project_modified = False
            self.added_channels = set(self.project_data.get("channels", []))
            
            # 更新界面
            self.project_tree.clear()
            self.project_root = QTreeWidgetItem([self.project_name])
            self.project_tree.addTopLevelItem(self.project_root)
            
            # 添加通道节点
            self.channels_item = QTreeWidgetItem(["通道"])
            self.project_root.addChild(self.channels_item)
            for channel in self.project_data.get("channels", []):
                item = ProjectItem(channel, item_type="channel")
                self.channels_item.addChild(item)
            
            # 添加图表节点
            self.charts_item = QTreeWidgetItem(["图表"])
            self.project_root.addChild(self.charts_item)
            for chart in self.project_data.get("charts", []):
                item = ProjectItem(chart, item_type="chart")
                self.charts_item.addChild(item)
            
            # 添加算法节点
            self.algo_item = QTreeWidgetItem(["算法"])
            self.project_root.addChild(self.algo_item)
            for algo in self.project_data.get("algorithms", []):
                item = ProjectItem(algo, item_type="algorithm")
                self.algo_item.addChild(item)
            
            # 添加四象限探测器
            if "quadrant_detectors" in self.project_data:
                for detector in self.project_data["quadrant_detectors"]:
                    item = ProjectItem(detector["name"], item_type="quadrant_detector")
                    item.detector_data = detector
                    self.charts_item.addChild(item)
                    
            # 添加表达式图表
            if "expression_charts" in self.project_data:
                for expr_chart in self.project_data["expression_charts"]:
                    # 检查是否为CSV来源
                    if expr_chart.get("is_from_csv") and expr_chart.get("csv_id"):
                        csv_id = expr_chart.get("csv_id")
                        # 尝试找到对应CSV文件的图表节点
                        csv_item = None
                        for i in range(self.csv_item.childCount()):
                            item = self.csv_item.child(i)
                            if os.path.splitext(item.text(0))[0] == csv_id:
                                csv_item = item
                                break
                        
                        if csv_item:
                            # 找到图表节点
                            charts_item = None
                            for i in range(csv_item.childCount()):
                                child = csv_item.child(i)
                                if child.text(0) == "图表":
                                    charts_item = child
                                    break
                            
                            # 添加表达式图表项
                            if charts_item:
                                item = ProjectItem(expr_chart["name"], item_type="expression_chart")
                                item.expression_data = expr_chart
                                charts_item.addChild(item)
                                continue
                    
                    # 默认添加到主图表节点
                    item = ProjectItem(expr_chart["name"], item_type="expression_chart")
                    item.expression_data = expr_chart
                    self.charts_item.addChild(item)
            
            # 添加CSV节点 - 新增
            self.csv_item = QTreeWidgetItem(["CSV"])
            self.project_root.addChild(self.csv_item)
            
            # 加载CSV数据
            self.csv_data = {}  # 重置CSV数据
            
            if "csv_files" in self.project_data and self.project_data["csv_files"]:
                # 有CSV数据，显示CSV节点
                self.csv_item.setHidden(False)
                
                for csv_file in self.project_data["csv_files"]:
                    try:
                        file_name = csv_file["file_name"]
                        file_path = csv_file["path"]
                        config = csv_file["config"]
                        
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            logging.warning(f"CSV文件不存在: {file_path}")
                            continue
                            
                        # 读取CSV文件
                        df = pd.read_csv(file_path, header=0 if config["has_header"] else None)
                        
                        # 如果没有列名，自动生成列名
                        if not config["has_header"]:
                            df.columns = [f"通道{i+1}" for i in range(len(df.columns))]
                        
                        # 创建CSV文件项
                        csv_file_item = QTreeWidgetItem([file_name])
                        self.csv_item.addChild(csv_file_item)
                        
                        # 创建通道和图表节点
                        csv_channels_item = QTreeWidgetItem(["通道"])
                        csv_file_item.addChild(csv_channels_item)
                        
                        csv_charts_item = QTreeWidgetItem(["图表"])
                        csv_file_item.addChild(csv_charts_item)
                        
                        # 存储数据
                        csv_id = os.path.splitext(file_name)[0]
                        self.csv_data[csv_id] = {
                            "data": df,
                            "config": config,
                            "channels": {}
                        }
                        
                        # 将每个通道添加到通道节点下
                        for column in df.columns:
                            channel_item = ProjectItem(column, item_type="csv_channel")
                            channel_item.csv_id = csv_id  # 存储CSV ID以便后续访问数据
                            channel_item.column_name = column  # 存储列名
                            csv_channels_item.addChild(channel_item)
                            
                            # 存储通道项引用
                            self.csv_data[csv_id]["channels"][column] = channel_item
                        
                    except Exception as e:
                        logging.error(f"加载CSV文件时出错 {file_name}: {str(e)}")
            else:
                # 没有CSV数据，隐藏CSV节点
                self.csv_item.setHidden(True)
            
            self.project_tree.expandItem(self.project_root)
            
            # 关闭所有打开的窗口
            self.mdi_area.closeAllSubWindows()
            
            # 使用状态栏替代消息框
            self.statusBar().showMessage(f"已加载工程: {self.project_name}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载工程时出错: {str(e)}")

    # 关闭工程
    def close_project(self):
        """
        关闭当前工程，询问是否保存
        """
        if self.project_modified:
            reply = QMessageBox.question(
                self, '确认', '当前工程已修改，是否保存？',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_project()
            elif reply == QMessageBox.Cancel:
                return
        
        # 先清理现有的采集任务
        if self.ai_task is not None:
            if self.ai_task_started:
                try:
                    self.ai_task.stop()
                except:
                    pass
                self.ai_task_started = False
                self.acquisition_act.setText("启动采集")
                self.acquisition_act.setIcon(QIcon("start_icon.png"))
            try:
                self.ai_task.close()
            except:
                pass
            self.ai_task = None
        
        # 重置工程状态
        self.project_name = "新工程"
        self.project_data = {
            "name": self.project_name,
            "channels": [],
            "charts": [],
            "algorithms": []
        }
        self.project_file_path = None
        self.project_modified = False
        self.added_channels = set()
        
        # 清空界面
        self.project_tree.clear()
        self.project_root = QTreeWidgetItem([self.project_name])
        self.project_tree.addTopLevelItem(self.project_root)
        self.channels_item = QTreeWidgetItem(["通道"])
        self.project_root.addChild(self.channels_item)
        self.charts_item = QTreeWidgetItem(["图表"])
        self.project_root.addChild(self.charts_item)
        self.algo_item = QTreeWidgetItem(["算法"])
        self.project_root.addChild(self.algo_item)
        self.project_tree.expandItem(self.project_root)
        
        # 关闭所有打开的窗口
        self.mdi_area.closeAllSubWindows()
        
        # 使用状态栏替代消息框
        self.statusBar().showMessage("工程已关闭", 5000)
      # ============= 视图操作 =============
    # 显示侧栏
    def show_dock(self):
        if (self.project_dock.isHidden()):
            self.project_dock.show()
        else:
            self.project_dock.raise_()  # 如果已经显示，则将其置顶

    # ============= 帮助操作 =============
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>Tracer 电压监测应用</h2>
        <p><b>开发者:</b> 张圳豪</p>
        <p><b>描述:</b> 高精度多通道电压监测与数据分析系统</p>
        <br>
        <p><b>主要功能:</b></p>
        <ul>
        <li>多通道电压数据采集与实时监测</li>
        <li>智能四象限探测器管理</li>
        <li>CSV数据导入导出与分析</li>
        <li>表达式图表与数据可视化</li>
        <li>工程文件管理与配置保存（即将推出）</li>
        </ul>
        <br>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("关于 Tracer")
        msg.setTextFormat(Qt.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

    def show_update_log(self):
        """显示更新日志对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("更新日志 - Tracer")
        dialog.setFixedSize(700, 500)
        
        layout = QVBoxLayout(dialog)
          # 创建文本编辑器用于显示更新日志
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml("""
        <h2>Tracer 更新日志</h2>
        
        <h3>Version 2.1 - Build 2025.06.12 - 重大版本更新</h3>
        <p><strong>发布日期:</strong> 2025年6月12日</p>
        
        <h4>🐛 重要问题修复:</h4>
        <ul>
        <li><strong>修复表达式图表对话框缺失方法:</strong> 在ExpressionChartDialog中添加了缺失的get_chart_config()方法，解决了图表配置获取问题</li>
        <li><strong>恢复四象限探测器自动选择功能:</strong> 修复了当选择4个通道时自动配置四象限探测器的智能检测功能</li>
        <li><strong>实现智能通道排序系统:</strong> 新增支持多种命名格式的通道排序算法，包括数字、字母数字组合等格式</li>
        <li><strong>修复语法错误:</strong> 解决了smartAddAlgorithm()和changeMode()方法中的语法问题</li>
        </ul>
        
        <h4>✨ 新增功能:</h4>
        <ul>
        <li><strong>增强的通道管理:</strong> 改进了通道树形控件的智能排序功能</li>
        <li><strong>自动探测器配置:</strong> 优化了四象限探测器的自动配置逻辑</li>
        <li><strong>版本信息显示:</strong> 在窗口标题和帮助菜单中添加了版本信息</li>
        <li><strong>完整的帮助系统:</strong> 新增更新日志和操作指引功能</li>
        </ul>
        
        <h4>🔧 代码优化:</h4>
        <ul>
        <li><strong>完善的测试覆盖:</strong> 创建了全面的测试套件验证所有修复功能</li>
        <li><strong>改进的错误处理:</strong> 增强了各种异常情况的处理机制</li>
        <li><strong>代码结构优化:</strong> 改进了方法定义和代码组织结构</li>
        </ul>
        
        <h4>📊 测试验证:</h4>
        <ul>
        <li>通道排序测试: ✅ 所有测试通过</li>
        <li>bug修复验证测试: ✅ 核心功能测试通过</li>
        <li>详细的bug修复报告已生成</li>
        </ul>
          <hr>
        <h3>历史版本</h3>
        <h4>Tracer V2.0 - 初始版本</h4>
        <ul>
        <li>基础电压监测功能</li>
        <li>多通道数据采集</li>
        <li>基本图表显示</li>
        <li>工程文件管理</li>
        </ul>
        """)
        
        layout.addWidget(text_edit)
        
        # 添加关闭按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec_()

    def show_operation_guide(self):
        """显示操作指引对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("操作指引 - Tracer")
        dialog.setFixedSize(800, 600)
        
        layout = QVBoxLayout(dialog)
          # 创建文本编辑器用于显示操作指引
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml("""
        <h2>Tracer 操作指引</h2>
        
        <h3>🚀 快速开始</h3>
        <ol>
        <li><strong>创建新工程（未上线）:</strong> 文件 → 新建工程</li>
        <li><strong>添加通道:</strong> 点击工具栏中的"添加通道"按钮</li>
        <li><strong>开始监测:</strong> 配置好通道后点击"开始"按钮</li>
        </ol>
        
        <h3>📊 通道管理</h3>
        <h4>添加通道</h4>
        <ul>
        <li>点击"添加通道"按钮打开通道选择对话框</li>
        <li>从可用通道列表中选择需要监测的通道（直接双击通道或者点击按钮）</li>
        <li>配置通道属性（采样率、量程等）（开发中）</li>
        <li>点击确定添加通道到项目中</li>
        </ul>
        
        <h4>通道</h4>
        <ul>
        <li>右键点击通道可以修改通道属性和删除通道</li>
        <li>双击通道名称可以打开通道图表</li>

        </ul>
        
        <h3>🔍 四象限探测器</h3>
        <h4>自动配置</h4>
        <ul>
        <li>当项目中有4个通道及以上时，可以添加四象限探测器</li>
        <li>可以通过直接在侧栏选中四个通道，然后点击按钮，系统会预设好各象限使用到的通道</li>

        </ul>
        
        <h4>手动配置</h4>
        <ul>
        <li>右键点击四象限探测器项目</li>
        <li>选择"配置探测器"</li>
        <li>手动分配四个象限的通道</li>
        <li>设置探测器参数和计算公式</li>
        </ul>
        
        <h3>📈 数据可视化</h3>
        <h4>通道图表</h4>
        <ul>
        <li>双击通道项目可以打开实时数据图表</li>
        <li>支持缩放、平移、测量等操作</li>
        <li>可以设置Y轴范围和时间窗口</li>
        </ul>
        
        <h4>表达式图表</h4>
        <ul>
        <li>创建自定义数学表达式图表</li>
        <li>支持多通道数据的复杂运算</li>
        <li>实时更新计算结果</li>
        </ul>
        
        <h3>💾 数据管理</h3>
        <h4>CSV数据</h4>
        <ul>
        <li>支持导入外部CSV数据文件</li>
        <li>可以对历史数据进行分析</li>
        <li>支持数据导出功能</li>
        </ul>
        
        <h4>工程文件</h4>
        <ul>
        <li>保存当前项目配置为工程文件</li>
        <li>包含所有通道设置、探测器配置等</li>
        <li>支持快速加载之前的项目</li>
        </ul>
        

        
        <h4>实时监测</h4>
        <ul>
        <li>高精度数据采集</li>
        <li>可配置采样率</li>
        <li>实时数据处理和显示</li>
        <li>异常值检测和报警</li>
        </ul>
        
        <h3>❓ 常见问题</h3>
        <h4>Q: 如何处理通道连接失败？</h4>
        <p>A: 检查硬件连接，确认设备驱动已正确安装，重启软件重新尝试。</p>
        
        <h4>Q: 四象限探测器配置不正确怎么办？</h4>
        <p>A: 可以手动重新配置象限分配，确保四个通道按正确顺序连接。</p>
        
        <h4>Q: 数据采集速度慢怎么办？</h4>
        <p>A: 适当降低采样率，关闭不必要的图表窗口，确保系统资源充足。</p>
        
        <hr>
        <p><i>如需更多技术支持，请联系开发团队。</i></p>
        """)
        
        layout.addWidget(text_edit)
        
        # 添加关闭按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec_()

    # ============= 功能操作 =============
    
    def add_channel(self):
        """
        在主窗口中点击"添加通道"时的处理逻辑：
        1. 若尚未创建 self.ai_task，则创建
        2. 打开 AddChannelDialog 列出可用通道
        3. 将用户勾选的通道加入 self.ai_task 的配置
        4. 将通道名加入工程树和已添加通道列表
        """
        # 确保当前模式为模拟输入模式
        if self.current_mode != "模拟输入":
            self.changeMode("模拟输入")
            
        device_name = "Dev1"  # 假设只有一个设备 Dev1
        
        try:
            # 打开对话框，传递已使用的通道
            dlg = AddChannelDialog(device_name, parent=self, used_channels=self.added_channels)
            if dlg.exec_() == QDialog.Accepted:
                selected_chans = dlg.get_selected_channels()
                logging.debug(f"用户选择的通道: {selected_chans}")
                if not selected_chans:
                    QMessageBox.information(self, "提示", "未选择任何通道。")
                    return
                
                # 保存当前运行状态
                was_running = self.ai_task_started
                
                # 先关闭所有正在采集的窗口
                self.close_all_charts_reading_threads()
                
                # 如果已经在采集，先停止
                if self.ai_task_started:
                    try:
                        self.ai_task.stop()
                        self.ai_task_started = False
                    except Exception as e:
                        logging.error(f"停止任务时出错: {str(e)}")
                
                # 完全关闭并重建任务
                if self.ai_task is not None:
                    try:
                        self.ai_task.close()
                    except Exception as e:
                        logging.error(f"关闭任务时出错: {str(e)}")
                
                # 创建新任务
                try:
                    self.ai_task = artdaq.Task("myAiTask")
                    
                    # 添加所有通道(现有的和新的)
                    all_channels = list(self.added_channels) + selected_chans
                    for ch in all_channels:
                        self.ai_task.ai_channels.add_ai_voltage_chan(ch)
                    
                    # 配置采样率、采样模式等
                    self.ai_task.timing.cfg_samp_clk_timing(
                        rate=1000.0,
                        sample_mode=artdaq.constants.AcquisitionType.CONTINUOUS,
                        samps_per_chan=10
                    )
                    
                    # 如果之前在采集，则重新启动
                    if was_running:
                        self.ai_task.start()
                        self.ai_task_started = True
                        
                    # 更新所有图表窗口以使用新的任务
                    self.restart_all_charts()
                      # 给通道加到工程树 "通道" 节点(只添加新选择的通道)
                    for ch in selected_chans:
                        item = ProjectItem(ch, item_type="channel")
                        self.channels_item.addChild(item)
                    
                    # 对通道进行排序
                    self.sort_channels_in_tree()
                    
                    self.project_tree.expandItem(self.channels_item)
                    
                    # 更新已添加通道集合和修改状态
                    self.added_channels.update(selected_chans)
                    self.project_modified = True  # 标记工程已修改

                    # 使用状态栏替代消息框
                    self.statusBar().showMessage(f"已添加 {len(selected_chans)} 个通道", 5000)
                    
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"添加通道时出错: {str(e)}")
                    return
        except Exception as e:            # 捕获可能的artdaq.System错误但不中断流程
            logging.error(f"加载可用通道时出错: {str(e)}")
            # 继续使用对话框，让用户手动输入通道名称
    
    def sort_channels_in_tree(self):
        """对侧栏中的通道进行排序"""
        # 收集所有通道项
        channel_items = []
        for i in range(self.channels_item.childCount()):
            channel_items.append(self.channels_item.child(i))
        
        # 如果没有通道项，直接返回
        if not channel_items:
            return
        
        # 移除所有通道项
        for item in channel_items:
            self.channels_item.removeChild(item)
        
        # 定义排序函数
        def channel_sort_key(item):
            """
            通道排序键函数
            支持多种通道命名格式：
            - Dev1/ai0, Dev1/ai1, Dev1/ai10 等
            - ai0, ai1, ai10 等
            - 通道1, 通道2, 通道10 等
            """
            channel_name = item.text(0)
            
            import re
            
            # 尝试匹配 Dev1/ai数字 格式
            match = re.match(r'(.*/)?ai(\d+)', channel_name)
            if match:
                prefix = match.group(1) or ""
                number = int(match.group(2))
                return (0, prefix, number)  # 0 表示ai类型
            
            # 尝试匹配 Dev1/ao数字 格式
            match = re.match(r'(.*/)?ao(\d+)', channel_name)
            if match:
                prefix = match.group(1) or ""
                number = int(match.group(2))
                return (1, prefix, number)  # 1 表示ao类型
            
            # 尝试匹配 通道数字 格式
            match = re.match(r'通道(\d+)', channel_name)
            if match:
                number = int(match.group(1))
                return (2, "", number)  # 2 表示中文通道类型
            
            # 尝试匹配纯数字
            match = re.match(r'(\d+)', channel_name)
            if match:
                number = int(match.group(1))
                return (3, "", number)  # 3 表示纯数字类型
            
            # 其他情况按字母顺序排序
            return (4, channel_name.lower(), 0)
        
        # 对通道项进行排序
        sorted_items = sorted(channel_items, key=channel_sort_key)
        
        # 重新添加排序后的通道项
        for item in sorted_items:
            self.channels_item.addChild(item)
    
    def close_all_charts_reading_threads(self):
        """关闭所有图表窗口的数据读取线程"""
        for window in self.mdi_area.subWindowList():
            if isinstance(window, ChannelChartWindow):
                window.reading = False
                if hasattr(window, 'reading_thread') and window.reading_thread:
                    window.reading_thread.join(timeout=0.5)
            # 同时处理四象限探测器窗口
            elif isinstance(window, QuadrantDetectorWindow):
                window.reading = False
                if hasattr(window, 'reading_thread') and window.reading_thread:
                    try:
                        window.reading_thread.join(timeout=0.5)
                    except:
                        pass
            # 处理表达式图表窗口
            elif isinstance(window, ExpressionChartWindow):
                window.reading = False
                if hasattr(window, 'reading_thread') and window.reading_thread:
                    try:
                        window.reading_thread.join(timeout=0.5)
                    except:
                        pass
    
    
    
    def toggle_acquisition(self):
        """启动或停止数据采集"""
        if len(self.added_channels) == 0:
            QMessageBox.warning(self, "警告", "没有可用的通道，请先添加通道。")
            return
        
        # 标记当前想要的采集状态
        want_to_start = not self.ai_task_started
        
        if want_to_start:
            try:
                # 要启动采集
                # 先停止所有读取线程
                self.close_all_charts_reading_threads()
                
                # 完全关闭旧任务并创建新任务
                if self.ai_task is not None:
                    try:
                        self.ai_task.close()
                    except Exception as e:
                        logging.warning(f"关闭旧任务时出错: {str(e)}")
                    self.ai_task = None
                
                # 创建新任务
                self.ai_task = artdaq.Task("myAiTask")
                
                # 添加所有通道
                for ch in self.added_channels:
                    self.ai_task.ai_channels.add_ai_voltage_chan(ch)
                
                # 配置任务
                self.ai_task.timing.cfg_samp_clk_timing(
                    rate=1000.0,
                    sample_mode=artdaq.constants.AcquisitionType.CONTINUOUS,
                    samps_per_chan=10
                )
                
                # 启动任务
                self.ai_task.start()
                self.ai_task_started = True
                self.acquisition_start_time = datetime.datetime.now()
                self.acquisition_act.setText("暂停采集")
                self.acquisition_act.setIcon(QIcon("C:/Users/17106/Desktop/pythonProject/icon/finish-flag.png"))
                
                # 更新所有窗口的任务引用并启动读取线程
                self.restart_all_charts(keep_data=True)
                self.start_all_expression_charts_reading()
                
                self.statusBar().showMessage("采集已启动", 5000)
                
            except Exception as e:
                logging.error(f"启动采集时出错: {str(e)}")
                QMessageBox.critical(self, "错误", f"启动采集时出错: {str(e)}")
                self.ai_task_started = False
                self.acquisition_act.setText("启动采集")
                self.acquisition_act.setIcon(QIcon("C:/Users/17106/Desktop/pythonProject/icon/finish-flag.png"))
        else:
            # 要停止采集
            try:
                # 首先停止所有读取线程
                self.close_all_charts_reading_threads()
                
                if self.ai_task is not None:
                    try:
                        self.ai_task.stop()
                        self.ai_task.close()
                        self.ai_task = None
                    except Exception as e:
                        logging.warning(f"关闭任务时出错: {str(e)}")
                
                self.ai_task_started = False
                self.acquisition_act.setText("继续采集")
                self.acquisition_act.setIcon(QIcon("C:/Users/17106/Desktop/pythonProject/icon/finish-flag.png"))
                
                self.statusBar().showMessage("采集已暂停", 5000)
                
            except Exception as e:
                logging.error(f"暂停采集时出错: {str(e)}")
                QMessageBox.critical(self, "错误", f"暂停采集时出错: {str(e)}")

    def restart_all_charts(self, keep_data=False):
        """
        重启所有图表窗口，使用新的ai_task
        
        参数:
        keep_data (bool): 如果为True，保留现有的图表数据；如果为False，清空图表数据
        """
        for window in self.mdi_area.subWindowList():
            # 正确处理常规通道图表窗口
            if isinstance(window.widget(), ChannelChartWindow):
                # 确保先停止旧的读取线程
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.2)
                    except:
                        pass
                    
                # 更新图表窗口的任务引用
                window.widget().ai_task = self.ai_task
                
                # 清空数据队列，防止积压的数据导致图表快进
                while not window.widget().data_queue.empty():
                    window.widget().data_queue.get()
                
                if keep_data:
                    # 保存当前时间戳作为偏移量，使图表能够从当前点继续
                    if window.widget().ptr > 0 and window.widget().last_timestamp > 0:
                        window.widget().time_offset = window.widget().last_timestamp                    # 重置起始时间，但保留偏移量
                    window.widget().start_time = None
                else:
                    # 重置数据和时间
                    window.widget().ptr = 0
                    window.widget().time_data = np.zeros(1000)
                    window.widget().voltage_data = np.zeros(1000)
                    window.widget().voltage_value.setText(f"0.000 {window.widget().voltage_unit}")
                    window.widget().curve.setData([], [])
                    window.widget().time_offset = 0.0
                    window.widget().last_timestamp = 0.0
                    window.widget().start_time = None
                    
                # 重新启动读取线程
                if self.ai_task is not None and self.ai_task_started:
                    window.widget().start_reading_thread()
            
            # 处理四象限探测器窗口
            elif isinstance(window.widget(), QuadrantDetectorWindow):
                # 停止旧的读取线程
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.2)
                    except:
                        pass
                
                # 清空数据队列
                while not window.widget().data_queue.empty():
                    window.widget().data_queue.get()
                
                # 其余处理代码...保持不变
                # 如果采集任务已启动，则启动读取线程
                if self.ai_task is not None and self.ai_task_started:
                    window.widget().start_reading_thread(self.ai_task)
            
            # 处理表达式图表窗口 - 修复此部分以正确使用widget()
            elif isinstance(window.widget(), ExpressionChartWindow):
                # 停止旧的读取线程
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.2)
                    except:
                        pass
                    
                # 更新图表窗口的任务引用
                window.widget().ai_task = self.ai_task
                
                # 清空数据队列
                while not window.widget().data_queue.empty():
                    window.widget().data_queue.get()
                
                if keep_data:
                    # 保存当前时间戳作为偏移量，使图表能够从当前点继续
                    if window.widget().ptr > 0 and window.widget().last_timestamp > 0:
                        window.widget().time_offset = window.widget().last_timestamp
                    # 重置起始时间，但保留偏移量
                    window.widget().start_time = None
                else:
                    # 重置数据和时间
                    window.widget().ptr = 0
                    window.widget().time_data = np.zeros(1000)
                    window.widget().result_data = np.zeros(1000)
                    window.widget().value_display.setText("0.000")
                    window.widget().curve.setData([], [])
                    window.widget().time_offset = 0.0
                    window.widget().last_timestamp = 0.0
                    window.widget().start_time = None
                
                # 如果采集任务已启动，则启动读取线程
                if self.ai_task is not None and self.ai_task_started:
                    window.widget().start_reading_thread()

    def close_all_charts_reading_threads(self):
        """关闭所有图表窗口的数据读取线程"""
        for window in self.mdi_area.subWindowList():
            if isinstance(window.widget(), ChannelChartWindow):
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.5)
                    except:
                        pass
            # 同时处理四象限探测器窗口
            elif isinstance(window.widget(), QuadrantDetectorWindow):
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.5)
                    except:
                        pass
            # 处理表达式图表窗口
            elif isinstance(window.widget(), ExpressionChartWindow):
                window.widget().reading = False
                if hasattr(window.widget(), 'reading_thread') and window.widget().reading_thread:
                    try:
                        window.widget().reading_thread.join(timeout=0.5)
                    except:
                        pass

    def start_all_expression_charts_reading(self):
        """启动所有表达式图表的读取线程"""
        for window in self.mdi_area.subWindowList():
            if isinstance(window.widget(), ExpressionChartWindow) and not window.widget().reading:
                # 确保窗口引用了当前任务
                window.widget().ai_task = self.ai_task
                # 启动读取线程
                window.widget().start_reading_thread()
                logging.debug(f"已启动表达式图表 '{window.widget().name}' 的读取线程")

    def show_channel_properties(self, item):
        """显示通道属性设置对话框"""
        if not isinstance(item, ProjectItem) or item.item_type not in ["channel", "csv_channel"]:
            return
            
        # 获取当前通道的电压单位
        current_unit = getattr(item, 'voltage_unit', 'mV')
        
        # 创建属性对话框
        dialog = ChannelPropertiesDialog(current_unit, self)
        if dialog.exec_() == QDialog.Accepted:
            new_unit = dialog.get_voltage_unit()
            
            # 保存单位到项目项
            item.voltage_unit = new_unit
            
            # 更新所有相关的打开窗口
            self.update_channel_voltage_unit(item.text(0), new_unit)
            
            # 标记工程已修改
            self.project_modified = True
            
            # 显示状态栏信息
            self.statusBar().showMessage(f"通道 '{item.text(0)}' 电压单位已更新为 {new_unit}", 5000)
    
    def show_expression_properties(self, item):
        """显示表达式图表属性设置对话框"""
        if not isinstance(item, ProjectItem) or item.item_type not in ["expression_chart", "csv_expression"]:
            return
            
        # 获取当前表达式图表的电压单位
        current_unit = getattr(item, 'voltage_unit', 'mV')
        
        # 创建属性对话框
        dialog = ExpressionPropertiesDialog(current_unit, self)
        if dialog.exec_() == QDialog.Accepted:
            new_unit = dialog.get_voltage_unit()
            
            # 保存单位到项目项
            item.voltage_unit = new_unit
            
            # 更新所有相关的打开窗口
            self.update_expression_voltage_unit(item.text(0), new_unit)
            
            # 标记工程已修改
            self.project_modified = True            # 显示状态栏信息
            self.statusBar().showMessage(f"表达式图表 '{item.text(0)}' 电压单位已更新为 {new_unit}", 5000)
    
    def update_channel_voltage_unit(self, channel_name, new_unit):
        """更新通道图表窗口的电压单位"""
        for window in self.mdi_area.subWindowList():
            widget = window.widget()
            # 对于 QMdiSubWindow 类型，检查窗口本身而不是内部widget
            if isinstance(window, (ChannelChartWindow, CSVChannelChartWindow)):
                if hasattr(window, 'channel_name') and window.channel_name == channel_name:
                    if hasattr(window, 'set_voltage_unit'):
                        window.set_voltage_unit(new_unit)
            # 也检查widget，以防有其他类型的窗口
            elif isinstance(widget, (ChannelChartWindow, CSVChannelChartWindow)):
                if hasattr(widget, 'channel_name') and widget.channel_name == channel_name:
                    if hasattr(widget, 'set_voltage_unit'):
                        widget.set_voltage_unit(new_unit)
    
    def update_expression_voltage_unit(self, expression_name, new_unit):
        """更新表达式图表窗口的电压单位"""
        for window in self.mdi_area.subWindowList():
            widget = window.widget()
            # 更新表达式图表窗口
            if isinstance(widget, (ExpressionChartWindow, CSVExpressionChartWindow)):
                if hasattr(widget, 'name') and widget.name == expression_name:
                    if hasattr(widget, 'set_voltage_unit'):
                        widget.set_voltage_unit(new_unit)

    # ...existing code...
    
    def on_tree_right_click(self, position):
        """处理侧栏工程树的右键点击事件"""
        item = self.project_tree.itemAt(position)
        if not item:
            return
            
        # 获取项目项类型
        if hasattr(item, 'item_type'):
            item_type = item.item_type
        else:
            # 对于非ProjectItem类型的项，根据父节点判断类型
            parent = item.parent()
            if parent == self.channels_item:
                item_type = "channel"
            elif parent == self.charts_item:
                item_type = "expression_chart"
            elif parent and parent.parent() == self.csv_item:
                # CSV子项
                grandparent = parent.parent()
                if parent.text(0).endswith("通道数据"):
                    item_type = "csv_channel"
                elif parent.text(0).endswith("表达式图表"):
                    item_type = "csv_expression"
                else:
                    item_type = "unknown"
            else:
                item_type = "unknown"        
        # 创建右键菜单
        menu = QMenu(self)
        
        # 根据项目类型添加相应的菜单项
        if item_type in ["channel", "csv_channel"]:
            properties_action = QAction("属性设置", self)
            properties_action.triggered.connect(lambda: self.show_channel_properties(item))
            menu.addAction(properties_action)
            
            # 添加删除选项
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.delete_tree_item(item))
            menu.addAction(delete_action)
            
        elif item_type in ["expression_chart", "csv_expression"]:
            properties_action = QAction("属性设置", self)
            properties_action.triggered.connect(lambda: self.show_expression_properties(item))
            menu.addAction(properties_action)
            
            # 添加删除选项
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.delete_tree_item(item))
            menu.addAction(delete_action)
            
        elif item_type == "quadrant_detector":
            # 四象限探测器也添加删除选项
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.delete_tree_item(item))
            menu.addAction(delete_action)
        
        # 显示菜单
        if menu.actions():
            menu.exec_(self.project_tree.mapToGlobal(position))
    def open_item_window(self, item, column):
        """处理双击侧栏项目打开窗口事件"""
        # 检查项目类型
        if hasattr(item, 'item_type'):
            item_type = item.item_type
            item_name = item.text(0)
            
            if item_type == "channel":
                # 打开通道图表窗口
                # 允许在采集开始前打开窗口，但不开始读取数据
                window = ChannelChartWindow(item_name, self.ai_task, self)
                self.mdi_area.addSubWindow(window)
                window.show()
                
                # 只有在采集已启动且任务存在时才开始读取数据
                if self.ai_task_started and self.ai_task is not None:
                    window.start_reading_thread()
                    
            elif item_type == "csv_channel":
                # 打开CSV通道图表窗口
                csv_id = getattr(item, 'csv_id', None)
                column_name = getattr(item, 'column_name', item_name)
                
                if csv_id and csv_id in self.csv_data:
                    window = CSVChannelChartWindow(column_name, csv_id, self.csv_data[csv_id], self)
                    self.mdi_area.addSubWindow(window)
                    window.show()
                else:
                    QMessageBox.warning(self, "警告", "无法找到对应的CSV数据")
                    
            elif item_type == "expression_chart":
                # 打开表达式图表窗口
                if hasattr(item, 'expression_data'):
                    expr_data = item.expression_data
                    
                    if expr_data.get("is_from_csv"):
                        # CSV表达式图表
                        csv_id = expr_data.get("csv_id")
                        if csv_id and csv_id in self.csv_data:
                            window = CSVExpressionChartWindow(
                                expr_data["name"],
                                expr_data["expression"],
                                expr_data["channel_aliases"],
                                csv_id,
                                self.csv_data[csv_id],
                                self
                            )
                            self.mdi_area.addSubWindow(window)
                            window.show()
                        else:
                            QMessageBox.warning(self, "警告", "无法找到对应的CSV数据")
                    else:
                    # 实时表达式图表
                        # 允许在采集开始前打开窗口，但不开始读取数据
                        window = ExpressionChartWindow(
                            expr_data["name"],
                            expr_data["expression"],
                            expr_data["channel_aliases"],
                            self.ai_task,
                            self
                        )
                        self.mdi_area.addSubWindow(window)
                        window.show()
                        
                        # 只有在采集已启动且任务存在时才开始读取数据
                        if self.ai_task_started and self.ai_task is not None:
                            window.start_reading_thread()
                else:
                    QMessageBox.warning(self, "警告", "无法找到表达式图表配置")
                    
            elif item_type == "quadrant_detector":
                # 打开四象限探测器窗口
                if hasattr(item, 'detector_data'):
                    detector_data = item.detector_data
                    
                    if detector_data.get("is_from_csv"):
                        # CSV四象限探测器
                        csv_id = detector_data.get("csv_id")
                        if csv_id and csv_id in self.csv_data:
                            # 构建CSV数据和时间数据
                            csv_data = self.csv_data[csv_id]["data"]
                            channels = detector_data["channels"]
                            
                            # 构建CSV数据字典
                            csv_data_dict = {}
                            for channel in channels:
                                if channel in csv_data.columns:
                                    csv_data_dict[channel] = csv_data[channel].values
                            
                            # 提取时间数据
                            if "time" in csv_data.columns:
                                time_data = csv_data["time"].values
                            else:
                                # 生成时间序列
                                time_data = np.arange(len(csv_data)) * 0.001  # 假设1ms间隔
                            
                            window = CSVQuadrantDetectorWindow(
                                channels,
                                detector_data["name"],
                                csv_data_dict,
                                time_data,
                                detector_data.get("detector_size", 10.0),
                                detector_data.get("dead_zone", 0.5),
                                detector_data.get("pen_width", 2),
                                self
                            )
                            self.mdi_area.addSubWindow(window)
                            window.show()
                        else:
                            QMessageBox.warning(self, "警告", "无法找到对应的CSV数据")
                    else:
                        # 实时四象限探测器
                        # 允许在采集开始前打开窗口，但不开始读取数据
                        window = QuadrantDetectorWindow(
                            detector_data["channels"],
                            detector_data["name"],
                            detector_data.get("detector_size", 10.0),
                            detector_data.get("dead_zone", 0.5),
                            detector_data.get("pen_width", 2),
                            self
                        )
                        self.mdi_area.addSubWindow(window)
                        window.show()
                        
                        # 只有在采集已启动且任务存在时才开始读取数据
                        if self.ai_task_started and self.ai_task is not None:
                            window.start_reading_thread(self.ai_task)
                else:
                    QMessageBox.warning(self, "警告", "无法找到四象限探测器配置")
        else:
            # 对于非ProjectItem类型的项目，可能只是展开/折叠节点
            if item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
    
    # ============= 文件操作 =============
    def delete_tree_item(self, item):
        """删除项目树中的项目"""
        if not isinstance(item, ProjectItem):
            return
            
        reply = QMessageBox.question(
            self, '确认删除', f'确定要删除 "{item.text(0)}" 吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 先关闭相关的打开窗口
            self.close_related_windows(item)
            
            # 从项目树中移除
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            
            # 从对应的数据结构中移除
            if item.item_type == "channel":
                self.added_channels.discard(item.text(0))
                # 如果需要，重新配置采集任务
                if self.ai_task_started:
                    self.restart_acquisition_task()
            
            # 标记工程已修改
            self.project_modified = True
            self.statusBar().showMessage(f"已删除 {item.text(0)}", 3000)

    def close_related_windows(self, item):
        """关闭与指定项目相关的窗口"""
        item_name = item.text(0)
        item_type = item.item_type
        
        windows_to_close = []
        for window in self.mdi_area.subWindowList():
            widget = window.widget()
            should_close = False
            
            if item_type == "channel":
                # 关闭对应通道的图表窗口
                if isinstance(widget, (ChannelChartWindow, CSVChannelChartWindow)):
                    if hasattr(widget, 'channel_name') and widget.channel_name == item_name:
                        should_close = True
            elif item_type == "expression_chart":
                # 关闭对应的表达式图表窗口
                if isinstance(widget, (ExpressionChartWindow, CSVExpressionChartWindow)):
                    if hasattr(widget, 'chart_name') and widget.chart_name == item_name:
                        should_close = True
            elif item_type == "quadrant_detector":
                # 关闭对应的四象限探测器窗口
                if isinstance(widget, (QuadrantDetectorWindow, CSVQuadrantDetectorWindow)):
                    if hasattr(widget, 'detector_name') and widget.detector_name == item_name:
                        should_close = True
            
            if should_close:
                windows_to_close.append(window)
        
        # 关闭窗口
        for window in windows_to_close:
            window.close()

    def restart_acquisition_task(self):
        """重新启动采集任务以反映通道变化"""
        if not self.ai_task_started or len(self.added_channels) == 0:
            return
            
        try:
            # 停止当前任务
            if self.ai_task:
                self.ai_task.stop()
                self.ai_task.close()
            
            # 创建新任务
            self.ai_task = artdaq.Task("myAiTask")
            
            # 添加剩余的通道
            for ch in self.added_channels:
                self.ai_task.ai_channels.add_ai_voltage_chan(ch)
            
            # 配置并启动任务
            self.ai_task.timing.cfg_samp_clk_timing(
                rate=1000.0,
                sample_mode=artdaq.constants.AcquisitionType.CONTINUOUS,
                samps_per_chan=10
            )
            self.ai_task.start()
              # 重新启动所有图表的读取线程
            self.restart_all_charts(keep_data=True)
        
        except Exception as e:
            logging.error(f"重启采集任务时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"重启采集任务时出错: {str(e)}")

    def delete_tree_item(self, item):
        """删除项目树中的项目"""
        if not isinstance(item, ProjectItem):
            return
            
        reply = QMessageBox.question(
            self, '确认删除', f'确定要删除 "{item.text(0)}" 吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 先关闭相关的打开窗口
            self.close_related_windows(item)
            
            # 从项目树中移除项目
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            
            # 如果是通道，从已添加通道集合中移除并重启采集任务
            if item.item_type == "channel":
                channel_name = item.text(0)
                if channel_name in self.added_channels:
                    self.added_channels.remove(channel_name)
                    # 重启采集任务以反映通道变化
                    self.restart_acquisition_task()
            
            # 标记工程已修改
            self.project_modified = True
            
            self.statusBar().showMessage(f"已删除 '{item.text(0)}'", 5000)

    def close_related_windows(self, item):
        """关闭与指定项目相关的窗口"""
        item_name = item.text(0)
        item_type = item.item_type
        
        windows_to_close = []
        
        for window in self.mdi_area.subWindowList():
            widget = window.widget()
            should_close = False
            
            if item_type == "channel":
                # 关闭通道图表窗口
                if isinstance(widget, (ChannelChartWindow, CSVChannelChartWindow)):
                    if hasattr(widget, 'channel_name') and widget.channel_name == item_name:
                        should_close = True
                        
            elif item_type == "expression_chart":
                # 关闭表达式图表窗口
                if isinstance(widget, (ExpressionChartWindow, CSVExpressionChartWindow)):
                    if hasattr(widget, 'chart_name') and widget.chart_name == item_name:
                        should_close = True
                        
            elif item_type == "quadrant_detector":
                # 关闭四象限探测器窗口
                if isinstance(widget, (QuadrantDetectorWindow, CSVQuadrantDetectorWindow)):
                    if hasattr(widget, 'detector_name') and widget.detector_name == item_name:
                        should_close = True
            
            if should_close:
                windows_to_close.append(window)
          # 关闭相关窗口
        for window in windows_to_close:
            try:
                # 停止数据读取
                widget = window.widget()
                if hasattr(widget, 'reading'):
                    widget.reading = False
                if hasattr(widget, 'reading_thread') and widget.reading_thread:
                    widget.reading_thread.join(timeout=0.5)
                # 关闭窗口
                window.close()
            except Exception as e:
                logging.error(f"关闭窗口时出错: {str(e)}")

    def restart_acquisition_task(self):
        """重新启动采集任务以反映通道变化"""
        if not self.added_channels:
            # 如果没有通道了，停止采集
            if self.ai_task_started:
                self.toggle_acquisition()
            return
            
        if not self.ai_task_started:
            return  # 如果采集没有运行，不需要重启
            
        try:
            # 停止所有读取线程
            self.close_all_charts_reading_threads()
            
            # 停止并关闭当前任务
            if self.ai_task is not None:
                try:
                    self.ai_task.stop()
                    self.ai_task.close()
                except:
                    pass
            
            # 创建新任务
            self.ai_task = artdaq.Task("myAiTask")
            
            # 添加剩余的通道
            for ch in self.added_channels:
                self.ai_task.ai_channels.add_ai_voltage_chan(ch)
            
            # 配置并启动任务
            self.ai_task.timing.cfg_samp_clk_timing(
                rate=1000.0,
                sample_mode=artdaq.constants.AcquisitionType.CONTINUOUS,
                samps_per_chan=10
            )
            self.ai_task.start()
            
            # 重新启动所有图表的读取线程
            self.restart_all_charts(keep_data=True)
            
        except Exception as e:
            logging.error(f"重启采集任务时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"重启采集任务时出错: {str(e)}")


# 主程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("TracerV2.1")
    app.setApplicationVersion("2.1")
    app.setOrganizationName("Voltage Monitor")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 启动应用程序事件循环
    sys.exit(app.exec_())
    