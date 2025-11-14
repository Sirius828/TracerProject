from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QComboBox, QDialogButtonBox, QGroupBox, QLineEdit, QPushButton, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QDoubleValidator

from dialogs.advanced_settings_dialog import AdvancedSettingsDialog

class QuadrantDetectorDialog(QDialog):
    """
    四象限探测器配置对话框
    """
    def __init__(self, available_channels, parent=None, existing_config=None, preselected_channels=None):
        super().__init__(parent)
        self.setWindowTitle("配置四象限探测器")
        self.setMinimumWidth(500)
        self.available_channels = available_channels
        self.selected_channels = []
        self.existing_config = existing_config
        self.preselected_channels = preselected_channels or []
        
        # 高级设置参数
        self.pen_width = 2
        
        self.setup_ui()
        
        # 如果是编辑现有配置，则加载配置
        if self.existing_config:
            self.load_existing_config()
        # 如果有预选通道，则自动填充
        elif self.preselected_channels:
            self.auto_fill_preselected_channels()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 顶部说明
        info_label = QLabel("请为四象限探测器选择四个通道，并按照以下顺序：")
        layout.addWidget(info_label)
        
        # 四个区域的描述和选择
        quadrant_layout = QGridLayout()
          # 示意图 - 修正为标准象限顺序
        diagram_label = QLabel()
        diagram_label.setText("""
        +--------+--------+
        |   V2   |   V1   |
        |（左上） | (右上) |
        +--------+--------+
        |   V3   |   V4   |
        |（左下） | (右下) |
        +--------+--------+
        """)
        diagram_label.setFont(QFont("Courier New", 11))
        diagram_label.setFixedHeight(150)
        layout.addWidget(diagram_label)
        
        # 四个通道选择下拉框 - 修正为标准象限顺序
        self.channel_combos = []
        for i, label in enumerate(["V1 (右上)", "V2 (左上)", "V3 (左下)", "V4 (右下)"]):
            row, col = divmod(i, 2)
            quadrant_layout.addWidget(QLabel(label), row, col * 2)
            
            combo = QComboBox()
            combo.addItem("-- 选择通道 --")
            combo.addItems(self.available_channels)
            combo.setCurrentIndex(0)
            combo.currentIndexChanged.connect(lambda idx, combo_index=i: self.on_combo_changed(idx, combo_index))
            self.channel_combos.append(combo)
            quadrant_layout.addWidget(combo, row, col * 2 + 1)
        
        layout.addLayout(quadrant_layout)
        
        # 提示说明文字
        tip_label = QLabel("提示: 如果选择已被其它象限使用的通道，将自动调整选择")
        tip_label.setStyleSheet("color: blue;")
        layout.addWidget(tip_label)
        
        # 基本参数设置
        basic_group = QGroupBox("基本设置")
        basic_layout = QGridLayout(basic_group)
        
        # 探测器名称
        basic_layout.addWidget(QLabel("探测器名称:"), 0, 0)
        self.name_edit = QLineEdit("四象限探测器")
        basic_layout.addWidget(self.name_edit, 0, 1)
        
        # 探测器尺寸
        basic_layout.addWidget(QLabel("探测器尺寸 (mm):"), 1, 0)
        self.size_edit = QLineEdit("10.0")
        self.size_edit.setValidator(QDoubleValidator(0.1, 100.0, 2))
        basic_layout.addWidget(self.size_edit, 1, 1)
        
        # 死区宽度
        basic_layout.addWidget(QLabel("死区宽度 (mm):"), 2, 0)
        self.dead_zone_edit = QLineEdit("0.5")
        self.dead_zone_edit.setValidator(QDoubleValidator(0.0, 10.0, 2))
        basic_layout.addWidget(self.dead_zone_edit, 2, 1)
        
        layout.addWidget(basic_group)
        
        # 高级设置按钮
        adv_layout = QHBoxLayout()
        adv_layout.addStretch()
        self.advanced_button = QPushButton("高级设置...")
        self.advanced_button.clicked.connect(self.show_advanced_settings)
        adv_layout.addWidget(self.advanced_button)
        layout.addLayout(adv_layout)
        
        # 添加分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        layout.addWidget(button_box)
    
    def show_advanced_settings(self):
        """显示高级设置对话框"""
        dialog = AdvancedSettingsDialog(pen_width=self.pen_width, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.pen_width = settings["pen_width"]
    
    def load_existing_config(self):
        """加载现有配置"""
        if not self.existing_config:
            return
            
        # 设置名称和基本参数
        self.name_edit.setText(self.existing_config.get("name", "四象限探测器"))
        self.size_edit.setText(str(self.existing_config.get("detector_size", 10.0)))
        self.dead_zone_edit.setText(str(self.existing_config.get("dead_zone", 0.5)))
        
        # 设置高级参数
        self.pen_width = self.existing_config.get("pen_width", 2)
        
        # 设置通道选择
        channels = self.existing_config.get("channels", [])
        if len(channels) == 4:
            for i, channel in enumerate(channels):
                index = self.channel_combos[i].findText(channel)
                if index >= 0:
                    self.channel_combos[i].setCurrentIndex(index)
        
        # 验证选择
        self.validate_selection()
    
    def on_combo_changed(self, idx, combo_index):
        """当某个下拉框选择变更时调用"""
        current_combo = self.channel_combos[combo_index]
        current_selection = current_combo.currentText()
        
        # 如果选择的是"-- 选择通道 --"，则不处理通道交换
        if (current_selection == "-- 选择通道 --"):
            self.validate_selection()
            return
            
        # 检查是否有其他象限已选择此通道
        for i, other_combo in enumerate(self.channel_combos):
            if (i != combo_index and other_combo.currentText() == current_selection):
                # 找到冲突，需要进行通道交换
                other_combo.blockSignals(True)
                
                # 保存当前被选择的组合框的旧值（即其它组合框要使用的通道）
                old_selection = other_combo.currentText()
                
                # 执行交换：将其它组合框设为当前组合框原来的选择
                # 当前组合框已经设置为用户选择的值，不需要再设置
                other_combo.setCurrentText("-- 选择通道 --")
                
                other_combo.blockSignals(False)
                break
        
        # 验证并更新选择状态
        self.validate_selection()
    
    def validate_selection(self):
        """验证通道选择"""
        selected = []
        for combo in self.channel_combos:
            text = combo.currentText()
            if text != "-- 选择通道 --":
                selected.append(text)
        
        # 检查是否选择了4个不同的通道
        if len(selected) == 4 and len(set(selected)) == 4:
            self.selected_channels = selected
            self.ok_button.setEnabled(True)
        else:
            self.selected_channels = []
            self.ok_button.setEnabled(False)
    
    def auto_fill_preselected_channels(self):
        """自动填充预选的通道"""
        if len(self.preselected_channels) >= 4:
            # 如果预选了4个或更多通道，按顺序填充到四个象限
            for i, channel in enumerate(self.preselected_channels[:4]):
                if channel in self.available_channels:
                    # 找到通道在下拉框中的索引
                    combo = self.channel_combos[i]
                    index = combo.findText(channel)
                    if index >= 0:
                        combo.setCurrentIndex(index)
            
            # 验证并更新选择状态
            self.validate_selection()
        elif len(self.preselected_channels) > 0:
            # 如果预选了1-3个通道，填充前几个象限
            for i, channel in enumerate(self.preselected_channels):
                if i < 4 and channel in self.available_channels:
                    combo = self.channel_combos[i]
                    index = combo.findText(channel)
                    if index >= 0:
                        combo.setCurrentIndex(index)
            
            # 验证并更新选择状态
            self.validate_selection()
    
    def get_detector_config(self):
        """获取探测器配置"""
        return {
            "channels": self.selected_channels,
            "name": self.name_edit.text(),
            "detector_size": float(self.size_edit.text()),
            "dead_zone": float(self.dead_zone_edit.text()),
            "pen_width": self.pen_width,
            "type": "quadrant_detector"
        }
