from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit, 
    QListWidget, QPushButton, QDialogButtonBox, QToolButton
)
from PyQt5.QtCore import Qt

class ExpressionChartDialog(QDialog):
    def __init__(self, parent=None, channels=None, mode="模拟输入", 
                 chart_name=None, expression=None, channel_aliases=None):
        super().__init__(parent)
        self.channels = channels or []
        self.mode = mode
        self.setWindowTitle("创建表达式图表")
        self.resize(800, 600)
        
        # 保存传入的初始值，用于编辑模式
        self.init_chart_name = chart_name
        self.init_expression = expression
        self.init_channel_aliases = channel_aliases
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 上部：表达式编辑区
        top_group = QGroupBox("表达式编辑器")
        top_layout = QGridLayout()
        
        # 表达式名称
        name_label = QLabel("图表名称:")
        self.name_edit = QLineEdit(self.init_chart_name or "表达式图表")
        top_layout.addWidget(name_label, 0, 0)
        top_layout.addWidget(self.name_edit, 0, 1, 1, 2)
        
        # 表达式输入
        expr_label = QLabel("表达式:")
        self.expr_edit = QLineEdit(self.init_expression or "")
        self.expr_edit.setPlaceholderText("输入数学表达式, 示例: 2*ch1 + sin(ch2)")
        top_layout.addWidget(expr_label, 1, 0)
        top_layout.addWidget(self.expr_edit, 1, 1, 1, 2)
        
        top_group.setLayout(top_layout)
        layout.addWidget(top_group)
        
        # 中部：通道选择与插入
        middle_layout = QHBoxLayout()
        
        # 左侧：可用通道列表
        channel_group = QGroupBox("可用通道")
        channel_layout = QVBoxLayout()
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.SingleSelection)
        channel_layout.addWidget(self.channel_list)
        
        # 添加插入通道按钮
        insert_channel_btn = QPushButton("插入所选通道")
        insert_channel_btn.clicked.connect(self.insert_channel)
        channel_layout.addWidget(insert_channel_btn)
        
        channel_group.setLayout(channel_layout)
        middle_layout.addWidget(channel_group)
        
        # 右侧：常用操作符
        operators_group = QGroupBox("常用操作符")
        operators_layout = QVBoxLayout()
        
        # 操作符按钮网格
        operators_grid = QGridLayout()
        operators = ['+', '-', '*', '/', '(', ')', ',', '=']
        functions = ['sin', 'cos', 'sqrt', 'abs', 'log', 'exp', 'pi']
        
        # 添加操作符按钮
        row = 0
        col = 0
        for op in operators:
            btn = QToolButton()
            btn.setText(op)
            btn.clicked.connect(lambda checked, o=op: self.insert_operator(o))
            operators_grid.addWidget(btn, row, col)
            col += 1
            if col > 3:  # 每行4个按钮
                col = 0
                row += 1
        
        # 添加函数按钮
        row += 1
        col = 0
        for func in functions:
            btn = QToolButton()
            btn.setText(func)
            btn.clicked.connect(lambda checked, f=func: self.insert_operator(f + '()'))
            operators_grid.addWidget(btn, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        operators_layout.addLayout(operators_grid)
        operators_group.setLayout(operators_layout)
        middle_layout.addWidget(operators_group)
        
        layout.addLayout(middle_layout)
        
        # 底部：功能按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 填充通道列表
        self.populate_channels()
    
    def populate_channels(self):
        """填充可用通道列表，并分配别名"""
        # 如果有初始别名，使用它
        if self.init_channel_aliases:
            self.channel_aliases = self.init_channel_aliases.copy()
            
            # 添加显示项到列表中
            for alias, channel in self.channel_aliases.items():
                self.channel_list.addItem(f"{alias}: {channel}")
        else:
            # 否则创建新的别名映射
            self.channel_aliases = {}
            
            for i, channel in enumerate(self.channels):
                alias = f"ch{i+1}"
                self.channel_aliases[alias] = channel
                self.channel_list.addItem(f"{alias}: {channel}")
    
    def insert_channel(self):
        """将选中的通道插入到表达式中"""
        current_item = self.channel_list.currentItem()
        if current_item:
            text = current_item.text()
            alias = text.split(":")[0].strip()
            
            # 在光标位置插入别名
            cursor_pos = self.expr_edit.cursorPosition()
            current_text = self.expr_edit.text()
            new_text = current_text[:cursor_pos] + alias + current_text[cursor_pos:]
            self.expr_edit.setText(new_text)
            self.expr_edit.setFocus()
            self.expr_edit.setCursorPosition(cursor_pos + len(alias))
    
    def insert_operator(self, op):
        """将操作符插入到表达式中"""
        # 在光标位置插入操作符
        cursor_pos = self.expr_edit.cursorPosition()
        current_text = self.expr_edit.text()
        new_text = current_text[:cursor_pos] + op + current_text[cursor_pos:]
        self.expr_edit.setText(new_text)
        self.expr_edit.setFocus()
        
        # 如果是函数，将光标放在括号内
        if '()' in op:
            self.expr_edit.setCursorPosition(cursor_pos + len(op) - 1)
        else:
            self.expr_edit.setCursorPosition(cursor_pos + len(op))
    
    def validate_and_accept(self):
        """验证表达式并接受对话框"""
        from PyQt5.QtWidgets import QMessageBox
        
        expr = self.expr_edit.text()
        if not expr:
            QMessageBox.warning(self, "错误", "表达式不能为空")
            return
            
        try:
            # 验证表达式语法（使用简化测试）
            test_values = {alias: 1.0 for alias in self.channel_aliases.keys()}
            result = self.evaluate_expression(expr, test_values)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "表达式错误", f"表达式语法错误: {str(e)}")
    
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
    
    def get_chart_config(self):
        """获取图表配置"""
        return {
            "name": self.name_edit.text(),
            "expression": self.expr_edit.text(),
            "channel_aliases": self.channel_aliases,
            "type": "expression_chart"
        }
