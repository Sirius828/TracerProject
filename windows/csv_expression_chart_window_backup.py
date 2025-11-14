import numpy as np
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel, QHBoxLayout, QMenu, QAction, QMessageBox, QDialog, QComboBox, QDialogButtonBox, QFormLayout
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class CSVExpressionChartWindow(QMainWindow):
    """
    通道电压图表窗口，显示实时电压-时间曲线和当前电压值
    """
    def __init__(self, channel_name, ai_task, main_win, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"通道 {channel_name}")
        self.channel_name = channel_name
        self.ai_task = ai_task
        
        # 电压单位设置
        self.voltage_unit = "mV"  # 默认单位为毫伏
        self.voltage_scale = 1000.0  # 转换系数：V -> mV
        
        # 数据缓冲
        self.time_data = np.zeros(1000)  # 最近1000个时间点
        self.voltage_data = np.zeros(1000)  # 最近1000个电压值
        self.ptr = 0  # 数据指针
        self.main_win = main_win
        
        # 创建数据队列和线程控制变量
        self.data_queue = Queue()
        self.reading_thread = None
        self.reading = False
        self.thread_error = False  # 新增：标记线程是否遇到错误
        
        # 记录起始时间用于时间戳计算
        self.start_time = None
        self.time_offset = 0.0  # 用于在暂停后继续时保持时间连续性
        self.last_timestamp = 0.0  # 记录最后一个时间点
        
        # 设置UI组件
        self.setup_ui()
        
        # 更新定时器 - 使用20ms刷新率
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(20)  # 20ms更新一次，即50Hz
        
        # 任务监控定时器 - 检查并尝试恢复读取线程
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_reading_thread)
        self.monitor_timer.start(500)  # 500ms检查一次
        
        # 启动数据读取线程
        self.start_reading_thread()
    
    def setup_ui(self):
        """设置UI组件"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
          # 顶部区域：显示当前电压值
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        voltage_label = QLabel("当前电压:")
        voltage_label.setFont(QFont("Arial", 14))
        top_layout.addWidget(voltage_label)
        
        self.voltage_value = QLabel(f"0.000 {self.voltage_unit}")
        self.voltage_value.setFont(QFont("Arial", 16, QFont.Bold))
        top_layout.addWidget(self.voltage_value)
        
        top_layout.addStretch(1)
        layout.addWidget(top_widget)
        
        # 底部区域：电压-时间曲线图
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Voltage', self.voltage_unit)
        self.plot_widget.setLabel('bottom', 'Time', 's')
        self.plot_widget.setTitle(f"{self.channel_name} 电压曲线")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground('w')  # 白色背景
        
        # 添加右键菜单支持
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)
          # 创建曲线项
        pen = pg.mkPen(color='b', width=2)
        self.curve = self.plot_widget.plot(self.time_data, self.voltage_data, pen=pen)
        
        layout.addWidget(self.plot_widget)
        self.setWidget(main_widget)
        self.resize(800, 500)
    
    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 添加属性设置选项
        properties_action = QAction("属性设置", self)
        properties_action.triggered.connect(self.show_properties_dialog)
        menu.addAction(properties_action)
        
        # 在鼠标位置显示菜单
        menu.exec_(self.plot_widget.mapToGlobal(pos))
    
    def show_properties_dialog(self):
        """显示属性设置对话框"""
        dialog = ChannelPropertiesDialog(self.voltage_unit, self)
        if dialog.exec_() == QDialog.Accepted:
            new_unit = dialog.get_voltage_unit()
            if new_unit != self.voltage_unit:
                self.set_voltage_unit(new_unit)
    
    def set_voltage_unit(self, unit):
        """设置电压单位"""
        # 单位转换映射
        unit_scales = {
            "V": 1.0,
            "mV": 1000.0,
            "uV": 1000000.0
        }
        
        if unit in unit_scales:
            self.voltage_unit = unit
            self.voltage_scale = unit_scales[unit]
            
            # 更新界面显示
            self.plot_widget.setLabel('left', 'Voltage', self.voltage_unit)
            
            # 更新当前电压显示（重新获取最新电压值）
            if hasattr(self, 'last_voltage_value'):
                scaled_voltage = self.last_voltage_value * self.voltage_scale
                self.voltage_value.setText(f"{scaled_voltage:.3f} {self.voltage_unit}")
    
    def check_reading_thread(self):
        """检查读取线程状态并尝试恢复"""
        # 如果主窗口的任务已启动但我们的读取线程不在运行，重启线程
        if self.main_win.ai_task_started:
            if (not self.reading or 
                self.thread_error or 
                not self.reading_thread or 
                not self.reading_thread.is_alive()):
                logging.info(f"尝试重新启动通道 {self.channel_name} 的读取线程")
                # 更新任务对象引用（防止使用旧的无效任务）
                self.ai_task = self.main_win.ai_task
                self.thread_error = False
                self.start_reading_thread()
    
    def start_reading_thread(self):
        """启动数据读取线程"""
        # 停止任何可能在运行的旧线程
        self.reading = False
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=0.5)
        
        # 仅当有任务对象时启动线程（允许在暂停状态下打开窗口）
        if self.ai_task is not None:
            self.reading = True
            # 如果是首次启动或线程出错后重启，重置时间
            if self.start_time is None:
                self.start_time = time.time()
                # 保持时间连续性，使用之前记录的偏移
            else:
                # 重启时保持时间连续
                self.time_offset = self.last_timestamp
                self.start_time = time.time()
            
            self.reading_thread = threading.Thread(target=self.read_data)
            self.reading_thread.daemon = True
            self.reading_thread.start()
    
    def read_data(self):
        """在单独线程中读取数据并放入队列"""
        channel_index = None
        error_count = 0  # 错误计数器
        max_errors = 5  # 最大允许连续错误次数
        retry_interval = 0.1  # 错误后重试间隔(秒)
        
        try:
            # 获取通道索引
            if hasattr(self.ai_task, 'channels') and hasattr(self.ai_task.channels, 'channel_names'):
                available_channels = self.ai_task.channels.channel_names
                logging.info(f"读取线程中可用通道: {available_channels}")
                
                # 寻找当前通道的索引
                found = False
                for i, ch_name in enumerate(available_channels):
                    if ch_name == self.channel_name:
                        channel_index = i
                        found = True
                        break
                
                if not found:
                    logging.error(f"无法找到通道 {self.channel_name} 的索引")
                    self.reading = False
                    self.thread_error = True
                    return
            else:
                logging.error("任务没有通道信息")
                self.reading = False
                self.thread_error = True
                return
            
            logging.info(f"找到通道 {self.channel_name} 的索引: {channel_index}")
            
            while self.reading:
                try:
                    # 如果主窗口任务未启动，则等待
                    if not self.main_win.ai_task_started:
                        time.sleep(0.1)
                        continue
                    
                    # 增加任务状态检查
                    if self.ai_task is None:
                        # 尝试从主窗口更新任务引用
                        if hasattr(self.main_win, 'ai_task'):
                            self.ai_task = self.main_win.ai_task
                        else:
                            time.sleep(retry_interval)
                            continue
                    
                    # 尝试确认任务状态
                    try:
                        # 尝试读取非破坏性属性而不是直接调用read
                        if hasattr(self.ai_task, 'channels'):
                            _ = self.ai_task.channels
                        else:
                            raise Exception("任务对象无效")
                        
                        # 重置错误计数
                        error_count = 0
                    except Exception as e:
                        error_count += 1
                        logging.warning(f"任务状态检查失败: {str(e)}, 错误计数: {error_count}/{max_errors}")
                        if error_count >= max_errors:
                            logging.error(f"连续错误超过阈值，停止读取线程: {str(e)}")
                            self.reading = False
                            self.thread_error = True
                            break
                        # 等待后重试
                        time.sleep(retry_interval)
                        continue
                    
                    # 读取数据
                    data = self.ai_task.read(number_of_samples_per_channel=1)
                    
                    # 获取通道电压
                    voltage = data[channel_index][0] if isinstance(data[channel_index], (list, tuple, np.ndarray)) else data[channel_index]
                    
                    # 计算当前时间，考虑时间偏移量
                    current_time = time.time() - self.start_time + self.time_offset
                    self.last_timestamp = current_time  # 记录最后的时间戳
                    
                    # 将数据放入队列
                    self.data_queue.put((current_time, voltage))
                    
                except Exception as e:
                    error_count += 1
                    logging.warning(f"读取通道数据出错: {str(e)}, 错误计数: {error_count}/{max_errors}")
                    
                    if error_count >= max_errors:
                        logging.error(f"读取出错次数过多，停止线程: {str(e)}")
                        self.reading = False
                        self.thread_error = True
                        break
                        
                    # 短暂暂停后重试
                    time.sleep(retry_interval)
            
        except Exception as e:
            logging.error(f"读取线程初始化失败: {str(e)}")
            self.reading = False
            self.thread_error = True
    
    def update_plot(self):
        """更新图表数据"""
        # 即使任务未启动也显示已有数据，只是不更新新数据
        if not self.main_win.ai_task_started and self.data_queue.empty():
            return
        
        # 批量处理队列中所有数据
        data_processed = False
        data_count = 0
        max_process = 100  # 限制每次处理的最大数据量，避免UI阻塞
        
        while not self.data_queue.empty() and data_count < max_process:
            data_count += 1
            data_processed = True
            elapsed, voltage = self.data_queue.get()
              # 更新当前电压值显示 - 只在有数据时更新文本
            if data_count == 1:  # 只更新最新值
                self.last_voltage_value = voltage  # 保存原始电压值（伏特）
                scaled_voltage = voltage * self.voltage_scale
                self.voltage_value.setText(f"{scaled_voltage:.3f} {self.voltage_unit}")
              # 高效添加数据到缓冲区，存储转换后的电压值
            scaled_voltage = voltage * self.voltage_scale
            if self.ptr < len(self.time_data):
                self.time_data[self.ptr] = elapsed
                self.voltage_data[self.ptr] = scaled_voltage
                self.ptr += 1
            else:
                # 数组已满，移除最老的数据点
                self.time_data[:-1] = self.time_data[1:]
                self.time_data[-1] = elapsed
                self.voltage_data[:-1] = self.voltage_data[1:]
                self.voltage_data[-1] = scaled_voltage
        
        # 只有在有新数据时才更新曲线
        if data_processed:
            self.curve.setData(self.time_data[:self.ptr], self.voltage_data[:self.ptr])
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 停止所有定时器
        self.update_timer.stop()
        self.monitor_timer.stop()
        
        # 停止数据读取线程
        self.reading = False
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=0.5)
        super().closeEvent(event)

class ChannelPropertiesDialog(QDialog):
    """通道属性设置对话框"""
    def __init__(self, current_unit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("通道属性设置")
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
