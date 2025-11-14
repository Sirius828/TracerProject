# 电压单位转换功能修复报告

## 问题概述
用户报告 Tracer 电压监控应用中的动态电压单位转换功能不工作。虽然软件可以记住更改的电压单位（在右键属性中可见），但图表不会更新以反映新单位 - 无论是在实时操作、重新打开图表时，还是在停止和重新启动数据采集后。

## 根本原因分析

经过深入调试，发现了两个关键问题：

### 1. 属性名称不一致
在 `tracer.py` 的 `update_expression_voltage_unit` 方法中，代码查找 `widget.chart_name` 属性：
```python
if hasattr(widget, 'chart_name') and widget.chart_name == expression_name:
```

但实际上表达式图表窗口使用的是 `name` 属性：
- `ExpressionChartWindow.name`
- `CSVExpressionChartWindow.name`

### 2. QMdiSubWindow 结构处理不当
通道图表窗口继承自 `QMdiSubWindow`：
- `ChannelChartWindow(QMdiSubWindow)`
- `CSVChannelChartWindow(QMdiSubWindow)`

而表达式图表窗口继承自 `QMainWindow`：
- `ExpressionChartWindow(QMainWindow)`
- `CSVExpressionChartWindow(QMainWindow)`

在 `update_channel_voltage_unit` 方法中，代码只检查 `window.widget()`，对于 `QMdiSubWindow` 类型，这返回的是内部的 widget 而不是窗口本身，导致无法找到通道图表窗口。

## 修复方案

### 修复 1: 更正属性名称
将 `update_expression_voltage_unit` 方法中的 `chart_name` 更正为 `name`：

```python
def update_expression_voltage_unit(self, expression_name, new_unit):
    """更新表达式图表窗口的电压单位"""
    for window in self.mdi_area.subWindowList():
        widget = window.widget()
        # 更新表达式图表窗口
        if isinstance(widget, (ExpressionChartWindow, CSVExpressionChartWindow)):
            if hasattr(widget, 'name') and widget.name == expression_name:  # 修复：chart_name -> name
                if hasattr(widget, 'set_voltage_unit'):
                    widget.set_voltage_unit(new_unit)
```

### 修复 2: 正确处理 QMdiSubWindow 结构
修改 `update_channel_voltage_unit` 方法，同时检查窗口本身和内部 widget：

```python
def update_channel_voltage_unit(self, channel_name, new_unit):
    """更新通道图表窗口的电压单位"""
    for window in self.mdi_area.subWindowList():
        widget = window.widget()
        # 对于 QMdiSubWindow 类型，检查窗口本身而不是内部widget
        if isinstance(window, (ChannelChartWindow, CSVChannelChartWindow)):
            if hasattr(window, 'channel_name') and window.channel_name == channel_name:
                if hasattr(window, 'set_voltage_unit'):
                    window.set_voltage_unit(new_unit)
        # 也检查widget，以防有其他类型的窗口
        elif isinstance(widget, (ChannelChartWindow, CSVChannelChartWindow)):
            if hasattr(widget, 'channel_name') and widget.channel_name == channel_name:
                if hasattr(widget, 'set_voltage_unit'):
                    widget.set_voltage_unit(new_unit)
```

## 修复文件

### 主要修改文件
- `c:\Users\17106\Desktop\pythonProject\tracer.py`
  - 修复了 `update_channel_voltage_unit` 方法
  - 修复了 `update_expression_voltage_unit` 方法

## 测试验证

创建了多个测试脚本来验证修复：

### 1. 基础功能测试 (`test_voltage_unit_debug.py`)
- ✅ 验证模块导入正常
- ✅ 验证图表窗口创建正常  
- ✅ 验证 `set_voltage_unit` 方法存在且工作正常

### 2. 集成测试 (`test_voltage_real.py`)
- ✅ 验证真实 MDI 结构下的单位转换
- ✅ 验证所有4种图表窗口类型的单位转换

### 3. 完整应用测试 (`test_tracer_final.py`)
- ✅ 验证真实 Tracer 应用程序中的单位转换功能
- ✅ 验证主窗口方法正确调用图表窗口的更新方法

## 修复结果

### ✅ 已修复的功能
1. **通道图表窗口电压单位转换** - 正常工作
2. **CSV通道图表窗口电压单位转换** - 正常工作  
3. **表达式图表窗口电压单位转换** - 正常工作
4. **CSV表达式图表窗口电压单位转换** - 正常工作

### ✅ 支持的单位
- **V (伏特)**: 基准单位，缩放系数 = 1.0
- **mV (毫伏)**: 缩放系数 = 1000.0
- **uV (微伏)**: 缩放系数 = 1000000.0

### ✅ 验证的功能特性
- ✅ 历史数据正确重新缩放
- ✅ 界面标签即时更新 
- ✅ 图表坐标轴单位更新
- ✅ 数值显示使用新单位
- ✅ 实时数据使用新单位
- ✅ 正确处理不同窗口结构（QMdiSubWindow vs QMainWindow）

## 使用方法

用户现在可以：
1. 右键点击侧栏中的通道或表达式项目
2. 选择"属性设置"
3. 在对话框中选择新的电压单位（V、mV、uV）
4. 点击确定后，所有相关的打开图表窗口将立即更新：
   - 图表坐标轴标签更新
   - 历史数据重新缩放
   - 当前数值显示更新
   - 后续实时数据使用新单位

## 技术要点

### 关键修复点
1. **属性名称统一**: 确保主窗口更新方法使用正确的属性名
2. **窗口结构处理**: 正确处理 QMdiSubWindow 和 QMainWindow 的不同结构
3. **类型检查**: 使用 `isinstance()` 正确识别窗口类型
4. **双重检查**: 同时检查窗口本身和内部 widget 以确保兼容性

### 架构设计
- **统一接口**: 所有图表窗口都实现 `set_voltage_unit(unit)` 方法
- **数据保真**: 原始数据精度在转换过程中完整保持
- **性能优化**: 转换算法高效，支持大量历史数据
- **错误处理**: 无效单位转换请求被安全忽略

## 总结

电压单位转换功能现已完全修复并正常工作。用户可以在应用运行或停止时任意时刻更改电压单位，所有图表会立即更新显示正确的电压值和单位标识。此修复解决了之前报告的所有问题，包括实时操作、重新打开图表和重启数据采集后的单位同步问题。

## 日期
2025年6月12日
