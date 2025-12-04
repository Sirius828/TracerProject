from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtCore import Qt


class ProjectItem(QTreeWidgetItem):
    """继承 QTreeWidgetItem，用于区分通道、图表等类型"""

    def __init__(self, text, item_type="channel"):
        super().__init__([text])
        self.item_type = item_type  # 'channel', 'chart', 'algorithm' 等
        self.display_name = text
        self.physical_name = text if item_type == "channel" else None

        editable_types = {"channel", "expression_chart", "quadrant_detector"}
        if item_type in editable_types:
            self.setFlags(self.flags() | Qt.ItemIsEditable)
