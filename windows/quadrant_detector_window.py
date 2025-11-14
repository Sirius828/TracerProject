import numpy as np
import time
import logging
import threading
from queue import Queue
from collections import deque
from PyQt5.QtWidgets import QMdiSubWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
import pyqtgraph as pg

class QuadrantDetectorWindow(QMdiSubWindow):
    """
    四象限探测器窗口，显示激光点位置和四个象限电压值
    """
    def __init__(self, channels, detector_name, detector_size=10.0, dead_zone=0.5, pen_width=2, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"四象限探测器 - {detector_name}")
        self.setWindowIcon(QIcon())  # 设置空图标
        self.channels = channels  # 四个通道 [v1, v2, v3, v4]
        self.detector_name = detector_name
        self.detector_size = detector_size  # 探测器尺寸(mm)
        self.dead_zone = dead_zone  # 死区宽度(mm)
        self.pen_width = pen_width  # 画笔粗细
        
        # 位置有效性阈值
        self.voltage_threshold = 0.0001  # 电压阈值
        
        # 数据存储
        self.max_trail_length = 1000
        self.valid_x_data = deque(maxlen=self.max_trail_length)
        self.valid_y_data = deque(maxlen=self.max_trail_length)
        self.invalid_x_data = deque(maxlen=self.max_trail_length)
        self.invalid_y_data = deque(maxlen=self.max_trail_length)
        self.voltage_time = deque(maxlen=self.max_trail_length)
        self.voltage_data = [deque(maxlen=self.max_trail_length) for _ in range(4)]
        
        # 当前位置和强度数据
        self.position = (0.0, 0.0)  # (x, y)
        self.intensity = 0.0  # 总电压 (Z)
        self.relative_height = 0.0  # 相对高度
        self.valid_position = False  # 位置是否有效
        
        # 创建数据队列和线程控制变量
        self.data_queue = Queue()
        self.reading_thread = None
        self.reading = False
        
        # 记录起始时间用于时间戳计算
        self.start_time = None
        self.time_offset = 0.0  # 用于在暂停后继续时保持时间连续性
        self.last_timestamp = 0.0  # 记录最后一个时间点
        
        # 设置UI组件
        self.setup_ui()
        
        # 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.start(20)  # 20ms更新一次
    
    def setup_ui(self):
        """设置UI组件"""
        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        
        # 左侧：电压和位置信息显示
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
          # 电压标签 - 更新标签文本以反映新的象限顺序
        self.voltage_labels = []
        quadrant_names = ["右上", "左上", "左下", "右下"]
        for i, ch in enumerate(self.channels):
            label = QLabel(f"电压 {i+1} ({ch}) [{quadrant_names[i]}]: 0.000 V")
            label.setFont(QFont("Arial", 12))
            self.voltage_labels.append(label)
            left_layout.addWidget(label)
        
        # 总电压、位置和高度标签
        self.intensity_label = QLabel("总电压 (Z): 0.000 V")
        self.position_label = QLabel("位置: (0.00, 0.00) mm")
        self.height_label = QLabel("相对高度: 0.00 μm")
        
        for lbl in [self.intensity_label, self.position_label, self.height_label]:
            lbl.setFont(QFont("Arial", 12))
            left_layout.addWidget(lbl)
        
        # 更新位置有效性标签
        self.validity_label = QLabel("位置有效")
        self.validity_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.validity_label.setStyleSheet("color: green")
        left_layout.addWidget(self.validity_label)
        
        # 显示轨迹复选框
        self.trajectory_checkbox = QCheckBox("显示轨迹")
        self.trajectory_checkbox.setChecked(True)
        self.trajectory_checkbox.stateChanged.connect(self.toggle_trajectory)
        left_layout.addWidget(self.trajectory_checkbox)
        
        # 清除轨迹按钮
        self.clear_button = QPushButton("清除轨迹")
        self.clear_button.clicked.connect(self.clear_trajectory)
        left_layout.addWidget(self.clear_button)
        
        # 添加复位按钮
        self.reset_view_button = QPushButton("复位视图")
        self.reset_view_button.clicked.connect(self.reset_view)
        left_layout.addWidget(self.reset_view_button)
        
        left_layout.addStretch(1)
        
        # 创建右侧的绘图区域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setAspectLocked(True, 1.0)  # 保持1:1的横纵比例
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground('w')  # 白色背景
        
        # 确保ViewBox也保持正方形
        view_box = self.plot_widget.getViewBox()
        view_box.setAspectLocked(True, 1.0)
        view_box.setDefaultPadding(0.1)  # 添加一些边距
        
        # 设置坐标轴范围
        self.plot_widget.setXRange(-self.detector_size/2, self.detector_size/2)
        self.plot_widget.setYRange(-self.detector_size/2, self.detector_size/2)
        
        # 添加轨迹和激光点
        valid_pen = pg.mkPen(color='b', width=self.pen_width)
        invalid_pen = pg.mkPen(color='r', width=self.pen_width)
        self.valid_trajectory_curve = self.plot_widget.plot([], [], pen=valid_pen)
        self.invalid_trajectory_curve = self.plot_widget.plot([], [], pen=invalid_pen)
        
        # 添加激光点
        self.spot = self.plot_widget.plot([], [], pen=None, symbol='o', symbolSize=10, symbolBrush='y')
        
        # 添加十字线
        self.vertical_line = pg.InfiniteLine(angle=90, movable=False, pen='k')
        self.horizontal_line = pg.InfiniteLine(angle=0, movable=False, pen='k')
        self.plot_widget.addItem(self.vertical_line)
        self.plot_widget.addItem(self.horizontal_line)
        
        # 添加死区线
        self.dead_zone_lines = []
        half_dead = self.dead_zone / 2
        
        # 左侧死区线
        left_line = pg.InfiniteLine(angle=90, pos=-half_dead, movable=False, pen=pg.mkPen('r', style=Qt.DashLine))
        self.plot_widget.addItem(left_line)
        self.dead_zone_lines.append(left_line)
        
        # 右侧死区线
        right_line = pg.InfiniteLine(angle=90, pos=half_dead, movable=False, pen=pg.mkPen('r', style=Qt.DashLine))
        self.plot_widget.addItem(right_line)
        self.dead_zone_lines.append(right_line)
        
        # 上侧死区线
        top_line = pg.InfiniteLine(angle=0, pos=half_dead, movable=False, pen=pg.mkPen('r', style=Qt.DashLine))
        self.plot_widget.addItem(top_line)
        self.dead_zone_lines.append(top_line)
        
        # 下侧死区线
        bottom_line = pg.InfiniteLine(angle=0, pos=-half_dead, movable=False, pen=pg.mkPen('r', style=Qt.DashLine))
        self.plot_widget.addItem(bottom_line)
        self.dead_zone_lines.append(bottom_line)
        
        # 添加探测器边界框 - 让边界更加清晰可见
        detector_rect = pg.QtWidgets.QGraphicsRectItem(
            -self.detector_size/2,  # 左上角x坐标
            -self.detector_size/2,  # 左上角y坐标
            self.detector_size,     # 宽度
            self.detector_size      # 高度
        )
        # 使用蓝色虚线作为边界，更加醒目
        detector_rect.setPen(pg.mkPen(color='b', width=2, style=Qt.SolidLine))
        self.plot_widget.addItem(detector_rect)
        
        # 添加鼠标移动事件处理
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)
        
        # 修改比例为1:2，给图表区域更多空间
        layout.addWidget(left_widget, 1)  # 1份空间给左侧面板
        layout.addWidget(self.plot_widget, 2)  # 2份空间给图表区域
        
        self.setWidget(main_widget)
        self.resize(900, 600)
    
    def start_reading_thread(self, ai_task):
        """启动数据读取线程"""
        self.ai_task = ai_task
        
        # 添加任务有效性验证
        if self.ai_task is None:
            logging.error("无法启动读取线程：传入的任务对象为空")
            return
        
        # 验证任务是否有效
        try:
            # 尝试获取任务的基本信息来验证其有效性
            task_name = self.ai_task.name if hasattr(self.ai_task, 'name') else "未知任务"
            logging.info(f"启动四象限探测器 {self.detector_name} 的数据读取线程，任务名称: {task_name}")
            
            # 验证通道信息是否可用
            if not hasattr(self.ai_task, 'channels') or not hasattr(self.ai_task.channels, 'channel_names'):
                logging.error(f"任务 {task_name} 缺少通道信息，无法获取通道名称")
                return
                
            # 记录可用的通道名称用于调试
            available_channels = self.ai_task.channels.channel_names
            logging.info(f"任务中可用的通道: {available_channels}")
            
            # 验证所需通道是否存在
            missing_channels = []
            for ch in self.channels:
                if ch not in available_channels:
                    missing_channels.append(ch)
            
            if missing_channels:
                logging.error(f"以下通道在任务中不存在: {missing_channels}")
                return
                
        except Exception as e:
            logging.error(f"验证任务时出错: {str(e)}")
            return
        
        if not self.reading:
            self.reading = True
            self.start_time = time.time()
            self.reading_thread = threading.Thread(target=self.read_data)
            self.reading_thread.daemon = True
            self.reading_thread.start()
    
    def read_data(self):
        """在单独线程中读取数据并放入队列"""
        channel_indices = []
        
        try:
            # 获取通道索引
            if hasattr(self.ai_task, 'channels') and hasattr(self.ai_task.channels, 'channel_names'):
                available_channels = self.ai_task.channels.channel_names
                logging.info(f"读取线程中可用通道: {available_channels}")
                
                for ch in self.channels:
                    found = False
                    for i, ch_name in enumerate(available_channels):
                        if ch_name == ch:
                            channel_indices.append(i)
                            found = True
                            break
                    if not found:
                        logging.error(f"无法找到通道 {ch} 的索引")
            
            if len(channel_indices) != 4:
                logging.error(f"未能找到所有四个通道的索引，仅找到 {len(channel_indices)} 个: {channel_indices}")
                self.reading = False
                return
            
            logging.info(f"成功获取通道索引: {channel_indices}")
            
            while self.reading and self.ai_task is not None:
                try:
                    # 读取数据
                    data = self.ai_task.read(number_of_samples_per_channel=1)
                    
                    # 获取四个通道的电压
                    v1 = data[channel_indices[0]][0] if isinstance(data[channel_indices[0]], (list, tuple, np.ndarray)) else data[channel_indices[0]]
                    v2 = data[channel_indices[1]][0] if isinstance(data[channel_indices[1]], (list, tuple, np.ndarray)) else data[channel_indices[1]]
                    v3 = data[channel_indices[2]][0] if isinstance(data[channel_indices[2]], (list, tuple, np.ndarray)) else data[channel_indices[2]]
                    v4 = data[channel_indices[3]][0] if isinstance(data[channel_indices[3]], (list, tuple, np.ndarray)) else data[channel_indices[3]]
                    
                    # 计算当前时间，考虑时间偏移量
                    if self.start_time is None:
                        self.start_time = time.time()
                        
                    current_time = time.time() - self.start_time + self.time_offset
                    self.last_timestamp = current_time  # 记录最后的时间戳
                    
                    # 将数据放入队列
                    self.data_queue.put((current_time, v1, v2, v3, v4))
                    
                except Exception as e:
                    logging.error(f"读取四象限数据出错: {str(e)}")
                    # 如果是任务无效错误，退出循环
                    if "invalid" in str(e).lower() or "does not exist" in str(e).lower():
                        logging.error("检测到任务无效错误，停止读取线程")
                        self.reading = False
                        break
                    time.sleep(0.05)
        except Exception as e:
            logging.error(f"读取线程初始化失败: {str(e)}")
            self.reading = False
    
    def update_plot(self):
        """更新图表数据"""
        # 批量处理队列中的数据
        data_processed = False
        max_process = 100
        
        for _ in range(min(max_process, self.data_queue.qsize())):
            if self.data_queue.empty():
                break
            
            data_processed = True
            current_time, v1, v2, v3, v4 = self.data_queue.get()
            
            # 保存电压数据
            self.voltage_time.append(current_time)
            self.voltage_data[0].append(v1)
            self.voltage_data[1].append(v2)
            self.voltage_data[2].append(v3)
            self.voltage_data[3].append(v4)
            
            # 计算总电压
            self.intensity = v1 + v2 + v3 + v4
            
            # 判断位置是否有效
            self.valid_position = all(v >= self.voltage_threshold for v in [v1, v2, v3, v4])
            
            # 计算位置
            if self.intensity != 0:
                # 计算归一化坐标
                x = (v1 + v4 - v2 - v3) / self.intensity
                y = (v1 + v2 - v3 - v4) / self.intensity
                
                # 转换为实际单位(mm)
                x_mm = (x * self.detector_size) / 2.0
                y_mm = (y * self.detector_size) / 2.0
                
                self.position = (x_mm, y_mm)
                
                # 计算相对高度
                self.relative_height = self.intensity
                
                # 保存轨迹数据
                if self.valid_position:
                    self.valid_x_data.append(x_mm)
                    self.valid_y_data.append(y_mm)
                else:
                    self.invalid_x_data.append(x_mm)
                    self.invalid_y_data.append(y_mm)
            else:
                self.position = (0.0, 0.0)
                self.relative_height = 0.0
            
            # 更新界面显示
            self.update_gui_elements(v1, v2, v3, v4)
          # 更新图表
        if data_processed:
            self.update_trajectory_plot()
    
    def update_gui_elements(self, v1, v2, v3, v4):
        """更新界面元素"""
        # 更新电压标签
        quadrant_names = ["右上", "左上", "左下", "右下"]
        for i, v in enumerate([v1, v2, v3, v4]):
            self.voltage_labels[i].setText(f"电压 {i+1} ({self.channels[i]}) [{quadrant_names[i]}]: {v:.3f} V")
        
        # 更新总电压、位置和高度标签
        self.intensity_label.setText(f"总电压 (Z): {self.intensity:.3f} V")
        x_mm, y_mm = self.position
        self.position_label.setText(f"位置: ({x_mm:.2f}, {y_mm:.2f}) mm")
        self.height_label.setText(f"相对高度: {self.relative_height:.2f} μm")
        
        # 更新位置有效性标签
        if self.valid_position:
            self.validity_label.setText("位置有效")
            self.validity_label.setStyleSheet("color: green")
            self.spot.setBrush(pg.mkBrush('y'))
        else:
            self.validity_label.setText("位置无效")
            self.validity_label.setStyleSheet("color: red")
            self.spot.setBrush(pg.mkBrush('r'))
    
    def update_trajectory_plot(self):
        """更新轨迹图"""
        # 更新轨迹曲线
        valid_x = list(self.valid_x_data)
        valid_y = list(self.valid_y_data)
        invalid_x = list(self.invalid_x_data)
        invalid_y = list(self.invalid_y_data)
        
        if self.trajectory_checkbox.isChecked():
            self.valid_trajectory_curve.setData(valid_x, valid_y)
            self.invalid_trajectory_curve.setData(invalid_x, invalid_y)
        else:
            self.valid_trajectory_curve.setData([], [])
            self.invalid_trajectory_curve.setData([], [])
        
        # 更新激光点位置
        x_mm, y_mm = self.position
        self.spot.setData([x_mm], [y_mm])
    
    def toggle_trajectory(self, state):
        """切换是否显示轨迹"""
        self.update_trajectory_plot()
    
    def clear_trajectory(self):
        """清除轨迹数据"""
        self.valid_x_data.clear()
        self.valid_y_data.clear()
        self.invalid_x_data.clear()
        self.invalid_y_data.clear()
        self.update_trajectory_plot()
    
    def mouse_moved(self, evt):
        """处理鼠标移动，显示坐标"""
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.getPlotItem().vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()
            # 可以显示坐标
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        self.reading = False
        if self.reading_thread and self.reading_thread.is_alive():
            self.reading_thread.join(timeout=0.5)
        super().closeEvent(event)
    
    def update_settings(self, detector_name, detector_size, dead_zone=None, pen_width=None, channels=None):
        """更新探测器配置"""
        # 更新名称和尺寸
        self.detector_name = detector_name
        self.detector_size = detector_size
        self.setWindowTitle(f"四象限探测器 - {detector_name}")
        
        # 如果通道列表发生变化，需要更新通道并重启读取线程
        channels_changed = False
        if channels is not None and channels != self.channels:
            # 停止当前读取线程
            old_reading_state = self.reading
            self.reading = False
            if hasattr(self, 'reading_thread') and self.reading_thread:
                try:
                    self.reading_thread.join(timeout=0.2)
                except:
                    pass
            
            # 更新通道配置
            self.channels = channels
              # 更新通道标签
            quadrant_names = ["右上", "左上", "左下", "右下"]
            for i, ch in enumerate(self.channels):
                if i < len(self.voltage_labels):
                    self.voltage_labels[i].setText(f"电压 {i+1} ({ch}) [{quadrant_names[i]}]: 0.000 V")
            
            # 如果之前在读取，则重新启动读取线程
            if hasattr(self, 'ai_task') and self.ai_task is not None and old_reading_state:
                self.reading = False  # 确保停止
                self.start_reading_thread(self.ai_task)
            
            # 清空数据队列
            while not self.data_queue.empty():
                self.data_queue.get()
                
            # 设置标志以通知属性已更改
            channels_changed = True
        
        # 更新其他参数（如果提供）
        if dead_zone is not None:
            self.dead_zone = dead_zone
            # 更新死区线位置
            half_dead = self.dead_zone / 2
            self.dead_zone_lines[0].setValue(-half_dead)  # 左侧
            self.dead_zone_lines[1].setValue(half_dead)   # 右侧
            self.dead_zone_lines[2].setValue(half_dead)   # 上侧
            self.dead_zone_lines[3].setValue(-half_dead)  # 下侧
            
        if pen_width is not None:
            self.pen_width = pen_width
            self.valid_trajectory_curve.setPen(pg.mkPen('b', width=pen_width))
            self.invalid_trajectory_curve.setPen(pg.mkPen('r', width=pen_width))
            
        # 更新图表标题
        self.plot_widget.setTitle(f"四象限探测器 - {self.detector_name}")
        
        # 更新探测器边界框
        for item in self.plot_widget.items():
            if isinstance(item, pg.QtWidgets.QGraphicsRectItem):
                self.plot_widget.removeItem(item)
        
        # 重新创建探测器边界框
        detector_rect = pg.QtWidgets.QGraphicsRectItem(
            -self.detector_size/2,  # 左上角x坐标
            -self.detector_size/2,  # 左上角y坐标
            self.detector_size,     # 宽度
            self.detector_size      # 高度
        )
        detector_rect.setPen(pg.mkPen(color='b', width=2, style=Qt.SolidLine))
        self.plot_widget.addItem(detector_rect)
        
        # 更新坐标轴范围
        self.plot_widget.setXRange(-self.detector_size/2, self.detector_size/2)
        self.plot_widget.setYRange(-self.detector_size/2, self.detector_size/2)
        
        # 如果通道或尺寸发生变更，可能需要清除轨迹
        if channels_changed or dead_zone is not None:
            self.clear_trajectory()
    
    def reset_view(self):
        """重置图表视图到默认状态"""
        self.plot_widget.setXRange(-self.detector_size/2, self.detector_size/2)
        self.plot_widget.setYRange(-self.detector_size/2, self.detector_size/2)
        self.plot_widget.getViewBox().setAspectLocked(True, 1.0)
        
        # 更新十字线位置
        self.vertical_line.setValue(0)
        self.horizontal_line.setValue(0)

    def resizeEvent(self, event):
        """处理窗口大小变化事件，确保图表保持正方形"""
        super().resizeEvent(event)
        # 确保在调整大小后仍然保持纵横比
        if hasattr(self, 'plot_widget'):
            self.plot_widget.getViewBox().setAspectLocked(True, 1.0)
            # 更新坐标轴范围，确保显示完整
            self.plot_widget.setXRange(-self.detector_size/2, self.detector_size/2)
            self.plot_widget.setYRange(-self.detector_size/2, self.detector_size/2)
