from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QCheckBox, QLineEdit, QComboBox, QDialogButtonBox
from PyQt5.QtGui import QDoubleValidator

class CSVConfigDialog(QDialog):
    """CSV数据配置对话框，用于设置电压单位和采样频率"""
    def __init__(self, channel_count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV数据配置")
        self.setMinimumWidth(400)
        self.channel_count = channel_count
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 显示文件信息
        info_label = QLabel(f"检测到 {self.channel_count} 个数据列")
        layout.addWidget(info_label)
        
        # 创建表单
        form_layout = QFormLayout()
        
        # 电压单位
        self.voltage_unit_combo = QComboBox()
        self.voltage_unit_combo.addItems(["伏特(V)", "毫伏(mV)", "微伏(μV)"])
        self.voltage_unit_combo.setCurrentIndex(0)
        form_layout.addRow("电压单位:", self.voltage_unit_combo)
        
        # 第一列是否为时间
        self.first_col_time_checkbox = QCheckBox("第一列为时间")
        self.first_col_time_checkbox.setChecked(False)
        self.first_col_time_checkbox.stateChanged.connect(self.toggle_sample_rate_field)
        form_layout.addRow("", self.first_col_time_checkbox)
        
        # 采样频率
        self.sample_rate_edit = QLineEdit("1000.0")
        self.sample_rate_edit.setValidator(QDoubleValidator(1.0, 1000000.0, 1))
        form_layout.addRow("采样频率 (Hz):", self.sample_rate_edit)
        
        # 首行是否为通道名
        self.header_checkbox = QCheckBox("第一行为通道名称")
        self.header_checkbox.setChecked(True)
        form_layout.addRow("", self.header_checkbox)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def toggle_sample_rate_field(self, state):
        """当第一列为时间选项改变时，控制采样率输入框状态"""
        self.sample_rate_edit.setEnabled(not state)
        if state:  # 如果选中"第一列为时间"
            self.sample_rate_edit.setText("自动计算")
    
    def get_config(self):
        """获取配置参数"""
        # 转换电压单位为系数
        voltage_unit_index = self.voltage_unit_combo.currentIndex()
        voltage_scale = 1.0  # 默认为伏特
        if voltage_unit_index == 1:  # 毫伏
            voltage_scale = 0.001
        elif voltage_unit_index == 2:  # 微伏
            voltage_scale = 0.000001
            
        return {
            "voltage_unit": self.voltage_unit_combo.currentText(),
            "voltage_scale": voltage_scale,
            "sample_rate": float(self.sample_rate_edit.text()) if not self.first_col_time_checkbox.isChecked() else None,
            "has_header": self.header_checkbox.isChecked(),
            "first_col_is_time": self.first_col_time_checkbox.isChecked()
        }
