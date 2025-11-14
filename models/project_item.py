from PyQt5.QtWidgets import QTreeWidgetItem

class ProjectItem(QTreeWidgetItem):
    """
    继承 QTreeWidgetItem，用于区分通道、图表等类型
    """
    def __init__(self, text, item_type="channel"):
        super().__init__([text])
        self.item_type = item_type  # 'channel', 'chart', 'algorithm' 等
