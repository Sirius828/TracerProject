from PyQt5.QtWidgets import QLabel, QPushButton, QComboBox, QHBoxLayout
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

from windows.quadrant_detector_window import QuadrantDetectorWindow

class CSVQuadrantDetectorWindow(QuadrantDetectorWindow):
    """从CSV数据创建的四象限探测器窗口"""
    def __init__(self, channels, detector_name, csv_data, csv_time, detector_size=10.0, dead_zone=0.5, pen_width=2, parent=None):
        super().__init__(channels, detector_name, detector_size, dead_zone, pen_width, parent)
        self.csv_data = csv_data       # CSV数据的字典 {channel_name: data_series}
        self.csv_time = csv_time       # CSV的时间数据
        self.current_index = 0         # 当前处理到的数据索引
        self.is_playing = False        # 是否正在播放
        self.playback_speed = 1.0      # 播放速度倍率
        
        # 移除原有的reading_thread和start_reading_thread逻辑，改为使用定时器
        if hasattr(self, 'reading_thread'):
            delattr(self, 'reading_thread')
        
        # 添加控制按钮
        self.add_csv_control_buttons()
        
        # 替换update_timer的功能
        self.update_timer.timeout.connect(self.update_csv_plot)
        
    def add_csv_control_buttons(self):
        """添加CSV控制按钮"""
        # 在左侧面板添加按钮
        control_layout = QHBoxLayout()
        
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_button)
        
        self.reset_button = QPushButton("重置")
        self.reset_button.clicked.connect(self.reset_playback)
        control_layout.addWidget(self.reset_button)
        
        # 速度控制
        speed_label = QLabel("速度:")
        control_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "5x", "10x"])
        self.speed_combo.setCurrentIndex(2)  # 默认1x
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        control_layout.addWidget(self.speed_combo)
        
        # 将控制区域添加到左侧面板
        left_widget = self.widget().layout().itemAt(0).widget()
        left_layout = left_widget.layout()
        left_layout.insertLayout(left_layout.count() - 1, control_layout)
        
    def toggle_play(self):
        """切换播放/暂停状态"""
        # 修复播放机制：如果当前索引已到末尾，重置为开始位置
        if self.current_index >= len(self.csv_time) - 1:
            self.current_index = 0
            self.clear_trajectory()
            
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_button.setText("暂停")
        else:
            self.play_button.setText("播放")
            
    def reset_playback(self):
        """重置回放到开始位置"""
        self.current_index = 0
        self.clear_trajectory()
        
    def change_speed(self, speed_text):
        """改变回放速度"""
        speed_value = float(speed_text.strip('x'))
        self.playback_speed = speed_value
        
    def update_csv_plot(self):
        """更新CSV数据的图表"""
        if not self.is_playing or self.current_index >= len(self.csv_time) - 1:
            return
            
        # 计算步进，基于播放速度
        step = max(1, int(self.playback_speed * 5))
        end_index = min(self.current_index + step, len(self.csv_time) - 1)
        
        for i in range(self.current_index, end_index):
            # 从CSV数据中获取电压值
            v1 = self.csv_data[self.channels[0]][i] if len(self.channels) > 0 and self.channels[0] in self.csv_data else 0
            v2 = self.csv_data[self.channels[1]][i] if len(self.channels) > 1 and self.channels[1] in self.csv_data else 0
            v3 = self.csv_data[self.channels[2]][i] if len(self.channels) > 2 and self.channels[2] in self.csv_data else 0
            v4 = self.csv_data[self.channels[3]][i] if len(self.channels) > 3 and self.channels[3] in self.csv_data else 0
            
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
        
        # 更新当前索引
        self.current_index = end_index
        
        # 更新GUI元素
        self.update_gui_elements(v1, v2, v3, v4)
        self.update_trajectory_plot()
        
        # 如果到达结尾，停止播放
        if self.current_index >= len(self.csv_time) - 1:
            self.is_playing = False
            self.play_button.setText("播放")
            
    def closeEvent(self, event):
        """CSV窗口关闭事件处理"""
        self.is_playing = False  # 停止播放
        # 不需要线程清理，因为CSV探测器不使用线程
        super(QuadrantDetectorWindow, self).closeEvent(event)
