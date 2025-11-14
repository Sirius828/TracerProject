from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDialogButtonBox

class AdvancedSettingsDialog(QDialog):
    """高级设置对话框"""
    def __init__(self, pen_width=2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级设置")
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        # 画笔粗细设置
        pw_layout = QHBoxLayout()
        pw_label = QLabel("轨迹画笔粗细:")
        self.pw_spinbox = QSpinBox()
        self.pw_spinbox.setRange(1, 10)
        self.pw_spinbox.setValue(pen_width)
        pw_layout.addWidget(pw_label)
        pw_layout.addWidget(self.pw_spinbox)
        
        layout.addLayout(pw_layout)
        
        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_settings(self):
        """获取设置值"""
        return {
            "pen_width": self.pw_spinbox.value()
        }
