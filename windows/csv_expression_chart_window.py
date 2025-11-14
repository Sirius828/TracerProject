import numpy as np
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QLabel, QHBoxLayout, QMenu, QAction, QMessageBox, QDialog, QComboBox, QDialogButtonBox, QFormLayout
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class CSVExpressionChartWindow(QMainWindow):
    def __init__(self, name, expression, channel_aliases, csv_id, csv_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(name)
        self.name = name
        self.expression = expression
        self.channel_aliases = channel_aliases
        self.csv_id = csv_id
        self.csv_data = csv_data
        self.voltage_unit = "mV"
        self.voltage_scale = 1000.0
        self.resize(800, 600)
        self.parent_window = parent
        self.init_ui()
        self.plot_data()
    
    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', f"数值 ({self.voltage_unit})")
        self.plot_widget.setLabel('bottom', "时间")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot = self.plot_widget.plot(pen=pg.mkPen(color=(255, 0, 0), width=2))
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.plot_widget)
        expr_layout = QHBoxLayout()
        expr_label = QLabel(f"表达式: {self.expression}")
        expr_layout.addWidget(expr_label)
        layout.addLayout(expr_layout)
        self.setCentralWidget(central_widget)
    
    def show_context_menu(self, pos):
        menu = QMenu(self)
        edit_action = QAction("编辑属性", self)
        edit_action.triggered.connect(self.edit_properties)
        menu.addAction(edit_action)
        unit_action = QAction("电压单位设置", self)
        unit_action.triggered.connect(self.show_unit_dialog)
        menu.addAction(unit_action)
        reset_action = QAction("重置视图", self)
        reset_action.triggered.connect(self.reset_view)
        menu.addAction(reset_action)
        menu.exec_(self.plot_widget.mapToGlobal(pos))
    
    def show_unit_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("电压单位设置")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        unit_combo = QComboBox()
        unit_combo.addItems(["V", "mV", "uV"])
        unit_combo.setCurrentText(self.voltage_unit)
        form_layout.addRow("电压单位:", unit_combo)
        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        if dialog.exec_() == QDialog.Accepted:
            new_unit = unit_combo.currentText()
            if new_unit != self.voltage_unit:
                self.set_voltage_unit(new_unit)
    
    def set_voltage_unit(self, unit):
        unit_scales = {"V": 1.0, "mV": 1000.0, "uV": 1000000.0}
        if unit in unit_scales:
            self.voltage_unit = unit
            self.voltage_scale = unit_scales[unit]
            self.plot_widget.setLabel('left', f"数值 ({self.voltage_unit})")
            self.plot_data()
    
    def edit_properties(self):
        QMessageBox.information(self, "提示", "表达式编辑功能开发中...")
    
    def reset_view(self):
        self.plot_widget.enableAutoRange()
    
    def plot_data(self):
        try:
            data = self.csv_data["data"]
            channel_data = {}
            for alias, channel in self.channel_aliases.items():
                if channel in data.columns:
                    channel_data[alias] = data[channel].values
                else:
                    channel_data[alias] = np.zeros(len(data))
            result_data = []
            for i in range(len(data)):
                values = {}
                for alias, channel_values in channel_data.items():
                    values[alias] = float(channel_values[i])
                try:
                    result = self.evaluate_expression(self.expression, values)
                    result_converted = result * self.voltage_scale
                    result_data.append(result_converted)
                except Exception as e:
                    result_data.append(0.0)
            time_data = np.arange(len(data))
            self.plot.setData(time_data, result_data)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"绘制数据时出错: {str(e)}")
    
    def evaluate_expression(self, expr, values):
        from math import sin, cos, tan, log, log10, sqrt, exp, pi
        namespace = {'sin': sin, 'cos': cos, 'tan': tan, 'sqrt': sqrt, 'exp': exp, 'log': log, 'log10': log10, 'pi': pi, 'abs': abs}
        namespace.update(values)
        return eval(expr, {"__builtins__": {}}, namespace)
