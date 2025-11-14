from PyQt5.QtWidgets import QMdiSubWindow, QTextEdit

class ChartWindow(QMdiSubWindow):
    """
    示例图表窗口，打开后在 MDI 中显示
    """
    def __init__(self, title="图表窗口"):
        super().__init__()
        self.setWindowTitle(title)
        # 简化处理，用一个文本编辑器代替实际图表
        text_editor = QTextEdit()
        text_editor.setPlainText(f"这里显示 {title} 的可视化内容")
        self.setWidget(text_editor)
