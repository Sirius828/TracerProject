from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QCheckBox, QLineEdit, QComboBox, QDialogButtonBox
from PyQt5.QtGui import QDoubleValidator

class CSVEditConfigDialog(QDialog):
    """CSV数据配置编辑对话框，用于编辑已导入CSV的电压单位和采样频率"""
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑CSV数据配置")
        self.setMinimumWidth(400)
        self.current_config = current_config
        
        self.setup_ui()
        self.load_current_config()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
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
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_current_config(self):
        """加载当前配置"""
        if not self.current_config:
            return
            
        # 设置电压单位
        voltage_unit = self.current_config.get("voltage_unit", "伏特(V)")
        if "毫伏" in voltage_unit:
            self.voltage_unit_combo.setCurrentIndex(1)
        elif "微伏" in voltage_unit:
            self.voltage_unit_combo.setCurrentIndex(2)
        else:
            self.voltage_unit_combo.setCurrentIndex(0)
            
        # 设置第一列是否为时间
        is_time = self.current_config.get("first_col_is_time", False)
        self.first_col_time_checkbox.setChecked(is_time)
        
        # 设置采样频率
        sample_rate = self.current_config.get("sample_rate", 1000.0)
        if sample_rate is not None:
            self.sample_rate_edit.setText(str(sample_rate))
        else:
            self.sample_rate_edit.setText("自动计算")
            self.sample_rate_edit.setEnabled(False)
    
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
        
        # 确定电压单位文本
        voltage_unit = self.voltage_unit_combo.currentText()
        
        # 判断是否使用时间列
        first_col_is_time = self.first_col_time_checkbox.isChecked()
        
        # 获取采样率，如果使用时间列则为None
        sample_rate = None if first_col_is_time else float(self.sample_rate_edit.text())
            
        return {
            "voltage_unit": voltage_unit,
            "voltage_scale": voltage_scale,
            "sample_rate": sample_rate,
            "has_header": self.current_config.get("has_header", True),  # 保留原有设置
            "first_col_is_time": first_col_is_time
        }
