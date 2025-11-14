from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                           QListWidgetItem, QDialogButtonBox, QLabel, QPushButton,
                           QLineEdit, QGroupBox, QGridLayout, QTabWidget, QWidget)
from PyQt5.QtCore import Qt
import logging
import os
import json

class AddChannelDialog(QDialog):
    """用于选择要添加的通道的对话框"""
    
    def __init__(self, device_name, parent=None, used_channels=None):
        super().__init__(parent)
        self.device_name = device_name
        self.used_channels = used_channels or set()
        self.selected_channels = []
        self.history_channels = self.load_history_channels()
        
        self.setWindowTitle("添加通道")
        self.resize(500, 550)
        
        self.setup_ui()
        self.populate_channels()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # ===== 标签页1：快速添加 =====
        quick_widget = QWidget()
        quick_layout = QVBoxLayout(quick_widget)
        
        # 快速添加组
        quick_group = QGroupBox("快速添加")
        quick_inner_layout = QGridLayout()
        
        # 设备名称（只读）
        device_label = QLabel("设备名称:")
        self.device_edit = QLineEdit(self.device_name)
        self.device_edit.setReadOnly(True)
        quick_inner_layout.addWidget(device_label, 0, 0)
        quick_inner_layout.addWidget(self.device_edit, 0, 1)
        
        # 通道序号输入
        channel_label = QLabel("通道序号:")
        self.channel_number_edit = QLineEdit()
        self.channel_number_edit.setPlaceholderText("输入序号，如: 0,1,2,3")
        quick_inner_layout.addWidget(channel_label, 1, 0)
        quick_inner_layout.addWidget(self.channel_number_edit, 1, 1)
        
        # 添加按钮
        add_btn = QPushButton("添加到选择列表")
        add_btn.clicked.connect(self.add_custom_channels)
        quick_inner_layout.addWidget(add_btn, 2, 1)
        
        # 说明标签
        tip_label = QLabel("提示: 可以输入单个序号如'0'，或用逗号分隔多个序号如'0,1,2'，或范围如'0-3'")
        tip_label.setWordWrap(True)
        quick_inner_layout.addWidget(tip_label, 3, 0, 1, 2)
        
        quick_group.setLayout(quick_inner_layout)
        quick_layout.addWidget(quick_group)
        
        # 历史记录组
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout()
        
        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.history_list.itemDoubleClicked.connect(self.add_from_history)
        
        history_btn_layout = QHBoxLayout()
        add_history_btn = QPushButton("添加所选")
        add_history_btn.clicked.connect(self.add_selected_history)
        clear_history_btn = QPushButton("清空历史")
        clear_history_btn.clicked.connect(self.clear_history)
        
        history_btn_layout.addWidget(add_history_btn)
        history_btn_layout.addWidget(clear_history_btn)
        
        history_layout.addWidget(self.history_list)
        history_layout.addLayout(history_btn_layout)
        
        history_group.setLayout(history_layout)
        quick_layout.addWidget(history_group)
        
        # ===== 标签页2：预设通道 =====
        preset_widget = QWidget()
        preset_layout = QVBoxLayout(preset_widget)
        
        preset_label = QLabel("选择预设通道:")
        preset_layout.addWidget(preset_label)
        
        # 预设通道列表
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.ExtendedSelection)
        preset_layout.addWidget(self.channel_list)
        
        # 添加标签页
        tab_widget.addTab(quick_widget, "快速添加")
        tab_widget.addTab(preset_widget, "预设通道")
        
        # 所选通道组
        selected_group = QGroupBox("已选择的通道")
        selected_layout = QVBoxLayout()
        
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.ExtendedSelection)
        
        remove_btn = QPushButton("移除所选")
        remove_btn.clicked.connect(self.remove_selected)
        
        selected_layout.addWidget(self.selected_list)
        selected_layout.addWidget(remove_btn)
        
        selected_group.setLayout(selected_layout)
        layout.addWidget(selected_group)
        
        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def populate_channels(self):
        """填充可用通道列表和历史记录"""
        # 填充预设通道列表
        available_channels = self.get_available_channels()
        
        for channel in available_channels:
            item = QListWidgetItem(channel)
            if channel in self.used_channels:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setText(f"{channel} (已使用)")
            self.channel_list.addItem(item)
        
        # 填充历史记录
        for channel in self.history_channels:
            item = QListWidgetItem(channel)
            if channel in self.used_channels:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setText(f"{channel} (已使用)")
            self.history_list.addItem(item)
    
    def get_available_channels(self):
        """获取设备的默认通道列表"""
        # 直接返回常用的模拟输入通道列表
        channels = []
        for i in range(16):  # NI设备通常有0-15的AI通道
            channels.append(f"{self.device_name}/ai{i}")
        return channels
    
    def add_custom_channels(self):
        """从用户输入的通道序号添加通道"""
        input_text = self.channel_number_edit.text().strip()
        if not input_text:
            return
            
        # 解析输入的通道序号
        channel_numbers = []
        
        # 分隔并处理每个部分
        parts = input_text.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:  # 处理范围，如 "0-3"
                try:
                    start, end = part.split('-')
                    start = int(start.strip())
                    end = int(end.strip())
                    channel_numbers.extend(range(start, end + 1))
                except (ValueError, IndexError):
                    logging.warning(f"无法解析通道范围: {part}")
            else:  # 处理单个数字
                try:
                    channel_numbers.append(int(part))
                except ValueError:
                    logging.warning(f"无法解析通道序号: {part}")
        
        # 创建通道名称并添加到已选列表
        for num in channel_numbers:
            channel_name = f"{self.device_name}/ai{num}"
            if channel_name in self.used_channels:
                continue
                
            # 检查是否已经在选择列表中
            already_selected = False
            for i in range(self.selected_list.count()):
                if self.selected_list.item(i).text() == channel_name:
                    already_selected = True
                    break
            
            if not already_selected:
                self.selected_list.addItem(channel_name)
                
                # 添加到历史记录（如果不在）
                if channel_name not in self.history_channels:
                    self.history_channels.append(channel_name)
                    self.history_list.addItem(channel_name)
        
        # 清空输入框
        self.channel_number_edit.clear()
    
    def add_from_history(self, item):
        """从历史记录中添加通道"""
        channel_name = item.text()
        if " (已使用)" in channel_name:
            return
            
        # 检查是否已经在选择列表中
        for i in range(self.selected_list.count()):
            if self.selected_list.item(i).text() == channel_name:
                return
                
        self.selected_list.addItem(channel_name)
    
    def add_selected_history(self):
        """添加所选历史记录项到选择列表"""
        for item in self.history_list.selectedItems():
            channel_name = item.text()
            if " (已使用)" in channel_name:
                continue
                
            # 检查是否已经在选择列表中
            already_selected = False
            for i in range(self.selected_list.count()):
                if self.selected_list.item(i).text() == channel_name:
                    already_selected = True
                    break
                    
            if not already_selected:
                self.selected_list.addItem(channel_name)
    
    def clear_history(self):
        """清空历史记录"""
        self.history_channels = []
        self.history_list.clear()
        self.save_history_channels()
    
    def remove_selected(self):
        """从已选列表中移除所选项"""
        for item in self.selected_list.selectedItems():
            row = self.selected_list.row(item)
            self.selected_list.takeItem(row)
    
    def get_selected_channels(self):
        """获取用户选择的通道列表"""
        selected = []
        
        # 从已选列表中获取
        for i in range(self.selected_list.count()):
            selected.append(self.selected_list.item(i).text())
            
        # 从预设通道列表中获取
        for item in self.channel_list.selectedItems():
            channel_name = item.text()
            if " (已使用)" in channel_name:
                continue
            if channel_name not in selected:
                selected.append(channel_name)
        
        return selected
    
    def accept(self):
        """确认选择"""
        self.selected_channels = self.get_selected_channels()
        
        # 如果有新的通道，添加到历史记录
        updated = False
        for channel in self.selected_channels:
            if channel not in self.history_channels:
                self.history_channels.append(channel)
                updated = True
        
        # 保存历史记录
        if updated:
            self.save_history_channels()
            
        super().accept()
    
    def load_history_channels(self):
        """加载历史通道记录"""
        try:
            config_path = os.path.join(os.path.expanduser("~"), "userdata", "channel_history.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("channels", [])
        except Exception as e:
            logging.error(f"加载通道历史记录出错: {str(e)}")
        return []
    
    def save_history_channels(self):
        """保存历史通道记录"""
        try:
            config_dir = os.path.join(os.path.expanduser("~"), "userdata")
            os.makedirs(config_dir, exist_ok=True)
            
            config_path = os.path.join(config_dir, "channel_history.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"channels": self.history_channels}, f, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存通道历史记录出错: {str(e)}")
