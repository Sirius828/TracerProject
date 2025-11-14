from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QMenu, QAction, QMessageBox
from PyQt5.QtCore import Qt, QTimer
import pyqtgraph as pg
import numpy as np
import threading
import time
from queue import Queue
import logging

class ExpressionChartWindow(QMainWindow):
    def __init__(self, name, expression, channel_aliases, ai_task, parent=None):
        super().__init__(parent)
        self.setWindowTitle(name)
        self.name = name
        self.expression = expression
        self.channel_aliases = channel_aliases
        self.ai_task = ai_task
        self.reading = False
        self.data_queue = Queue(maxsize=1000)
        
        # 电压单位设置
        self.voltage_unit = "mV"  # 默认单位为毫伏
        self.voltage_scale = 1000.0  # 转换系数：V -> mV
        
        # 初始化数据存储
        self.times = []
        self.data = []
        
        # 用于存储时间和数据点
        self.time_data = np.zeros(1000)
        self.result_data = np.zeros(1000)
        self.ptr = 0
        self.time_offset = 0.0
        self.last_timestamp = 0.0
        self.start_time = None
        
        # 设置窗口大小
        self.resize(800, 600)
        
        # 存储父窗口引用以便后续操作
        self.parent_window = parent
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
          # 添加图表标题和表达式显示
        info_layout = QHBoxLayout()
        expression_label = QLabel(f"表达式: {self.expression}")
        info_layout.addWidget(expression_label)
        self.value_display = QLabel(f"0.000 {self.voltage_unit}")
        info_layout.addWidget(self.value_display)
        layout.addLayout(info_layout)
        
        # 添加图表
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', f"数值 ({self.voltage_unit})")
        self.plot_widget.setLabel('bottom', "时间(s)")
        self.plot_widget.showGrid(x=True, y=True)
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color=(255, 0, 0), width=2))
        
        layout.addWidget(self.plot_widget)
        
        self.setCentralWidget(central_widget)
        
        # 提高定时器频率，增加实时性
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(16)  # 提高到约60Hz (1000/16≈62.5)
    
    def edit_properties(self):
        """编辑表达式图表属性"""
        # 检查父窗口是否可用
        if not self.parent_window or not hasattr(self.parent_window, 'smartAddExpressionChart'):
            QMessageBox.warning(self, "警告", "无法编辑属性，父窗口不可用")
            return
            
        try:
            # 需要导入相关对话框
            from dialogs.expression_chart_dialog import ExpressionChartDialog
            
            # 获取当前通道列表
            if hasattr(self.parent_window, 'added_channels'):
                channels = list(self.parent_window.added_channels)
                
                # 创建并显示表达式编辑对话框，传入当前值进行编辑
                dialog = ExpressionChartDialog(
                    self.parent_window, 
                    channels, 
                    "模拟输入",
                    self.name,
                    self.expression,
                    self.channel_aliases
                )
                
                if dialog.exec_():
                    # 更新表达式图表属性
                    new_name = dialog.name_edit.text()
                    new_expression = dialog.expr_edit.text()
                    new_channel_aliases = dialog.channel_aliases
                    
                    # 更新窗口标题和表达式
                    self.setWindowTitle(new_name)
                    self.name = new_name
                    self.expression = new_expression
                    self.channel_aliases = new_channel_aliases
                    
                    # 更新界面显示
                    child_widgets = self.centralWidget().findChildren(QLabel)
                    for widget in child_widgets:
                        if widget.text().startswith("表达式:"):
                            widget.setText(f"表达式: {new_expression}")
                            break
                    
                    # 清空数据并重新启动
                    self.clear_data()
                      # 如果正在读取，重新启动读取线程
                    if self.reading:
                        self.reading = False
                        if hasattr(self, 'reading_thread') and self.reading_thread:
                            self.reading_thread.join(timeout=0.5)
                        self.start_reading_thread()
            else:
                QMessageBox.warning(self, "警告", "无法获取通道列表")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"编辑属性时出错: {str(e)}")
    
    def reset_view(self):
        """重置图表视图"""
        if self.ptr > 0:
            # 重置为显示全部数据
            self.plot_widget.enableAutoRange()
    
    def clear_data(self):
        """清空已收集的数据"""
        self.ptr = 0
        self.time_data = np.zeros(1000)
        self.result_data = np.zeros(1000)
        self.value_display.setText(f"0.000 {self.voltage_unit}")
        self.curve.setData([], [])
        self.time_offset = 0.0
        self.last_timestamp = 0.0
        self.start_time = None
          # 清空数据队列
        while not self.data_queue.empty():
            self.data_queue.get()
    
    def set_voltage_unit(self, unit):
        """设置电压单位"""
        # 单位转换映射
        unit_scales = {
            "V": 1.0,
            "mV": 1000.0,
            "uV": 1000000.0
        }
        
        if unit in unit_scales:
            # 计算转换系数
            old_scale = self.voltage_scale
            new_scale = unit_scales[unit]
            conversion_factor = new_scale / old_scale
            
            # 更新单位和比例
            self.voltage_unit = unit
            self.voltage_scale = new_scale
            
            # 更新界面显示
            self.plot_widget.setLabel('left', f"数值 ({self.voltage_unit})")
            
            # 转换现有数据
            if self.ptr > 0:
                self.result_data[:self.ptr] = self.result_data[:self.ptr] * conversion_factor
                self.curve.setData(self.time_data[:self.ptr], self.result_data[:self.ptr])
            
            # 更新当前显示值
            current_text = self.value_display.text()
            try:
                # 提取数值部分
                value_part = current_text.split()[0]
                current_value = float(value_part)
                new_value = current_value * conversion_factor
                self.value_display.setText(f"{new_value:.3f} {self.voltage_unit}")
            except (ValueError, IndexError):
                self.value_display.setText(f"0.000 {self.voltage_unit}")
    
    def start_reading_thread(self):
        self.reading = True
        self.reading_thread = threading.Thread(target=self.read_data)
        self.reading_thread.daemon = True
        self.reading_thread.start()
    
    def read_data(self):
        while self.reading:
            try:
                # 检查AI任务是否有效且已启动
                if self.ai_task is None:
                    time.sleep(0.1)
                    continue
                    
                try:
                    # 尝试读取一个样本测试任务状态
                    is_task_active = True
                    _ = self.ai_task.read(number_of_samples_per_channel=1)
                except Exception as e:
                    # 如果读取失败，可能是因为任务未启动
                    is_task_active = False
                    logging.debug(f"任务可能未启动: {str(e)}")
                    time.sleep(0.1)
                    continue
                    
                # 获取所有通道的数据
                data = self.ai_task.read(number_of_samples_per_channel=1)
                
                # 优化日志输出，避免过度记录
                if np.random.random() < 0.01:  # 只有约1%的概率输出调试信息
                    logging.debug(f"读取到的数据结构类型: {type(data)}")
                    if isinstance(data, dict):
                        logging.debug(f"数据中的键: {list(data.keys())}")
                    elif isinstance(data, (list, np.ndarray)):
                        data_array = np.array(data)
                        logging.debug(f"数据形状: {data_array.shape if hasattr(data_array, 'shape') else len(data)}")
                
                # 创建通道值字典
                values = {}
                # 首先确保所有别名都有默认值，避免表达式中出现未定义变量
                for alias in self.channel_aliases.keys():
                    values[alias] = 0.0  # 默认值为0
                
                # 然后处理实际读取的数据，支持多种可能的数据结构
                if isinstance(data, dict):  # 如果返回的是字典
                    for alias, channel in self.channel_aliases.items():
                        if channel in data and len(data[channel]) > 0:
                            values[alias] = float(data[channel][0])  # 确保是标量值
                
                elif isinstance(data, (list, np.ndarray)):  # 如果返回的是数组
                    data_array = np.array(data)
                    
                    # 特殊处理常见的(4,1)结构 - 这是最常见的情况
                    if len(data_array.shape) > 1 and data_array.shape[1] == 1:
                        channel_order = list(self.channel_aliases.keys())
                        for i, alias in enumerate(channel_order):
                            if i < data_array.shape[0]:
                                values[alias] = float(data_array[i][0])
                    
                    # 其他情况的处理逻辑保持不变
                    # 优化针对一维数组的处理
                    elif len(data_array.shape) == 1:
                        channel_order = list(self.channel_aliases.keys())
                        for i, alias in enumerate(channel_order):
                            if i < len(data_array):
                                values[alias] = float(data_array[i])
                                logging.debug(f"一维数组: 为通道别名 {alias} 分配值 {data_array[i]}")
                    
                    # 处理通道在第一维的情况 - 常见于NI DAQmx返回的数据格式
                    elif data_array.shape[0] == len(self.channel_aliases):
                        channel_order = list(self.channel_aliases.keys())
                        for i, alias in enumerate(channel_order):
                            if data_array.shape[1] > 0:  # 确保有样本
                                values[alias] = float(data_array[i][0])  # 取第一个样本
                                logging.debug(f"二维数组(通道优先): 为通道别名 {alias} 分配值 {data_array[i][0]}")
                    
                    # 处理通道在第二维的情况
                    elif data_array.shape[1] == len(self.channel_aliases):
                        channel_order = list(self.channel_aliases.keys())
                        for i, alias in enumerate(channel_order):
                            values[alias] = float(data_array[0][i])  # 取第一个样本
                            logging.debug(f"二维数组(样本优先): 为通道别名 {alias} 分配值 {data_array[0][i]}")
                    
                    # 尝试通过大小判断数据结构
                    elif data_array.shape[0] > 0 and data_array.shape[1] > 0:
                        logging.debug("尝试根据维度大小确定通道分布")
                        channel_order = list(self.channel_aliases.keys())
                        
                        # 特殊处理常见的(4,1)或类似结构 - 通道在第一维，每个通道一个样本
                        if data_array.shape[1] == 1:
                            for i, alias in enumerate(channel_order):
                                if i < data_array.shape[0]:
                                    values[alias] = float(data_array[i][0])
                                    logging.debug(f"特殊处理(N,1): 为通道别名 {alias} 分配值 {data_array[i][0]}")
                        else:
                            # 回退到简单映射
                            logging.warning(f"未识别的数据结构，尝试简单映射: {data_array.shape}")
                            for i, alias in enumerate(channel_order):
                                if i < min(data_array.shape):
                                    values[alias] = float(data_array[i % data_array.shape[0]][i % data_array.shape[1]])
                
                # 计算表达式结果前记录中间值
                logging.debug(f"用于计算表达式的变量值: {values}")
                
                # 计算表达式结果
                result = self.evaluate_expression(self.expression, values)
                logging.debug(f"表达式计算结果: {result}")
                
                # 确保结果是标量
                if hasattr(result, '__len__'):
                    logging.warning(f"表达式结果不是标量: {result}，尝试转换")
                    try:
                        result = float(result[0] if len(result) > 0 else 0.0)
                    except (TypeError, IndexError):
                        result = 0.0
                
                # 记录当前时间
                if self.start_time is None:
                    self.start_time = time.time()
                current_time = time.time() - self.start_time + self.time_offset
                
                # 将数据放入队列
                self.data_queue.put((current_time, result))
                self.last_timestamp = current_time
                
            except Exception as e:
                # 减少日志输出频率，避免日志刷屏
                if np.random.random() < 0.1:  # 只有约10%的错误会被记录
                    logging.error(f"读取数据时出错: {e}")
                time.sleep(0.1)  # 发生错误时暂停一下，避免CPU占用过高
            
            # 减少延迟，增加读取频率
            time.sleep(0.005)  # 提高到200Hz
    
    def update_plot(self):
        """更新图表显示，从队列获取数据并应用表达式"""
        # 优化：一次性处理队列中所有数据，避免延迟
        if self.data_queue.empty():
            return
            
        points_processed = 0
        max_points_per_update = 10  # 每次更新最多处理10个点
            
        while not self.data_queue.empty() and points_processed < max_points_per_update:
            try:                # 从队列获取最新数据
                timestamp, value = self.data_queue.get_nowait()
                points_processed += 1
                  # 确保数据是标量
                timestamp = float(timestamp)
                value = float(value)
                
                # 应用电压单位转换
                scaled_value = value * self.voltage_scale
                
                # 更新数据数组
                if self.ptr < len(self.time_data):
                    self.time_data[self.ptr] = timestamp
                    self.result_data[self.ptr] = scaled_value
                else:
                    # 扩展数组 - 一次扩展更多，减少频繁扩展
                    self.time_data = np.append(self.time_data, np.zeros(1000))
                    self.result_data = np.append(self.result_data, np.zeros(1000))
                    self.time_data[self.ptr] = timestamp
                    self.result_data[self.ptr] = scaled_value
                
                self.ptr += 1
                
                # 更新显示的值
                self.value_display.setText(f"{scaled_value:.3f} {self.voltage_unit}")
                
            except Exception as e:
                logging.error(f"处理数据点时出错: {e}")
        
        # 每次更新后一次性重绘图表
        if self.ptr > 0 and points_processed > 0:
            self.curve.setData(self.time_data[:self.ptr], self.result_data[:self.ptr])
            # 自动滚动
            if self.ptr > 100:  # 当有足够数据时
                self.plot_widget.setXRange(max(0, self.time_data[self.ptr-1] - 10), self.time_data[self.ptr-1])
    
    def evaluate_expression(self, expr, values):
        """计算表达式的值"""
        # 导入必要的数学函数
        from math import sin, cos, tan, log, log10, sqrt, exp, pi
        
        # 创建本地命名空间
        namespace = {
            'sin': sin, 'cos': cos, 'tan': tan,
            'sqrt': sqrt, 'exp': exp, 'log': log, 
            'log10': log10, 'pi': pi,
            'abs': abs
        }
        
        # 添加通道变量
        namespace.update(values)
        
        # 使用eval函数安全地计算表达式
        return eval(expr, {"__builtins__": {}}, namespace)
    
    def closeEvent(self, event):
        self.reading = False
        if hasattr(self, 'reading_thread') and self.reading_thread:
            self.reading_thread.join(timeout=0.5)
        super().closeEvent(event)
