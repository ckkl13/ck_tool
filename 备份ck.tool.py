from maya import cmds
import maya.mel as mel
import re
import math
import os
import sys  # 用于动态添加路径
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                               QColorDialog, QLabel, QGridLayout, QScrollArea, QToolTip, QFrame,
                               QGraphicsOpacityEffect, QListWidget, QListWidgetItem,
                               QGroupBox, QRadioButton, QFileDialog, QTabWidget, QMessageBox,
                               QSizePolicy, QDialog, QSlider, QMenu, QAction)
from PySide2.QtGui import QColor, QPalette, QFont, QPixmap, QPainter, QImage, QCursor, QMovie
from PySide2.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QSize, QRect, QSequentialAnimationGroup
import shiboken2
from maya import OpenMayaUI
from functools import wraps  # 用于装饰器
import importlib
import json
import time
from datetime import datetime

# 导入控制器形状模块
from controllers import controller_shapes


# 导入通用工具模块
def get_script_path():
    try:
        # 首先尝试使用__file__变量（在脚本文件执行时可用）
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # 在Maya控制台中直接执行时，使用Maya的脚本路径
        import inspect
        return os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


sys.path.append(os.path.join(get_script_path(), "tool"))
from common_utils import reload_module


# 辅助函数：加载模块
def load_module(module_name, file_path=None, function_name=None, *args, **kwargs):
    """
    通用模块加载函数，用于导入或重载指定的模块，并可选择性地执行其中的函数

    参数:
        module_name (str): 要导入或重载的模块名称
        file_path (str, 可选): 模块文件的完整路径
        function_name (str, 可选): 要执行的函数名称
        *args, **kwargs: 传递给函数的参数

    返回:
        module: 导入或重载后的模块对象
    """
    try:
        # 使用reload_module函数加载或重载模块
        module = reload_module(module_name, file_path)

        # 如果指定了函数名，则执行该函数
        if function_name and hasattr(module, function_name):
            func = getattr(module, function_name)
            func(*args, **kwargs)
            print(f"已运行 {module_name}.py 中的 {function_name} 函数")
        elif function_name:
            cmds.warning(f"{module_name}.py 中未找到 {function_name} 函数")

        return module
    except Exception as e:
        cmds.warning(f"加载 {module_name}.py 失败: {str(e)}")
        print(f"错误详情: {str(e)}")
        return None


# 动态路径设置
SCRIPT_DIR = get_script_path()
TOOL_DIR = os.path.join(SCRIPT_DIR, "tool")
if TOOL_DIR not in sys.path:
    sys.path.append(TOOL_DIR)

# 确保controllers目录也在路径中
CONTROLLERS_DIR = os.path.join(SCRIPT_DIR, "controllers")
if CONTROLLERS_DIR not in sys.path:
    sys.path.append(CONTROLLERS_DIR)


# 获取 Maya 主窗口作为 PySide2 小部件
def get_maya_main_window():
    main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
    if main_window_ptr is not None:
        return shiboken2.wrapInstance(int(main_window_ptr), QWidget)
    return None


# 确保 PySide2 应用实例存在
if QApplication.instance() is None:
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()


# 全局撤销装饰器
def with_undo_support(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            cmds.undoInfo(openChunk=True)
            result = func(self, *args, **kwargs)
            if func.__name__ not in ["show", "closeEvent"]:
                print(f"'{func.__name__}' 操作完成。按 Ctrl+Z 可撤销此操作。")
            return result
        except Exception as e:
            print(f"'{func.__name__}' 操作出错: {e}")
            raise
        finally:
            cmds.undoInfo(closeChunk=True)

    return wrapper


# 自定义按钮类，带延迟工具提示
class DelayedToolTipButton(QPushButton):
    def __init__(self, text, tooltip_text="", parent=None):
        super().__init__(text, parent)
        
        # 保存工具提示文本，但不立即设置
        self.tooltip_text = tooltip_text
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.showToolTipDelayed)
        
        # 设置工具提示政策
        self.setToolTipDuration(5000)  # 设置工具提示显示5秒
        
        # 找到主窗口以获取字体大小
        self.main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if isinstance(parent_widget, CombinedTool):
                self.main_window = parent_widget
                break
            parent_widget = parent_widget.parent()
        
        # 获取字体大小并应用
        font_size = 11
        if self.main_window and hasattr(self.main_window, 'font_size'):
            font_size = self.main_window.font_size
        
        # 将字体大小应用到按钮
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)

    def enterEvent(self, event):
        self.hover_timer.start(300)  # 设置300毫秒延迟
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def showToolTipDelayed(self):
        """延迟显示工具提示"""
        if not self.underMouse():
            return
            
        # 显示工具提示
        if self.tooltip_text:
            # 获取屏幕上当前鼠标位置
            cursor_pos = QCursor.pos()
            QToolTip.showText(cursor_pos, self.tooltip_text, self)


# 交互式图标标签类，支持拖动、缩放和设置
class InteractiveIconLabel(QLabel):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.dragging = False
        self.drag_start_position = None
        self.default_size = QSize(60, 60)
        self.current_size = self.default_size
        self.main_window = main_window  # 保存主窗口引用
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("双击打开设置 | 滚轮缩放 | 拖动移动位置 | 右键菜单切换显示 | 按住缩放")
        self.setMinimumSize(30, 30)
        # 默认启用窗口缩放效果
        self.enable_window_scaling = True
        # 默认显示图标
        self.is_visible = True
        # 默认字体大小
        self.font_size = 11
        # 允许绝对定位
        self.setStyleSheet("QLabel { background: transparent; }")
        
        # 设置上下文菜单策略，接受右键事件
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        
        # 加载保存的配置
        self.load_settings()
        
        # 移除按住时缩放动画的参数
        
    def load_settings(self):
        """从Maya optionVar加载设置"""
        if cmds.optionVar(exists="CKTool_IconSize"):
            size = cmds.optionVar(query="CKTool_IconSize")
            self.current_size = QSize(size, size)
        
        if cmds.optionVar(exists="CKTool_IconScaling"):
            self.enable_window_scaling = bool(cmds.optionVar(query="CKTool_IconScaling"))
            
        if cmds.optionVar(exists="CKTool_IconVisible"):
            self.is_visible = bool(cmds.optionVar(query="CKTool_IconVisible"))
            
        if cmds.optionVar(exists="CKTool_IconPath"):
            self.icon_path = cmds.optionVar(query="CKTool_IconPath")
        else:
            # 默认图标路径
            self.icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "siri.gif")
        
        # 加载字体大小设置
        if cmds.optionVar(exists="CKTool_FontSize"):
            self.font_size = cmds.optionVar(query="CKTool_FontSize")
        else:
            # 默认字体大小设置为11
            self.font_size = 11
    
    def save_settings(self):
        """保存设置到Maya optionVar"""
        cmds.optionVar(intValue=("CKTool_IconSize", self.current_size.width()))
        cmds.optionVar(intValue=("CKTool_IconScaling", int(self.enable_window_scaling)))
        cmds.optionVar(intValue=("CKTool_IconVisible", int(self.is_visible)))
        
        if hasattr(self, 'icon_path') and self.icon_path:
            cmds.optionVar(stringValue=("CKTool_IconPath", self.icon_path))
            
        # 保存字体大小设置
        if hasattr(self, 'font_size'):
            cmds.optionVar(intValue=("CKTool_FontSize", self.font_size))
            
        # 如果有位置信息，也保存它
        if self.pos():
            cmds.optionVar(intValue=("CKTool_IconX", self.pos().x()))
            cmds.optionVar(intValue=("CKTool_IconY", self.pos().y()))
            
        # 调试信息 - 打印保存的设置
        print(f"保存设置: 大小={self.current_size.width()}, 可见={self.is_visible}, 图标路径={self.icon_path if hasattr(self, 'icon_path') else '无'}")
    
    def showContextMenu(self, pos):
        """显示右键菜单"""
        context_menu = QMenu(self)
        
        # 根据当前可见状态添加切换选项
        toggle_action = QAction("隐藏图标" if self.is_visible else "显示图标", self)
        toggle_action.triggered.connect(self.toggleVisibility)
        context_menu.addAction(toggle_action)
        
        # 添加设置选项
        settings_action = QAction("图标设置", self)
        settings_action.triggered.connect(self.showSettingsDialog)
        context_menu.addAction(settings_action)
        
        # 添加重置位置选项
        reset_pos_action = QAction("重置位置", self)
        reset_pos_action.triggered.connect(self.resetPosition)
        context_menu.addAction(reset_pos_action)
        
        # 显示菜单
        context_menu.exec_(self.mapToGlobal(pos))
    
    def toggleVisibility(self):
        """切换图标显示状态"""
        self.is_visible = not self.is_visible
        
        # 获取父容器以便调整
        parent_container = self.parent()
        
        # 批量处理UI更新，避免多次重绘
        self.setUpdatesEnabled(False)
        
        if hasattr(self, 'movie') and self.movie:
            if self.is_visible:
                # 恢复容器高度
                if parent_container:
                    parent_container.setMinimumHeight(70)
                # 启动动画并显示
                self.movie.start()
                self.setFixedSize(self.current_size)
                self.show()
            else:
                # 停止动画并隐藏
                self.movie.stop()
                self.setFixedSize(0, 0)
                # 减小容器高度
                if parent_container:
                    parent_container.setMinimumHeight(10)
        else:
            # 如果不是动画，使用普通显示/隐藏
            if self.is_visible:
                if parent_container:
                    parent_container.setMinimumHeight(70)
                self.setFixedSize(self.current_size)
                self.show()
            else:
                self.setFixedSize(0, 0)
                if parent_container:
                    parent_container.setMinimumHeight(10)
        
        # 恢复UI更新
        self.setUpdatesEnabled(True)
        
        # 更新布局，确保所有父级布局都能正确重新计算
        self.updateLayout()
        
        # 立即保存可见性状态
        self.save_settings()
        
        # 通知主窗口布局变化，以便整体调整
        if self.main_window:
            # 使用单一延迟调整
            QTimer.singleShot(50, self.main_window.adjustSize)
    
    def resetPosition(self):
        """重置图标位置到容器中央"""
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = (parent_rect.height() - self.height()) // 2
            self.move(x, y)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_position = event.pos()
            # 记录全局鼠标位置和当前控件位置
            self.start_global_pos = event.globalPos()
            self.start_position = self.pos()
            
            # 移除缩放动画功能
            
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.dragging and (event.buttons() & Qt.LeftButton):
            # 使用全局坐标计算相对移动距离，减少抽搐
            global_pos = event.globalPos()
            delta = global_pos - self.start_global_pos
            # 允许在水平和垂直方向上移动
            new_pos = self.start_position + delta
            
            # 确保不会移出父控件的边界
            parent_rect = self.parent().rect()
            new_x = max(0, min(parent_rect.width() - self.width(), new_pos.x()))
            new_y = max(0, min(parent_rect.height() - self.height(), new_pos.y()))
            self.move(new_x, new_y)
            
            # 移除了离中心越远越小的功能
            # 图标大小保持不变，无论其位置如何
            
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        self.dragging = False
        
        # 移除缩放动画恢复功能
            
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        # 打开设置对话框
        self.showSettingsDialog()
        super().mouseDoubleClickEvent(event)
        
    def wheelEvent(self, event):
        # 使用滚轮调整大小
        delta = event.angleDelta().y()
        scale_factor = 1.05 if delta > 0 else 0.95
        
        # 记录旧尺寸和当前位置
        old_size = self.current_size
        current_pos = self.pos()
        
        # 计算新尺寸
        new_width = max(30, min(200, int(self.current_size.width() * scale_factor)))
        new_height = max(30, min(200, int(self.current_size.height() * scale_factor)))
        self.current_size = QSize(new_width, new_height)
        
        # 应用新尺寸到动画
        if hasattr(self, 'movie') and self.movie:
            self.movie.setScaledSize(self.current_size)
        
        # 调整UI布局，而不是整个窗口大小
        if self.main_window and self.enable_window_scaling:
            # 通知布局调整
            self.updateLayout()
    
    def updateLayout(self):
        """优化的布局更新方法"""
        # 获取父布局
        if not self.parent() or not self.parent().layout():
            return
            
        # 强制更新一次布局
        self.parent().layout().activate()
        
        # 查找滚动区域
        scroll_area = self.findScrollArea(self.main_window)
        if scroll_area and scroll_area.widget() and scroll_area.widget().layout():
            content = scroll_area.widget()
            
            # 根据图标状态设置合适的边距
            if self.is_visible:
                size_ratio = min(2.0, max(0.5, self.current_size.width() / 60.0))
                margin = min(25, max(5, int(10 * size_ratio)))
                spacing = max(3, int(6 * size_ratio))
            else:
                margin = 5
                spacing = 3
            
            # 批量更新布局属性
            content.layout().setContentsMargins(margin, margin, margin, margin)
            content.layout().setSpacing(spacing)
            
            # 一次性触发布局更新
            content.layout().invalidate()
            content.layout().activate()
    
    def findScrollArea(self, widget):
        """递归查找窗口中的第一个QScrollArea"""
        if isinstance(widget, QScrollArea):
            return widget
            
        for child in widget.findChildren(QWidget):
            if isinstance(child, QScrollArea):
                return child
                
        return None

    def showSettingsDialog(self):
        # 创建设置对话框
        dialog = QDialog(self.window())
        dialog.setWindowTitle("图标设置")
        dialog.setMinimumWidth(300)
        dialog_layout = QVBoxLayout(dialog)
        
        # 添加图标选择部分
        icon_group = QGroupBox("图标选择")
        icon_layout = QVBoxLayout(icon_group)
        
        # 添加内置图标选择
        built_in_layout = QHBoxLayout()
        built_in_layout.addWidget(QLabel("内置图标:"))
        built_in_combo = QComboBox()
        built_in_combo.addItems(["标准动画", "控制版本", "控制Alt版本", "控制Shift版本", "猫咪动画"])
        # 尝试根据当前图标路径设置选中状态
        if hasattr(self, 'icon_path'):
            if "siri.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(0)
            elif "siri_ctrl.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(1)
            elif "siri_ctrlAlt.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(2)
            elif "siri_ctrlShift.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(3)
            elif "cat.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(4)
                
        built_in_layout.addWidget(built_in_combo)
        icon_layout.addLayout(built_in_layout)
        
        # 添加自定义图标选择
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("自定义图标:"))
        custom_path = QLineEdit()
        custom_path.setReadOnly(True)
        # 如果是自定义图标，显示路径
        if hasattr(self, 'icon_path') and os.path.exists(self.icon_path):
            icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
            if not self.icon_path.startswith(icons_dir):
                custom_path.setText(self.icon_path)
                
        custom_layout.addWidget(custom_path)
        browse_button = QPushButton("浏览...")
        
        def browse_icon():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "选择图标文件", "", 
                "图像文件 (*.png *.jpg *.gif *.svg)"
            )
            if file_path:
                custom_path.setText(file_path)
        
        browse_button.clicked.connect(browse_icon)
        custom_layout.addWidget(browse_button)
        icon_layout.addLayout(custom_layout)
        
        # 添加窗口缩放效果选项
        effect_group = QGroupBox("UI效果")
        effect_layout = QVBoxLayout(effect_group)
        
        # 窗口缩放效果复选框
        scale_window_check = QCheckBox("图标缩放时调整界面布局")
        scale_window_check.setChecked(self.enable_window_scaling)
        effect_layout.addWidget(scale_window_check)
        
        # 添加字体大小调整
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("字体大小:"))
        font_size_slider = QSlider(Qt.Horizontal)
        font_size_slider.setMinimum(8)
        font_size_slider.setMaximum(32)  # 增加最大值，移除上限
        font_size_slider.setValue(self.font_size)
        font_size_layout.addWidget(font_size_slider)
        font_size_label = QLabel(f"{font_size_slider.value()}px")
        font_size_layout.addWidget(font_size_label)
        
        def update_font_size(value):
            font_size_label.setText(f"{value}px")
            # 创建新的字体并设置大小
            new_font = QFont()
            new_font.setPointSize(value)
            # 实时应用到主窗口
            if self.main_window:
                # 使用主窗口的更新字体大小方法
                self.main_window.update_font_size(value)
            
        font_size_slider.valueChanged.connect(update_font_size)
        effect_layout.addLayout(font_size_layout)
        
        # 添加窗口透明度调整
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("窗口透明度:"))
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setMinimum(50)
        opacity_slider.setMaximum(100)
        opacity_slider.setValue(int(self.main_window.windowOpacity() * 100) if self.main_window else 100)
        opacity_layout.addWidget(opacity_slider)
        opacity_label = QLabel(f"{opacity_slider.value()}%")
        opacity_layout.addWidget(opacity_label)
        
        def update_opacity(value):
            opacity_label.setText(f"{value}%")
            if self.main_window:
                self.main_window.setWindowOpacity(value / 100.0)
                
        opacity_slider.valueChanged.connect(update_opacity)
        effect_layout.addLayout(opacity_layout)
        
        # 添加尺寸调整部分
        size_group = QGroupBox("图标尺寸")
        size_layout = QVBoxLayout(size_group)
        
        size_slider_layout = QHBoxLayout()
        size_slider_layout.addWidget(QLabel("尺寸:"))
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setMinimum(30)
        size_slider.setMaximum(200)
        size_slider.setValue(self.current_size.width())
        size_slider_layout.addWidget(size_slider)
        size_label = QLabel(f"{self.current_size.width()}px")
        size_slider_layout.addWidget(size_label)
        
        def update_size_label(value):
            size_label.setText(f"{value}px")
            
        size_slider.valueChanged.connect(update_size_label)
        size_layout.addLayout(size_slider_layout)
        
        # 添加重置按钮
        reset_button = QPushButton("重置到默认值")
        
        def reset_to_default():
            size_slider.setValue(60)
            built_in_combo.setCurrentIndex(0)
            custom_path.setText("")
            opacity_slider.setValue(100)
            scale_window_check.setChecked(True)
            font_size_slider.setValue(11)  # 重置字体大小到默认值11px
            
        reset_button.clicked.connect(reset_to_default)
        
        # 添加确定和取消按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        def apply_settings():
            # 保存当前尺寸
            self.current_size = QSize(size_slider.value(), size_slider.value())
            
            # 保存窗口缩放设置
            self.enable_window_scaling = scale_window_check.isChecked()
            
            # 保存字体大小设置
            self.font_size = font_size_slider.value()
            
            # 应用选择的图标
            icon_path = ""
            if custom_path.text():
                icon_path = custom_path.text()
            else:
                # 根据内置图标选择相应文件
                icon_index = built_in_combo.currentIndex()
                icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
                if icon_index == 0:
                    icon_path = os.path.join(icons_dir, "siri.gif")
                elif icon_index == 1:
                    icon_path = os.path.join(icons_dir, "siri_ctrl.gif")  # 蓝色图标
                elif icon_index == 2:
                    icon_path = os.path.join(icons_dir, "siri_ctrlAlt.gif")  # 绿色图标
                elif icon_index == 3:
                    icon_path = os.path.join(icons_dir, "siri_ctrlShift.gif")  # 红色图标
                elif icon_index == 4:
                    icon_path = os.path.join(icons_dir, "cat.gif")  # 猫咪动画
            
            # 保存图标路径
            self.icon_path = icon_path
            
            # 加载新图标
            if os.path.exists(icon_path):
                if hasattr(self, 'movie') and self.movie:
                    self.movie.stop()
                
                # 根据文件类型选择加载方式
                if icon_path.lower().endswith(('.gif')):
                    movie = QMovie(icon_path)
                    movie.setScaledSize(self.current_size)
                    self.setMovie(movie)
                    self.movie = movie
                    movie.start()
                else:
                    pixmap = QPixmap(icon_path)
                    pixmap = pixmap.scaled(
                        self.current_size, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    self.setPixmap(pixmap)
                    if hasattr(self, 'movie'):
                        self.movie = None
            
            # 更新全局字体大小
            if self.main_window:
                self.main_window.update_font_size(self.font_size)
                        
            # 触发UI布局调整
            if scale_window_check.isChecked() and self.main_window:
                self.updateLayout()
            
            # 保存设置到Maya optionVar
            self.save_settings()
            
            dialog.accept()
            
        ok_button.clicked.connect(apply_settings)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 组装对话框
        dialog_layout.addWidget(icon_group)
        dialog_layout.addWidget(effect_group)
        dialog_layout.addWidget(size_group)
        dialog_layout.addLayout(button_layout)
        
        # 显示对话框
        dialog.exec_()


class CollapsibleGroupBox(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        
        # 创建切换按钮
        self.toggle_button = QPushButton(f"▼ {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        
        # 创建内容部件
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_widget)
        self.is_collapsed = False

        # 标题为骨骼Tag或FK层级设置的折叠组增加额外的最小高度
        self.special_group = title in ["骨骼Tag", "FK层级设置"]
        
        # 避免内容闪烁，初始设置不可见
        self.content_widget.setVisible(False)
        
        # 创建更复杂的动画系统
        # 1. 高度动画
        self.height_animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.height_animation.setDuration(200)  # 稍微增加时长，使动画更平滑
        self.height_animation.setEasingCurve(QEasingCurve.OutCubic)  # 使用更平滑的缓动效果
        
        # 2. 透明度动画
        self.opacity_effect = QGraphicsOpacityEffect(self.content_widget)
        self.opacity_effect.setOpacity(1.0)
        self.content_widget.setGraphicsEffect(self.opacity_effect)
        
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(150)  # 透明度动画比高度动画稍快
        
        # 3. 创建动画组
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(self.height_animation)
        self.animation_group.addAnimation(self.opacity_animation)
        self.animation_group.finished.connect(self.on_animation_finished)
        
        # 添加缓存内容高度，避免重复计算
        self._cached_content_height = 0
        
        # 确保内容高度为0
        self.content_widget.setMaximumHeight(0)
        
        # 延迟初始化，确保初始状态正确
        QTimer.singleShot(5, self.toggle_collapsed)

    def toggle_collapsed(self):
        # 停止所有正在进行的动画
        self.animation_group.stop()
        
        # 更新折叠状态
        self.is_collapsed = not self.is_collapsed

        # 设置文本和图标
        original_text = self.toggle_button.text().lstrip('▶▼ ')
        self.toggle_button.setText(
            f"{'▼' if not self.is_collapsed else '▶'} {original_text}"
        )
        
        # 获取主窗口实例以获取字体大小设置
        main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if isinstance(parent_widget, CombinedTool):
                main_window = parent_widget
                break
            parent_widget = parent_widget.parent()
            
        # 获取字体大小，默认为12
        font_size = 12
        if main_window and hasattr(main_window, 'font_size'):
            font_size = main_window.font_size
            
        # 更新按钮样式
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #3A3A3A;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
                font-size: {font_size}px;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: #4A4A4A;
            }}
            QPushButton:pressed {{
                background-color: #353535;
            }}
        """)

        # 如果展开，先设置内容为可见
        if not self.is_collapsed:
            self.content_widget.setVisible(True)
            self.opacity_effect.setOpacity(0.0)
        
        # 计算内容高度
        if self._cached_content_height > 0 and not self.is_collapsed:
            content_height = self._cached_content_height
        else:
            # 计算内容的实际高度
            self.content_widget.adjustSize()
            content_height = self.content_layout.sizeHint().height() + 8
            
            # 如果是特殊组件，确保最小高度足够
            if self.special_group and not self.is_collapsed:
                content_height = max(content_height, 180)
                
            # 缓存计算结果
            if not self.is_collapsed:
                self._cached_content_height = content_height

        # 确保动画结束值不为0
        if not self.is_collapsed and content_height <= 0:
            content_height = 50
            self._cached_content_height = content_height
            
        # 设置高度动画参数
        self.height_animation.setStartValue(0 if not self.is_collapsed else content_height)
        self.height_animation.setEndValue(content_height if not self.is_collapsed else 0)
        
        # 设置透明度动画参数
        self.opacity_animation.setStartValue(0.0 if not self.is_collapsed else 1.0)
        self.opacity_animation.setEndValue(1.0 if not self.is_collapsed else 0.0)
        
        # 开始动画
        self.animation_group.start()
        
        # 更新布局
        self.updateGeometry()
        if self.parentWidget():
            self.parentWidget().updateGeometry()

    def on_animation_finished(self):
        """动画完成后的处理"""
        # 根据折叠状态设置最终状态
        if self.is_collapsed:
            self.content_widget.setVisible(False)
        else:
            self.content_widget.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        
        # 更新布局
        self.updateGeometry()
        if self.parentWidget():
            self.parentWidget().updateGeometry()

    def setLayout(self, layout):
        """设置内容布局"""
        # 清除旧布局内容
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # 添加新布局
        self.content_layout.addLayout(layout)
        
        # 重置缓存高度
        self._cached_content_height = 0
        
        # 如果当前未折叠，立即更新高度
        if not self.is_collapsed:
            self.content_widget.adjustSize()
            content_height = self.content_layout.sizeHint().height() + 8
            
            if self.special_group:
                content_height = max(content_height, 180)
                
            self.content_widget.setMaximumHeight(content_height)
            self._cached_content_height = content_height
            
            self.updateGeometry()
            if self.parentWidget():
                self.parentWidget().updateGeometry()


class CombinedTool(QMainWindow):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = CombinedTool()
        return cls._instance

    def __init__(self):
        super().__init__(parent=get_maya_main_window())
        self.setWindowTitle("综合工具")
        self.setObjectName("CombinedToolWindow")
        self.resize(420, 500)  # 设置默认窗口大小
        
        # 设置窗口标志
        try:
            self.setWindowFlags(Qt.Window)  # 移除 Qt.WindowStaysOnTopHint
        except:
            # 如果设置失败（可能是旧版本的Qt）
            pass

        # 重载controller_shapes模块以获取最新的形状
        try:
            importlib.reload(controller_shapes)
        except:
            # 导入失败时继续
            pass
        
        # 尝试恢复之前保存的窗口大小
        if cmds.optionVar(exists="CombinedToolWindowWidth") and cmds.optionVar(exists="CombinedToolWindowHeight"):
            width = cmds.optionVar(query="CombinedToolWindowWidth")
            height = cmds.optionVar(query="CombinedToolWindowHeight")
            if width > 200 and height > 300:  # 确保合理的最小大小
                self.resize(width, height)

        # 默认设置
        self.group_prefix = "zero"
        self.remove_prefix = True
        self.use_existing_suffix = True
        self.freeze_scale = True
        self.match_position = True
        self.match_rotation = True
        self.match_scale = False
        self.color_rgb = [1.0, 1.0, 1.0]
        self.use_hierarchy_logic = True
        self.controller_type = "sphere"
        self.create_joint_flag = False
        self.create_controller_flag = True
        self.create_sub_controller_flag = False
        self.enable_custom_group = False
        self.use_selection_count_flag = True
        self.tag_history = []
        self.custom_group_name = ""

        # 用于保存外部工具的实例
        
        # 获取保存的字体大小设置
        self.font_size = 11  # 默认字体大小
        if cmds.optionVar(exists="CKTool_FontSize"):
            self.font_size = cmds.optionVar(query="CKTool_FontSize")

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QWidget {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QPushButton {{
                background-color: #3E3E42;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 22px;
                font-size: {self.font_size}px;
            }}
            QPushButton:hover {{
                background-color: #505054;
                border-color: #6A6A6A;
            }}
            QPushButton:pressed {{
                background-color: #2A2A2A;
                border-color: #777777;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                selection-background-color: #264F78;
                font-size: {self.font_size}px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                min-height: 20px;
                font-size: {self.font_size}px;
            }}
            QComboBox:hover {{
                border-color: #6A6A6A;
            }}
            QComboBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QCheckBox {{
                color: #E0E0E0;
                spacing: 6px;
                font-size: {self.font_size}px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid #555555;
                border-radius: 2px;
                background-color: #333337;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0078D7;
                border-color: #0078D7;
            }}
            QCheckBox::indicator:hover {{
                border-color: #6A6A6A;
            }}
            QLabel {{
                color: #E0E0E0;
                font-size: {self.font_size}px;
            }}
            QScrollArea {{
                background-color: #2D2D30;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: #2D2D30;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555555;
                min-height: 20px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #6A6A6A;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: #2D2D30;
            }}
            QToolTip {{
                background-color: #2D2D30;
                color: #E0E0E0;
                border: 1px solid #555555;
                padding: 4px;
                opacity: 220;
                font-size: {self.font_size}px;
            }}
            QFrame[frameShape="4"] {{ /* 分隔线 */
                background-color: #555555;
                height: 1px;
                max-height: 1px;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 添加可交互GIF动画
        self.gif_container = QWidget()
        # 设置最小高度，确保有足够的空间显示图标
        self.gif_container.setMinimumHeight(70)
        # 设置尺寸策略，允许收缩但优先保持最小高度
        self.gif_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        # 使用绝对定位布局，允许图标自由移动
        container_layout = QHBoxLayout(self.gif_container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setContentsMargins(0, 0, 0, 0)
        # 添加对象名便于识别和样式化
        self.gif_container.setObjectName("gifContainer")
        
        # 创建交互式图标标签
        self.gif_label = InteractiveIconLabel(main_window=self)
        container_layout.addWidget(self.gif_label)
        
        # 先获取可见性状态，以便后续处理
        is_visible = self.gif_label.is_visible
        print(f"加载的可见性状态: {is_visible}")
        
        # 加载GIF - 使用保存的图标路径
        if hasattr(self.gif_label, 'icon_path') and os.path.exists(self.gif_label.icon_path):
            if self.gif_label.icon_path.lower().endswith('.gif'):
                movie = QMovie(self.gif_label.icon_path)
                movie.setScaledSize(self.gif_label.current_size)
                self.gif_label.setMovie(movie)
                self.gif_label.movie = movie
                movie.start()
            else:
                pixmap = QPixmap(self.gif_label.icon_path)
                pixmap = pixmap.scaled(
                    self.gif_label.current_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.gif_label.setPixmap(pixmap)
                self.gif_label.movie = None
        else:
            # 默认图标
            gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "siri.gif")
            if os.path.exists(gif_path):
                movie = QMovie(gif_path)
                movie.setScaledSize(self.gif_label.current_size)
                self.gif_label.setMovie(movie)
                self.gif_label.movie = movie
                movie.start()
                self.gif_label.icon_path = gif_path
            
        # 设置图标在容器中的初始垂直位置
        # 在布局更新后用QTimer延迟执行，确保容器大小已经计算好
        QTimer.singleShot(100, self.center_icon_vertically)
        
        # 如果之前保存了位置信息，恢复位置
        if cmds.optionVar(exists="CKTool_IconX") and cmds.optionVar(exists="CKTool_IconY"):
            x = cmds.optionVar(query="CKTool_IconX")
            y = cmds.optionVar(query="CKTool_IconY")
            QTimer.singleShot(200, lambda: self.gif_label.move(x, y))
        
        # 确保图标容器有正确的初始状态
        if is_visible:
            self.gif_container.setMinimumHeight(70)
        else:
            self.gif_container.setMinimumHeight(10)
        
        # 最后处理图标隐藏状态
        if not is_visible:
            # 使用单次计时器确保在UI完全初始化后再处理隐藏
            QTimer.singleShot(500, lambda: self._apply_icon_visibility(False))
        
        # 将GIF容器添加到主布局
        main_layout.addWidget(self.gif_container)
        
        # 为整个主窗口添加右键菜单功能
        main_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        main_widget.customContextMenuRequested.connect(self.showMainContextMenu)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("QFrame { border: 0.5px double #000000; }")
        main_layout.addWidget(separator)

        # 创建固定在顶部的控制区域
        fixed_controls_widget = QWidget()
        fixed_controls_layout = QVBoxLayout(fixed_controls_widget)
        fixed_controls_layout.setSpacing(5)
        fixed_controls_layout.setContentsMargins(10, 5, 10, 5)
        
        # 分隔线样式
        separator_style = "QFrame { border: 0.5px double #000000; }"

        # 添加控制器大小调整控件
        controller_size_layout = QHBoxLayout()
        controller_size_label = QLabel("曲线大小:")
        controller_size_label.setFixedWidth(80)
        self.scale_factor_input = QDoubleSpinBox()
        self.scale_factor_input.setRange(0.1, 10.0)
        self.scale_factor_input.setValue(1)
        self.scale_factor_input.setSingleStep(0.1)
        self.scale_factor_input.setDecimals(2)
        self.scale_factor_input.setToolTip("输入缩放倍率（0.1-10.0）")
        scale_up_button = DelayedToolTipButton("变大", "按倍率放大控制顶点，要保证输入不小于1")
        scale_up_button.clicked.connect(self.scale_cv_handles_up)
        scale_down_button = DelayedToolTipButton("变小", "按倍率缩小控制顶点，要保证输入不小于1")
        scale_down_button.clicked.connect(self.scale_cv_handles_down)
        controller_size_layout.addWidget(controller_size_label)
        controller_size_layout.addWidget(self.scale_factor_input)
        controller_size_layout.addWidget(scale_up_button)
        controller_size_layout.addWidget(scale_down_button)
        fixed_controls_layout.addLayout(controller_size_layout)

        # 添加曲线粗细调整控件
        curve_width_layout = QHBoxLayout()
        curve_width_label = QLabel("曲线粗细:")
        curve_width_label.setFixedWidth(80)
        self.curve_width_input = QSpinBox()
        self.curve_width_input.setRange(1, 20)
        self.curve_width_input.setValue(1)
        self.curve_width_input.setSingleStep(1)
        self.curve_width_input.setToolTip("设置曲线粗细值（1-20）")
        apply_curve_width_button = DelayedToolTipButton("应用粗细", "为选中的曲线设置指定的粗细值")
        apply_curve_width_button.clicked.connect(self.apply_curve_width)
        curve_width_layout.addWidget(curve_width_label)
        curve_width_layout.addWidget(self.curve_width_input)
        curve_width_layout.addWidget(apply_curve_width_button)
        fixed_controls_layout.addLayout(curve_width_layout)

        # 添加位移旋转缩放重置按钮
        reset_layout = QHBoxLayout()
        reset_pos_button = DelayedToolTipButton("位移归0", "将选中物体的平移值重置为 (0, 0, 0)")
        reset_pos_button.clicked.connect(self.reset_position)
        reset_layout.addWidget(reset_pos_button)
        reset_rot_button = DelayedToolTipButton("旋转归0", "将选中物体的旋转值重置为 (0, 0, 0)")
        reset_rot_button.clicked.connect(self.reset_rotation)
        reset_layout.addWidget(reset_rot_button)
        reset_scale_button = DelayedToolTipButton("缩放归1", "将选中物体的缩放值重置为 (1, 1, 1)")
        reset_scale_button.clicked.connect(self.reset_scale)
        reset_layout.addWidget(reset_scale_button)
        fixed_controls_layout.addLayout(reset_layout)
        
        # 将固定控制区域添加到主布局
        main_layout.addWidget(fixed_controls_widget)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        main_layout.addWidget(separator)

        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        scroll_layout.addWidget(separator)

        # 控制器颜色 - 移动到创建关节与控制器组件的上面
        color_group = CollapsibleGroupBox("控制器颜色")
        color_layout = QGridLayout()
        color_layout.setSpacing(5)
        # 移除颜色选择按钮和标签
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(100, 24)  # 略微增大尺寸
        self.color_preview.setStyleSheet("""
            border: 1px solid #666666; 
            border-radius: 5px;
            background-color: transparent;
        """)
        self.color_preview.setCursor(Qt.PointingHandCursor)  # 添加手型光标
        self.color_preview.mousePressEvent = lambda event: self.show_color_dialog()  # 使组件可点击

        # 添加悬停效果
        def preview_enter_event(event):
            r, g, b = [int(c * 255) for c in self.color_rgb]
            hex_color = QColor(r, g, b).name().upper()
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
            
            self.color_preview.setStyleSheet(f"""
                background-color: {hex_color}; 
                border: 2px solid #0078D7; 
                border-radius: 5px;
                color: {text_color};
                font-size: 10px;
                text-align: center;
                padding: 2px;
            """)

        def preview_leave_event(event):
            r, g, b = [int(c * 255) for c in self.color_rgb]
            hex_color = QColor(r, g, b).name().upper()
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
            
            self.color_preview.setStyleSheet(f"""
                background-color: {hex_color}; 
                border: 1px solid #666666; 
                border-radius: 5px;
                color: {text_color};
                font-size: 10px;
                text-align: center;
                padding: 2px;
            """)

        self.color_preview.enterEvent = preview_enter_event
        self.color_preview.leaveEvent = preview_leave_event

        self.update_color_preview()
        color_layout.addWidget(QLabel("颜色:"), 0, 0)
        color_layout.addWidget(self.color_preview, 0, 1)
        color_layout.addWidget(QLabel("预设颜色："), 1, 0)
        
        # 从颜色选择器.py引用颜色数组
        preset_colors = [
            # 第一行
            (0.5, 0.5, 0.5), (0, 0, 0), (0.247, 0.247, 0.247), (0.498, 0.498, 0.498),
            (0.608, 0, 0.157), (0, 0.16, 0.376), (0, 0, 1), (0, 0.275, 0.094),
            # 第二行
            (0.149, 0, 0.263), (0.78, 0, 0.78), (0.537, 0.278, 0.2), (0.243, 0.133, 0.121),
            (0.6, 0.145, 0), (1, 0, 0), (0, 1, 0), (0, 0.2549, 0.6),
            # 第三行
            (1, 1, 1), (1, 1, 0), (0.388, 0.863, 1), (0.263, 1, 0.639),
            (1, 0.686, 0.686), (0.89, 0.674, 0.474), (1, 1, 0.388), (0, 0.6, 0.329),
            # 第四行
            (0.627, 0.411, 0.188), (0.619, 0.627, 0.188), (0.408, 0.631, 0.188), (0.188, 0.631, 0.365),
            (0.188, 0.627, 0.627), (0.188, 0.403, 0.627), (0.434, 0.188, 0.627), (0.627, 0.188, 0.411)
        ]
        
        # 创建颜色网格布局，8列4行
        preset_grid_layout = QGridLayout()
        preset_grid_layout.setSpacing(2)
        
        for i, color in enumerate(preset_colors):
            row = i // 8
            col = i % 8
            
            # 将RGB值转换为十六进制颜色
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255)
            )
            
            color_button = DelayedToolTipButton("", f"应用颜色 {hex_color}")
            color_button.setFixedSize(20, 20)
            color_button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #666666; padding: 0px; min-width: 20px; min-height: 20px; max-width: 20px; max-height: 20px;")
            color_button.clicked.connect(lambda checked=False, rgb=color: (self.set_preset_color(rgb), self.apply_color_to_controller()))
            
            preset_grid_layout.addWidget(color_button, row, col)
        
        color_layout.addLayout(preset_grid_layout, 1, 1)
        apply_color_button = DelayedToolTipButton("应用颜色", "将当前颜色应用到选中的控制器")
        apply_color_button.clicked.connect(self.apply_color_to_controller)
        color_layout.addWidget(apply_color_button, 2, 0, 1, 2)
        
        # 应用颜色和重置颜色按钮 - 横向平均分布
        apply_reset_layout = QHBoxLayout()
        apply_reset_layout.setSpacing(5)  # 设置按钮间距
        
        reset_color_button = DelayedToolTipButton("重置颜色", "将绘制覆盖从RGB改为索引，然后关闭启用覆盖")
        reset_color_button.clicked.connect(self.reset_color)
        apply_reset_layout.addWidget(reset_color_button, 1)  # stretch factor = 1
        
        color_layout.addLayout(apply_reset_layout, 3, 0, 1, 2)
        
        # 随机颜色和渐变颜色按钮 - 横向平均分布
        color_buttons_layout = QHBoxLayout()
        color_buttons_layout.setSpacing(5)  # 设置按钮间距
        
        random_color_button = DelayedToolTipButton("随机颜色", "为选中的物体赋予随机颜色材质")
        random_color_button.clicked.connect(self.apply_random_colors)
        color_buttons_layout.addWidget(random_color_button, 1)  # stretch factor = 1
        
        gradient_color_button = DelayedToolTipButton("渐变颜色", "打开渐变颜色工具，为选中的物体应用渐变色彩效果")
        gradient_color_button.clicked.connect(self.open_gradient_color_tool)
        color_buttons_layout.addWidget(gradient_color_button, 1)  # stretch factor = 1
        
        color_layout.addLayout(color_buttons_layout, 4, 0, 1, 2)
        
        color_group.setLayout(color_layout)
        scroll_layout.addWidget(color_group)

        # 关节与控制器创建
        joint_ctrl_group = CollapsibleGroupBox("创建关节与控制器")
        joint_ctrl_layout = QVBoxLayout()
        joint_ctrl_layout.setSpacing(5)

        custom_group_layout = QHBoxLayout()
        custom_group_label = QLabel("自定义组名称:")
        self.custom_group_input = QLineEdit()
        self.custom_group_input.setPlaceholderText("输入组名（创建的控制器放入的位置）")
        self.enable_custom_group_check = QCheckBox("启用自定义组")
        self.enable_custom_group_check.setChecked(False)
        self.enable_custom_group_check.stateChanged.connect(self.toggle_custom_group)
        custom_group_layout.addWidget(custom_group_label)
        custom_group_layout.addWidget(self.custom_group_input)
        custom_group_layout.addWidget(self.enable_custom_group_check)
        joint_ctrl_layout.addLayout(custom_group_layout)

        main_settings_layout = QGridLayout()
        main_settings_layout.addWidget(QLabel("名称："), 0, 0)
        self.name_text = QLineEdit("")
        main_settings_layout.addWidget(self.name_text, 0, 1)
        main_settings_layout.addWidget(QLabel("侧面："), 0, 2)
        self.side_text = QLineEdit("")
        self.side_text.setToolTip("可用逗号隔开来创建多个侧面，例如 'l,r,m'")  # 添加工具提示
        main_settings_layout.addWidget(self.side_text, 0, 3)
        main_settings_layout.addWidget(QLabel("控制器大小："), 1, 0)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setMinimum(0.1)
        self.size_spin.setValue(1.0)
        main_settings_layout.addWidget(self.size_spin, 1, 1)
        main_settings_layout.addWidget(QLabel("数量："), 1, 2)
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setValue(1)
        main_settings_layout.addWidget(self.count_spin, 1, 3)
        main_settings_layout.addWidget(QLabel("控制器类型："), 2, 0)
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["球形 (Sphere)", "立方体 (Cube)", "圆形 (Circle)",
                                        "箭头 (Arrow)", "齿轮 (Gear)", "圆锥 (Cone)",
                                        "十字 (Cross)", "钻石 (Diamond)", "矩形 (Rectangle)",
                                        "正方形 (Square)"])
        self.controller_combo.currentTextChanged.connect(self.update_controller_type)
        main_settings_layout.addWidget(self.controller_combo, 2, 1, 1, 3)
        # 创建关节选项行，包含识别物体名称和忽略后缀选项
        joint_options_layout = QHBoxLayout()
        self.create_joint_check = QCheckBox("创建关节")
        self.create_joint_check.setChecked(False)
        self.create_joint_check.stateChanged.connect(self.toggle_create_joint)
        joint_options_layout.addWidget(self.create_joint_check)
        
        # 物体名称识别选项
        self.auto_name_from_joint_check = QCheckBox("识别物体名称")
        self.auto_name_from_joint_check.setChecked(False)
        self.auto_name_from_joint_check.setToolTip("自动从选中物体名称识别控制器名称\n支持骨骼格式：jnt_m_aaa_001 -> ctrl_m_aaa_001\n支持其他物体：任意物体名称都可识别\n如果不符合格式则使用完整物体名称")
        joint_options_layout.addWidget(self.auto_name_from_joint_check)
        
        joint_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(joint_options_layout, 3, 0, 1, 4)
        
        # 创建控制器选项行，包含忽略后缀选项
        controller_options_layout = QHBoxLayout()
        self.create_controller_check = QCheckBox("创建控制器")
        self.create_controller_check.setChecked(True)
        self.create_controller_check.stateChanged.connect(self.toggle_create_controller)
        controller_options_layout.addWidget(self.create_controller_check)
        
        # 忽略后缀选项
        self.ignore_suffix_check = QCheckBox("忽略后缀")
        self.ignore_suffix_check.setChecked(True)
        self.ignore_suffix_check.setToolTip("识别物体名称时忽略末尾的后缀\n例如：object_001、object1、object_a 都会被识别为 object")
        controller_options_layout.addWidget(self.ignore_suffix_check)
        
        controller_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(controller_options_layout, 4, 0, 1, 4)
        
        # 创建层级关系选项行
        hierarchy_options_layout = QHBoxLayout()
        self.controller_parent_original_check = QCheckBox("控制器作为原物体父级")
        self.controller_parent_original_check.setChecked(False)
        self.controller_parent_original_check.setToolTip("生成后原物体会在控制器的子级")
        self.controller_parent_original_check.stateChanged.connect(self.toggle_controller_parent_original)
        hierarchy_options_layout.addWidget(self.controller_parent_original_check)
        
        self.original_parent_controller_check = QCheckBox("原物体作为控制器父级")
        self.original_parent_controller_check.setChecked(False)
        self.original_parent_controller_check.setToolTip("生成后控制器会在原物体的子级")
        self.original_parent_controller_check.stateChanged.connect(self.toggle_original_parent_controller)
        hierarchy_options_layout.addWidget(self.original_parent_controller_check)
        
        hierarchy_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(hierarchy_options_layout, 5, 0, 1, 4)
        
        self.create_sub_controller_check = QCheckBox("创建子控制器")
        self.create_sub_controller_check.setChecked(False)
        self.create_sub_controller_check.stateChanged.connect(self.toggle_create_sub_controller)
        main_settings_layout.addWidget(self.create_sub_controller_check, 6, 0, 1, 2)
        self.hierarchy_check = QCheckBox("使用层级组逻辑")
        self.hierarchy_check.setChecked(True)
        self.hierarchy_check.stateChanged.connect(self.toggle_hierarchy_logic)
        main_settings_layout.addWidget(self.hierarchy_check, 6, 2, 1, 2)
        
        # 根据选择物体数量创建选项 - 默认开启，不显示UI
        # self.use_selection_count_check = QCheckBox("根据选择物体数量创建")
        # self.use_selection_count_check.setChecked(True)
        # self.use_selection_count_check.setToolTip("启用后，将根据当前选择的物体数量创建对应数量的关节和控制器\n例如：选择5个物体就创建5个关节控制器组合")
        # self.use_selection_count_check.stateChanged.connect(self.toggle_use_selection_count)
        # main_settings_layout.addWidget(self.use_selection_count_check, 6, 0, 1, 4)
        
        joint_ctrl_layout.addLayout(main_settings_layout)

        match_group = CollapsibleGroupBox("匹配变换")
        match_layout = QGridLayout()
        match_layout.setSpacing(5)
        self.match_position_check = QCheckBox("匹配平移")
        self.match_position_check.setChecked(True)
        self.match_position_check.stateChanged.connect(self.toggle_match_position)
        match_layout.addWidget(self.match_position_check, 0, 0)
        self.match_rotation_check = QCheckBox("匹配旋转")
        self.match_rotation_check.setChecked(True)
        self.match_rotation_check.stateChanged.connect(self.toggle_match_rotation)
        match_layout.addWidget(self.match_rotation_check, 1, 0)
        self.match_scale_check = QCheckBox("匹配缩放")
        self.match_scale_check.setChecked(False)
        self.match_scale_check.stateChanged.connect(self.toggle_match_scale)
        match_layout.addWidget(self.match_scale_check, 2, 0)

        # 添加匹配变换按钮
        match_button = DelayedToolTipButton("应用匹配", "将选中的物体匹配到最后一个选中的物体")
        match_button.clicked.connect(self.match_selected_transforms)
        match_layout.addWidget(match_button, 3, 0)

        match_group.setLayout(match_layout)
        joint_ctrl_layout.addWidget(match_group)

        create_button = DelayedToolTipButton("创建", "根据选择数量创建关节和/或控制器，根据匹配变换设置匹配变换")
        create_button.clicked.connect(self.create_joint_and_controller)
        joint_ctrl_layout.addWidget(create_button)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        joint_ctrl_layout.addWidget(separator)

        # 第一行：镜像曲线形状、替换曲线形状、添加形状节点
        first_row_layout = QHBoxLayout()
        first_row_layout.setSpacing(5)  # 设置按钮间距
        
        mirror_curve_button = DelayedToolTipButton("镜像曲线形状",
                                                   "选择两个曲线，将第一个曲线的形状沿 X 轴镜像到第二个")
        mirror_curve_button.clicked.connect(self.open_mirror_curve_shape)
        first_row_layout.addWidget(mirror_curve_button, 1)  # stretch factor = 1
        
        trans_curve_button = DelayedToolTipButton("替换曲线形状", "将源曲线的形状复制到目标曲线，替换目标曲线的现有形状")
        trans_curve_button.clicked.connect(self.open_trans_curve_shape)
        first_row_layout.addWidget(trans_curve_button, 1)  # stretch factor = 1
        
        reparent_shape_button = DelayedToolTipButton("添加形状节点",
                                                     "将选中物体的形状节点添加到最后一个选中的目标物体下")
        reparent_shape_button.clicked.connect(self.reparent_shape_nodes)
        first_row_layout.addWidget(reparent_shape_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(first_row_layout)
        
        # 第二行：曲线Shape重命名、切换显示在前面
        second_row_layout = QHBoxLayout()
        second_row_layout.setSpacing(5)  # 设置按钮间距
        
        rename_curve_shapes_button = DelayedToolTipButton("曲线Shape重命名",
                                                          "自动识别场景中所有曲线并重命名其Shape节点")
        rename_curve_shapes_button.clicked.connect(self.auto_rename_curve_shapes)
        second_row_layout.addWidget(rename_curve_shapes_button, 1)  # stretch factor = 1
        
        always_draw_on_top_button = DelayedToolTipButton("切换显示在前面",
                                                         "切换选中曲线的alwaysDrawOnTop属性，使其显示在其他物体前面")
        always_draw_on_top_button.clicked.connect(self.toggle_always_draw_on_top)
        second_row_layout.addWidget(always_draw_on_top_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(second_row_layout)
        
        # 第三行：结合曲线、拆分曲线
        third_row_layout = QHBoxLayout()
        third_row_layout.setSpacing(5)  # 设置按钮间距
        
        combine_curves_button = DelayedToolTipButton("结合曲线",
                                                     "将选中的多个曲线合并为一个曲线对象")
        combine_curves_button.clicked.connect(self.combine_selected_curves)
        third_row_layout.addWidget(combine_curves_button, 1)  # stretch factor = 1
        
        separate_curves_button = DelayedToolTipButton("拆分曲线",
                                                      "将包含多个形状的曲线拆分为独立的曲线对象")
        separate_curves_button.clicked.connect(self.separate_selected_curves)
        third_row_layout.addWidget(separate_curves_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(third_row_layout)

        # 添加FK层级功能
        fk_hierarchy_separator = QFrame()
        fk_hierarchy_separator.setFrameShape(QFrame.HLine)
        fk_hierarchy_separator.setStyleSheet(separator_style)
        joint_ctrl_layout.addWidget(fk_hierarchy_separator)

        fk_hierarchy_group = CollapsibleGroupBox("FK层级设置")
        fk_hierarchy_layout = QVBoxLayout()
        fk_hierarchy_layout.setSpacing(8)  # 增加间距使布局更清晰
        
        # 添加提示信息
        info_label = QLabel("注：FK层级将使用上方「创建关节与控制器」的设置")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #999999; font-style: italic;")
        fk_hierarchy_layout.addWidget(info_label)
        
        # 排除最后一个骨骼选项
        self.exclude_last_joint_check = QCheckBox("排除最后一个骨骼")
        self.exclude_last_joint_check.setChecked(True)
        self.exclude_last_joint_check.setToolTip("创建FK层级时排除骨骼链中的最后一个骨骼")
        fk_hierarchy_layout.addWidget(self.exclude_last_joint_check)
        
        
        # 创建约束框架
        constraints_group = QGroupBox("")
        constraints_layout = QGridLayout()
        constraints_layout.setVerticalSpacing(6)  # 增加垂直间距防止文字重叠
        constraints_layout.setHorizontalSpacing(10)  # 调整水平间距
        constraints_layout.setContentsMargins(10, 8, 10, 8)  # 增加边距

        # 使用两列布局：左侧是约束类型，右侧是偏移设置
        constraint_types = [
            ("父子约束", "parent_constraint_check", "parent_offset_check"),
            ("点约束", "point_constraint_check", "point_offset_check"),
            ("方向约束", "orient_constraint_check", "orient_offset_check"),
            ("缩放约束", "scale_constraint_check", "scale_offset_check")
        ]
        
        # 创建约束类型和偏移复选框
        for row, (label, constraint_attr, offset_attr) in enumerate(constraint_types):
            # 约束类型
            setattr(self, constraint_attr, QCheckBox(label))
            constraint_check = getattr(self, constraint_attr)
            constraint_check.setMinimumWidth(80)  # 确保有足够宽度显示文字
            constraints_layout.addWidget(constraint_check, row, 0)
            
            # 如果是父子约束，默认选中
            if constraint_attr == "parent_constraint_check":
                constraint_check.setChecked(True)
            
            # 偏移设置
            setattr(self, offset_attr, QCheckBox("保持偏移"))
            offset_check = getattr(self, offset_attr)
            offset_check.setMinimumWidth(80)  # 确保有足够宽度显示文字
            constraints_layout.addWidget(offset_check, row, 1)

        constraints_group.setLayout(constraints_layout)
        fk_hierarchy_layout.addWidget(constraints_group)

        # 创建FK层级按钮 - 使其更醒目
        create_fk_hierarchy_button = DelayedToolTipButton("创建FK层级", "为选中的骨骼链创建FK控制器层级")
        create_fk_hierarchy_button.setMinimumHeight(30)  # 增加按钮高度
        create_fk_hierarchy_button.setStyleSheet("""
            QPushButton {
                background-color: #4d90fe; 
                color: white; 
                border-radius: 3px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c7ae6;
            }
            QPushButton:pressed {
                background-color: #356ac3;
            }
        """)
        create_fk_hierarchy_button.clicked.connect(self.create_fk_hierarchy)
        fk_hierarchy_layout.addWidget(create_fk_hierarchy_button)

        fk_hierarchy_group.setLayout(fk_hierarchy_layout)
        joint_ctrl_layout.addWidget(fk_hierarchy_group)

        joint_ctrl_group.setLayout(joint_ctrl_layout)
        scroll_layout.addWidget(joint_ctrl_group)

        # 分组与前缀设置
        group_prefix_group = CollapsibleGroupBox("分组与前缀设置")
        group_prefix_layout = QGridLayout()
        group_prefix_layout.setSpacing(5)
        group_prefix_layout.addWidget(QLabel("自定义前缀："), 0, 0)
        self.prefix_text = QLineEdit()
        self.prefix_text.textChanged.connect(self.update_custom_prefix)
        group_prefix_layout.addWidget(self.prefix_text, 0, 1)
        group_prefix_layout.addWidget(QLabel("预设前缀："), 1, 0)
        self.prefix_combo = QComboBox()
        self.prefix_combo.addItems(["zero", "driven", "connect", "offset", "space"])
        self.prefix_combo.currentTextChanged.connect(self.update_group_prefix)
        group_prefix_layout.addWidget(self.prefix_combo, 1, 1)
        group_prefix_layout.addWidget(QLabel("分组与层级："), 2, 0)
        self.remove_prefix_check = QCheckBox("去除前缀")
        self.remove_prefix_check.setChecked(True)
        self.remove_prefix_check.stateChanged.connect(self.toggle_remove_prefix)
        group_prefix_layout.addWidget(self.remove_prefix_check, 2, 1)
        self.use_existing_suffix_check = QCheckBox("使用现有后缀")
        self.use_existing_suffix_check.setChecked(True)
        self.use_existing_suffix_check.stateChanged.connect(self.toggle_use_existing_suffix)
        group_prefix_layout.addWidget(self.use_existing_suffix_check, 3, 1)
        self.freeze_scale_check = QCheckBox("冻结缩放")
        self.freeze_scale_check.setChecked(True)
        self.freeze_scale_check.stateChanged.connect(self.toggle_freeze_scale)
        group_prefix_layout.addWidget(self.freeze_scale_check, 4, 1)
        create_group_button = DelayedToolTipButton("创建组", "为选中的物体创建组并匹配变换")
        create_group_button.clicked.connect(self.create_group_for_selected)
        group_prefix_layout.addWidget(create_group_button, 5, 0, 1, 2)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        group_prefix_layout.addWidget(separator, 6, 0, 1, 2)

        # 创建控制器层级操作按钮 - 双排布局，平均分布
        # 第一行：添加控制器层级、控制器层级次级控制器
        controller_first_row_layout = QHBoxLayout()
        controller_first_row_layout.setSpacing(5)  # 设置按钮间距
        add_hierarchy_button = DelayedToolTipButton("添加控制器层级", "为选中的控制器添加层级结构")
        add_hierarchy_button.clicked.connect(self.add_controller_hierarchy)
        controller_first_row_layout.addWidget(add_hierarchy_button, 1)  # 使用stretch factor平均分布
        
        ctrl_connect_button = DelayedToolTipButton("控制器层级次级控制器", "为选中的控制器创建层级结构和次级控制器")
        ctrl_connect_button.clicked.connect(self.open_ctrl_connect)
        controller_first_row_layout.addWidget(ctrl_connect_button, 1)  # 使用stretch factor平均分布
        
        # 第二行：选定物体创建控制器、基础层级
        controller_second_row_layout = QHBoxLayout()
        controller_second_row_layout.setSpacing(5)  # 设置按钮间距
        create_obj_ctrl_button = DelayedToolTipButton("选定物体创建控制器", "为选定的物体创建控制器并匹配变换")
        create_obj_ctrl_button.clicked.connect(self.open_object_creation_controller)
        controller_second_row_layout.addWidget(create_obj_ctrl_button, 1)  # 使用stretch factor平均分布
        
        create_controller_hierarchy_button = DelayedToolTipButton("基础层级", "创建包含控制器和层级结构的骨骼系统")
        create_controller_hierarchy_button.clicked.connect(self.open_create_controller_hierarchy)
        controller_second_row_layout.addWidget(create_controller_hierarchy_button, 1)  # 使用stretch factor平均分布
        
        # 将两行布局添加到主布局中
        group_prefix_layout.addLayout(controller_first_row_layout, 7, 0, 1, 2)
        group_prefix_layout.addLayout(controller_second_row_layout, 8, 0, 1, 2)
        # 添加父子物体创建折叠组件到分组与前缀设置中
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet(separator_style)
        group_prefix_layout.addWidget(separator2, 9, 0, 1, 2)
        
        # 创建父子物体创建折叠组件
        parent_child_group = CollapsibleGroupBox("父子物体创建")
        parent_child_layout = QVBoxLayout()
        parent_child_layout.setSpacing(5)
        
        # 添加创建类型选择复选框
        self.create_locator_check = QCheckBox("创建Locator")
        self.create_locator_check.setChecked(True)
        self.create_locator_check.setToolTip("勾选创建Locator，取消勾选创建空组")
        parent_child_layout.addWidget(self.create_locator_check)
        
        create_under_button = DelayedToolTipButton("在物体层级下创建", "为选中物体在其层级下创建locator或空组，匹配变换并保持层级结构")
        create_under_button.clicked.connect(self.create_object_under)
        parent_child_layout.addWidget(create_under_button)
        
        create_above_button = DelayedToolTipButton("在物体层级上创建", "为选中物体在其层级上创建locator或空组，匹配变换并保持层级结构")
        create_above_button.clicked.connect(self.create_object_above)
        parent_child_layout.addWidget(create_above_button)
        
        parent_child_group.setLayout(parent_child_layout)
        group_prefix_layout.addWidget(parent_child_group, 16, 0, 1, 2)
        
        group_prefix_group.setLayout(group_prefix_layout)
        scroll_layout.addWidget(group_prefix_group)

        # 创建Tag并选择
        tag_group = CollapsibleGroupBox("创建Tag并选择")
        tag_layout = QVBoxLayout()
        tag_layout.setSpacing(5)

        tag_name_layout = QHBoxLayout()
        tag_name_label = QLabel("Tag 名称:")
        tag_name_layout.addWidget(tag_name_label)
        self.tag_name_input = QLineEdit("isCtrl")
        tag_name_layout.addWidget(self.tag_name_input)
        tag_layout.addLayout(tag_name_layout)

        # 第一行：添加Tag、选择有tag的物体
        tag_first_row_layout = QHBoxLayout()
        tag_first_row_layout.setSpacing(5)  # 设置按钮间距
        
        add_tag_button = DelayedToolTipButton("添加Tag", "为选中的物体添加指定的 Tag 属性")
        add_tag_button.clicked.connect(self.add_tag_attribute)
        tag_first_row_layout.addWidget(add_tag_button, 1)  # stretch factor = 1

        select_tag_button = DelayedToolTipButton("选择有tag的物体", "选择场景中具有指定 Tag 的所有物体")
        select_tag_button.clicked.connect(self.select_objects_with_tag)
        tag_first_row_layout.addWidget(select_tag_button, 1)  # stretch factor = 1
        
        tag_layout.addLayout(tag_first_row_layout)
        
        # 第二行：删除Tag、识别选中物体的Tag
        tag_second_row_layout = QHBoxLayout()
        tag_second_row_layout.setSpacing(5)  # 设置按钮间距

        remove_tag_button = DelayedToolTipButton("删除 Tag", "从选中的物体上删除指定的 Tag 属性")
        remove_tag_button.clicked.connect(self.remove_tag_attribute)
        tag_second_row_layout.addWidget(remove_tag_button, 1)  # stretch factor = 1

        identify_tag_button = DelayedToolTipButton("识别选中物体的 Tag", "识别并列出选中物体的所有布尔 Tag")
        identify_tag_button.clicked.connect(self.identify_object_tags)
        tag_second_row_layout.addWidget(identify_tag_button, 1)  # stretch factor = 1
        
        tag_layout.addLayout(tag_second_row_layout)

        tag_history_label = QLabel("历史 Tag 记录:")
        tag_layout.addWidget(tag_history_label)
        self.tag_history_combo = QComboBox()
        self.tag_history_combo.addItem("无记录")
        self.tag_history_combo.currentTextChanged.connect(self.on_tag_history_selected)
        tag_layout.addWidget(self.tag_history_combo)

        clear_history_button = DelayedToolTipButton("清空历史 Tag 记录", "清空所有保存的历史 Tag 记录")
        clear_history_button.clicked.connect(self.clear_tag_history)
        tag_layout.addWidget(clear_history_button)

        tag_layout.addSpacing(5)

        tag_group.setLayout(tag_layout)
        scroll_layout.addWidget(tag_group)

        # 添加独立的骨骼Tag组件
        joint_tag_group = CollapsibleGroupBox("骨骼Tag")
        joint_tag_layout = QVBoxLayout()
        joint_tag_layout.setSpacing(5)
        joint_tag_v1_button = DelayedToolTipButton("骨骼绘制标签", "切换骨骼的绘制标签显示开关，优先对选中骨骼操作，无选择时对所有骨骼操作")
        joint_tag_v1_button.clicked.connect(self.open_joint_tag_v1)
        joint_tag_layout.addWidget(joint_tag_v1_button)
        joint_tag_v2_button = DelayedToolTipButton("通用骨骼Tag", "运行 joint_TagV2.py，为场景中所有关节添加通用标签")
        joint_tag_v2_button.clicked.connect(self.open_joint_tag_v2)
        joint_tag_layout.addWidget(joint_tag_v2_button)
        joint_tag_group.setLayout(joint_tag_layout)
        scroll_layout.addWidget(joint_tag_group)



    @with_undo_support
    def scale_cv_handles_up(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = self.scale_factor_input.value()
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        scaled_vector = [v * scale_factor for v in vector]
                        new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                        cmds.xform(cv, worldSpace=True, translation=new_pos)
                print(f"已将控制器 '{ctrl}' 的控制顶点按倍率 {scale_factor} 放大")
            else:
                print(f"物体 '{ctrl}' 不是 NURBS 曲线，跳过调整")

    @with_undo_support
    def scale_cv_handles_down(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = 1.0 / self.scale_factor_input.value()
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        scaled_vector = [v * scale_factor for v in vector]
                        new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                        cmds.xform(cv, worldSpace=True, translation=new_pos)
                print(f"已将控制器 '{ctrl}' 的控制顶点按倍率 {1.0 / scale_factor} 缩小")
            else:
                print(f"物体 '{ctrl}' 不是 NURBS 曲线，跳过调整")

    def get_cv_handle_scale(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            print("未选择任何控制器，返回默认值 50")
            return 50.0

        total_scale = 0.0
        count = 0
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        magnitude = math.sqrt(sum(v * v for v in vector))
                        total_scale += magnitude * 50.0
                        count += 1

        if count > 0:
            avg_scale = total_scale / count
            print(f"计算得到控制器平均缩放值: {avg_scale}")
            return avg_scale
        else:
            print("未找到任何控制顶点，返回默认值 50")
            return 50.0

    @with_undo_support
    def apply_curve_width(self):
        """为选中的曲线设置指定的粗细值"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return
        
        width_value = self.curve_width_input.value()
        
        try:
            # 遍历所有选择的对象，查找它们的shape节点
            shape_nodes = []
            for obj in selected_objects:
                # 检查对象是否为transform节点
                if cmds.objectType(obj) == 'transform':
                    # 获取transform下的所有shape节点
                    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
                    shape_nodes.extend(shapes)
                # 如果对象本身就是shape节点
                elif cmds.objectType(obj, isAType='shape'):
                    shape_nodes.append(obj)
            
            # 设置所有shape节点的lineWidth属性
            for shape in shape_nodes:
                if cmds.objExists(f'{shape}.lineWidth'):
                    cmds.setAttr(f'{shape}.lineWidth', width_value)
                    print(f"已将 '{shape}' 的线宽设置为 {width_value}")
        except Exception as e:
            cmds.warning(f"设置曲线粗细失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    @with_undo_support
    def combine_selected_curves(self):
        """结合选中的曲线"""
        combine_file = os.path.join(TOOL_DIR, "结合曲线.py")
        if not os.path.exists(combine_file):
            cmds.warning(f"未找到 结合曲线.py 文件: {combine_file}")
            return

        try:
            import importlib.util
            module_name = "结合曲线"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                combine_module = sys.modules[module_name]
                importlib.reload(combine_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, combine_file)
                combine_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = combine_module
                spec.loader.exec_module(combine_module)

            # 调用函数
            if hasattr(combine_module, "selected_curves_combine"):
                combine_module.selected_curves_combine()
                print("已运行 结合曲线.py 中的 selected_curves_combine 函数，结合选中的曲线")
            else:
                cmds.warning("结合曲线.py 中未找到 selected_curves_combine 函数")
        except Exception as e:
            cmds.warning(f"运行 结合曲线.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    @with_undo_support
    def separate_selected_curves(self):
        """拆分选中的曲线"""
        separate_file = os.path.join(TOOL_DIR, "拆分曲线.py")
        if not os.path.exists(separate_file):
            cmds.warning(f"未找到 拆分曲线.py 文件: {separate_file}")
            return

        try:
            import importlib.util
            module_name = "拆分曲线"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                separate_module = sys.modules[module_name]
                importlib.reload(separate_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, separate_file)
                separate_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = separate_module
                spec.loader.exec_module(separate_module)

            # 调用函数
            if hasattr(separate_module, "selected_curves_separate"):
                separate_module.selected_curves_separate()
                print("已运行 拆分曲线.py 中的 selected_curves_separate 函数，拆分选中的曲线")
            else:
                cmds.warning("拆分曲线.py 中未找到 selected_curves_separate 函数")
        except Exception as e:
            cmds.warning(f"运行 拆分曲线.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def update_color_preview(self):
        # 创建一个属性动画用于颜色变换
        animation = QPropertyAnimation(self.color_preview, b"palette")
        animation.setDuration(300)  # 300毫秒的动画时长
        animation.setEasingCurve(QEasingCurve.InOutQuad)

        # 获取当前调色板
        old_palette = self.color_preview.palette()
        new_palette = QPalette(old_palette)

        # 设置新的颜色
        new_color = QColor.fromRgbF(*self.color_rgb)
        new_palette.setColor(QPalette.Window, new_color)

        # 设置动画属性
        animation.setStartValue(old_palette)
        animation.setEndValue(new_palette)

        # 获取RGB值的十六进制表示
        hex_color = new_color.name().upper()
        
        # 计算亮度以确定文字颜色
        brightness = (0.299 * new_color.red() + 0.587 * new_color.green() + 0.114 * new_color.blue()) / 255
        text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
        
        # 设置样式以显示颜色和颜色值
        self.color_preview.setStyleSheet(f"""
            background-color: {hex_color}; 
            border: 1px solid #666666; 
            border-radius: 5px;
            color: {text_color};
            font-size: 10px;
            text-align: center;
            padding: 2px;
        """)
        
        # 显示RGB值
        self.color_preview.setText(f"{hex_color}")
        
        # 添加工具提示显示RGB值
        r, g, b = [int(c * 255) for c in self.color_rgb]
        self.color_preview.setToolTip(f"RGB: {r}, {g}, {b}\n点击修改颜色")
        
        # 启动动画
        self.color_preview.setAutoFillBackground(True)
        
        # 创建大小变化的动画效果
        size_animation = QPropertyAnimation(self.color_preview, b"minimumSize")
        size_animation.setDuration(150)
        size_animation.setStartValue(QSize(80, 20))
        size_animation.setEndValue(QSize(84, 22))
        size_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        size_animation2 = QPropertyAnimation(self.color_preview, b"minimumSize")
        size_animation2.setDuration(150)
        size_animation2.setStartValue(QSize(84, 22))
        size_animation2.setEndValue(QSize(80, 20))
        size_animation2.setEasingCurve(QEasingCurve.InQuad)
        
        # 创建动画组
        animation_group = QSequentialAnimationGroup()
        animation_group.addAnimation(size_animation)
        animation_group.addAnimation(size_animation2)
        
        # 启动所有动画
        animation.start()
        animation_group.start()

    def update_tag_history_combo(self):
        self.tag_history_combo.clear()
        if not self.tag_history:
            self.tag_history_combo.addItem("无记录")
        else:
            self.tag_history_combo.addItems(self.tag_history)

    def generate_unique_name(self, base_name, start_index=1):
        index = start_index
        unique_name = f"{base_name}_{index:03d}"
        while cmds.objExists(unique_name):
            index += 1
            unique_name = f"{base_name}_{index:03d}"
        return unique_name

    def get_color_index_from_name(self, name):
        name_lower = name.lower()
        if "_l_" in name_lower:
            return 6  # 蓝色（左侧）
        elif "_r_" in name_lower:
            return 13  # 红色（右侧）
        elif "_m_" in name_lower:
            return 17  # 黄色（中线）
        return None

    @with_undo_support
    def apply_color_index(self, obj, color_index):
        shapes = cmds.listRelatives(obj, shapes=True) or []
        for shape in shapes:
            cmds.setAttr(f"{shape}.overrideEnabled", 1)
            cmds.setAttr(f"{shape}.overrideRGBColors", 0)
            cmds.setAttr(f"{shape}.overrideColor", color_index)
        print(f"物体 '{obj}' 已应用颜色索引 {color_index}。")

    @with_undo_support
    def create_joint(self, prefix, name, side, index, translation, rotation, scale, orient="xyz", sec_axis_orient="yup",
                     preferred_angles=(0, 0, 0), joint_set=None):
        formatted_side = f"_{side}" if side and side.lower() != "none" else ""
        base_name = f"{prefix}{formatted_side}_{name}"
        joint_name = self.generate_unique_name(base_name, start_index=index or 1)

        cmds.select(clear=True)
        joint = cmds.joint(name=joint_name)
        cmds.joint(joint, edit=True, oj=orient, sao=sec_axis_orient, ch=True, zso=True)
        cmds.xform(joint, scale=scale, ws=True, a=True, translation=translation, rotation=rotation)
        cmds.setAttr(f"{joint}.preferredAngle", *preferred_angles)

        if joint_set:
            if not cmds.objExists(joint_set) or cmds.nodeType(joint_set) != "objectSet":
                joint_set = cmds.sets(name=joint_set, empty=True)
            cmds.sets(joint, edit=True, forceElement=joint_set)

        return joint_name

    @with_undo_support
    def create_custom_controller(self, name, side, index, size=1, color_rgb=(1.0, 1.0, 1.0),
                                 translation=(0, 0, 0), rotation=(0, 0, 0),
                                 controller_type="sphere"):
        formatted_side = f"_{side}" if side and side.lower() != "none" else ""
        base_name = f"ctrl{formatted_side}_{name}"
        ctrl_name = self.generate_unique_name(base_name, start_index=index or 1)

        # 添加调试输出
        print(f"DEBUG: controllers模块路径: {os.path.abspath(os.path.dirname(controller_shapes.__file__))}")
        print(f"DEBUG: controller_shapes模块包含的函数: {dir(controller_shapes)}")
        print(f"DEBUG: 尝试创建控制器类型: {controller_type}, 大小: {size}")
        
        # 使用外部模块创建控制器
        try:
            ctrl = controller_shapes.create_custom_controller(ctrl_name, controller_type, size)
            print(f"DEBUG: 控制器创建成功: {ctrl}")
        except Exception as e:
            print(f"ERROR: 创建控制器失败: {str(e)}")
            # 如果创建失败，使用默认的圆形控制器
            ctrl = cmds.circle(name=ctrl_name, radius=size, normal=(0, 1, 0))[0]
            print(f"DEBUG: 已改用默认圆形控制器: {ctrl}")
        
        # 设置变换
        cmds.xform(ctrl, translation=translation, rotation=rotation, worldSpace=True)
        
        # 应用颜色
        controller_shapes.apply_color_to_controller(ctrl, color_rgb)
        
        # 重命名形状节点
        controller_shapes.rename_controller_shape(ctrl)

        # 处理颜色索引（如果有）
        color_index = self.get_color_index_from_name(ctrl_name)
        if color_index is not None:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                cmds.setAttr(f"{shape}.overrideColor", color_index)
            print(f"物体 '{ctrl_name}' 已应用颜色索引 {color_index}。")

        return ctrl_name

    @with_undo_support
    def create_joint_and_controller(self):
        """
        创建关节和控制器组件，支持逗号分隔的侧面输入（例如 "l,r,m"），并根据数量生成对应组件。
        """
        name = self.name_text.text()
        side_input = self.side_text.text()  # 获取侧面输入，例如 "l,r,m"
        count = self.count_spin.value()
        size = self.size_spin.value()
        joint_set = "Skin_Joints_Set"
        
        # 如果启用了根据选择物体数量创建功能，则覆盖count值
        if self.use_selection_count_flag:
            selected_objects = cmds.ls(selection=True)
            if selected_objects:
                count = len(selected_objects)
                print(f"根据选择物体数量创建: 选择了{count}个物体，将创建{count}个关节/控制器")
            else:
                print("根据选择物体数量创建: 未选择任何物体，使用默认数量")
        else:
            selected_objects = cmds.ls(selection=True)
        
        # 检查是否启用物体名称识别
        use_auto_naming = self.auto_name_from_joint_check.isChecked()
        ignore_suffix = self.ignore_suffix_check.isChecked()
        
        # 如果启用了物体名称识别且选择了物体，则从物体名称解析名称和侧面
        selected_objects = cmds.ls(selection=True)
        target_obj = selected_objects[0] if selected_objects else None
        
        if use_auto_naming and target_obj:
            # 从物体名称解析控制器名称（支持任意类型的Maya物体）
            parsed_name = self.parse_object_name(target_obj, ignore_suffix)
            
            # 检查解析的名称是否包含侧面信息
            if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                # 包含侧面信息，分离侧面和名称
                side_part, name_part = parsed_name.split("_", 1)
                name = name_part
                side_input = side_part.lower()
                print(f"从物体名称识别: 物体='{target_obj}', 名称='{name}', 侧面='{side_input}'")
            else:
                # 不包含侧面信息，使用解析的名称作为控制器名称
                name = parsed_name
                print(f"从物体名称识别: 物体='{target_obj}', 名称='{name}'")

        if not name:
            cmds.warning("请输入名称！")
            return

        # 解析侧面输入，支持逗号分隔
        sides = [s.strip() for s in side_input.split(',')] if side_input else ["none"]
        created_groups = []

        self.custom_group_name = self.custom_group_input.text().strip() if self.enable_custom_group else ""

        # 为每个侧面创建指定数量的组件
        for side in sides:
            # 转换为小写并验证侧面输入是否有效
            side = side.lower()
            if side and side not in ["l", "r", "m", "none"]:
                cmds.warning(f"无效的侧面输入 '{side}'，应为 l, r, m 或 none，已跳过")
                continue

            for i in range(count):
                # 如果启用了根据选择物体数量创建功能且启用了识别物体名称，使用对应物体的名称
                if self.use_selection_count_flag and selected_objects and i < len(selected_objects) and use_auto_naming:
                    current_object = selected_objects[i]
                    # 使用parse_object_name方法解析物体名称
                    parsed_name = self.parse_object_name(current_object, self.ignore_suffix_check.isChecked())
                    
                    # 检查解析的名称是否包含侧面信息
                    if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                        # 包含侧面信息，分离侧面和名称
                        object_side, object_name = parsed_name.split("_", 1)
                        base_name = object_name
                        current_side = object_side.lower()
                        formatted_side = f"_{current_side}"
                        print(f"从物体名称识别: 物体='{current_object}', 名称='{base_name}', 侧面='{current_side}'")
                    else:
                        # 不包含侧面信息，使用解析的名称作为基础名称，保持原侧面
                        base_name = parsed_name
                        formatted_side = f"_{side}" if side != "none" else ""
                        print(f"从物体名称识别: 物体='{current_object}', 名称='{base_name}'")
                else:
                    # 使用统一的名称和侧面
                    base_name = f"{name}"
                    formatted_side = f"_{side}" if side != "none" else ""

                # 生成唯一的 zero 组名称并提取后缀
                zero_base_name = f"zero{formatted_side}_{base_name}"
                zero_group_name = self.generate_unique_name(zero_base_name, start_index=i + 1)
                # 提取后缀（例如 "_001"）
                suffix = re.search(r"_(\d+)$", zero_group_name).group(0) if re.search(r"_(\d+)$",
                                                                                      zero_group_name) else f"_{i + 1:03d}"

                ctrl = None
                joint = None
                last_group = None

                # 创建层级结构，所有层级使用相同的后缀
                if self.use_hierarchy_logic:
                    zero_group = cmds.group(name=zero_group_name, empty=True)
                    driven_group_name = f"driven{formatted_side}_{base_name}{suffix}"
                    connect_group_name = f"connect{formatted_side}_{base_name}{suffix}"
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"

                    driven_group = cmds.group(name=driven_group_name, empty=True, parent=zero_group)
                    connect_group = cmds.group(name=connect_group_name, empty=True, parent=driven_group)
                    offset_group = cmds.group(name=offset_group_name, empty=True, parent=connect_group)
                    last_group = offset_group
                else:
                    zero_group = cmds.group(name=zero_group_name, empty=True)
                    offset_group_name = f"grpOffset{formatted_side}_{base_name}{suffix}"
                    offset_group = cmds.group(name=offset_group_name, empty=True, parent=zero_group)
                    last_group = offset_group

                # 创建控制器或空组，使用相同的后缀
                if self.create_controller_flag:
                    ctrl_base = f"ctrl{formatted_side}_{base_name}"
                    ctrl_name = f"{ctrl_base}{suffix}"
                    ctrl = self.create_custom_controller(
                        name=name,
                        side=side,
                        index=None,
                        size=size,
                        color_rgb=self.color_rgb,
                        translation=(0, 0, 0),
                        controller_type=self.controller_type
                    )
                    ctrl = cmds.rename(ctrl, ctrl_name)  # 重命名以确保后缀一致
                    cmds.parent(ctrl, offset_group)
                    
                    # 确保控制器的旋转顺序是可见和可关键帧的
                    cmds.setAttr(f"{ctrl}.rotateOrder", channelBox=True, keyable=True)

                    # 如果启用了子控制器选项，创建子控制器和输出组
                    if self.create_sub_controller_flag:
                        # 使用单独方法创建子控制器
                        sub_ctrl_name, output_name = self.create_sub_controller(
                            parent_ctrl=ctrl,
                            name=name,
                            formatted_side=formatted_side,
                            suffix=suffix
                        )

                        if sub_ctrl_name and output_name:
                            # 层级关系和属性连接已在create_sub_controller方法中完成
                            print(f"已设置控制器层级: '{sub_ctrl_name}' 和 '{output_name}' 作为 '{ctrl}' 的子级")

                elif not self.create_joint_flag and not self.create_controller_flag:
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
                    ctrl = cmds.group(name=ctrl_name, empty=True)
                    cmds.parent(ctrl, offset_group)
                elif self.create_joint_flag and not self.use_hierarchy_logic:
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
                    ctrl = cmds.group(name=ctrl_name, empty=True)
                    cmds.parent(ctrl, offset_group)

                # 创建关节，使用相同的后缀
                if self.create_joint_flag:
                    joint_base = f"jntSkin{formatted_side}_{base_name}"
                    joint_name = f"{joint_base}{suffix}"
                    joint = self.create_joint(
                        prefix="jntSkin",
                        name=name,
                        side=side,
                        index=None,
                        translation=(0, 0, 0),
                        rotation=(0, 0, 0),
                        scale=(1, 1, 1),
                        orient="xyz",
                        sec_axis_orient="yup",
                        preferred_angles=(0, 0, 0),
                        joint_set=joint_set
                    )
                    joint = cmds.rename(joint, joint_name)  # 重命名以确保后缀一致

                    # 如果创建了控制器且创建了子控制器，则将关节父级到output组
                    if ctrl and self.create_controller_flag and self.create_sub_controller_flag:
                        # 找到与控制器关联的output组
                        output_name = ctrl.replace(f"ctrl{formatted_side}_", f"output{formatted_side}_")
                        if cmds.objExists(output_name):
                            # 确保output组是ctrl的子级
                            if not cmds.listRelatives(output_name, parent=True) or cmds.listRelatives(output_name, parent=True)[0] != ctrl:
                                cmds.parent(output_name, ctrl)
                                print(f"已将输出组 '{output_name}' 父级到控制器 '{ctrl}'")
                            
                            # 将关节放到output组下
                            cmds.parent(joint, output_name)
                            print(f"已将关节 '{joint}' 父级到输出组 '{output_name}'")
                        else:
                            cmds.parent(joint, ctrl)
                    elif ctrl:  # 如果 ctrl 存在（控制器或空组），关节父级到 ctrl
                        cmds.parent(joint, ctrl)
                    else:  # 否则父级到 offset_group
                        cmds.parent(joint, offset_group)

                created_groups.append(zero_group)
                
                # 如果启用了根据选择物体数量创建功能，立即匹配到对应的选择物体
                if self.use_selection_count_flag and selected_objects:
                    # 计算当前组件对应的选择物体索引
                    current_index = len(created_groups) - 1
                    if current_index < len(selected_objects):
                        target_transform = selected_objects[current_index]
                        # 保存当前选择
                        current_selection = cmds.ls(selection=True)
                        
                        # 清除选择并选择零组
                        cmds.select(clear=True)
                        cmds.select(zero_group)
                        
                        # 执行匹配变换
                        cmds.matchTransform(zero_group, target_transform,
                                            pos=self.match_position,
                                            rot=self.match_rotation,
                                            scl=self.match_scale)
                        
                        # 恢复之前的选择状态
                        cmds.select(clear=True)
                        if current_selection:
                            cmds.select(current_selection)
                        
                        print(f"已将组件 '{zero_group}' 匹配到物体 '{target_transform}' 的变换")

        # 处理自定义组
        if self.enable_custom_group and self.custom_group_name:
            custom_group = self.custom_group_name
            if not cmds.objExists(custom_group):
                custom_group = cmds.group(empty=True, name=custom_group)
                print(f"已创建自定义组 '{custom_group}'")
            for zero_group in created_groups:
                cmds.parent(zero_group, custom_group)
                print(f"已将 '{zero_group}' 父级到自定义组 '{custom_group}'")

        # 在所有组件创建完成后，将zero组匹配到目标物体
        # 如果启用了根据选择物体数量创建功能，则跳过统一匹配（已在创建过程中完成个别匹配）
        if target_obj and not (self.use_selection_count_flag and selected_objects):
            for group in created_groups:
                # 保存当前选择
                current_selection = cmds.ls(selection=True)
                
                # 清除选择并选择零组
                cmds.select(clear=True)
                cmds.select(group)
                
                # 执行匹配变换
                cmds.matchTransform(group, target_obj,
                                    pos=self.match_position,
                                    rot=self.match_rotation,
                                    scl=self.match_scale)
                
                # 恢复之前的选择状态
                cmds.select(clear=True)
                if current_selection:
                    cmds.select(current_selection)
            
            print(f"已将 {len(created_groups)} 个 zero 组匹配到 '{target_obj}' 的变换。")
        elif self.use_selection_count_flag and selected_objects:
            print(f"已完成根据选择物体数量创建: 每个组件已匹配到对应选择物体的变换。")

        # 处理新的层级关系选项
        if selected_objects and (self.controller_parent_original_check.isChecked() or self.original_parent_controller_check.isChecked()):
            self.apply_hierarchy_relationships(created_groups, selected_objects)
        
        print(
            f"已完成创建：共 {len(sides)} 个侧面 ({','.join(sides)})，每个侧面 {count} 个组件，总计 {len(created_groups)} 个组")

    def apply_hierarchy_relationships(self, created_groups, selected_objects):
        """
        应用新的层级关系选项
        """
        controller_parent_original = self.controller_parent_original_check.isChecked()
        original_parent_controller = self.original_parent_controller_check.isChecked()
        
        # 如果两个选项都选中，给出警告并优先使用第一个选项
        if controller_parent_original and original_parent_controller:
            cmds.warning("两个层级关系选项都被选中，将优先使用'控制器作为原物体父级'选项")
            original_parent_controller = False
        
        for i, zero_group in enumerate(created_groups):
            if i < len(selected_objects):
                original_object = selected_objects[i]
                
                # 查找与zero_group相关的控制器
                controller = self.find_controller_in_hierarchy(zero_group)
                
                if controller and cmds.objExists(original_object):
                    if controller_parent_original:
                        # 控制器作为原物体父级：原物体成为控制器的子级
                        try:
                            cmds.parent(original_object, controller)
                            print(f"层级关系: 已将原物体 '{original_object}' 父级到控制器 '{controller}'")
                        except Exception as e:
                            print(f"警告: 无法将 '{original_object}' 父级到 '{controller}': {e}")
                    
                    elif original_parent_controller:
                        # 原物体作为控制器父级：控制器成为原物体的子级
                        try:
                            cmds.parent(zero_group, original_object)
                            print(f"层级关系: 已将控制器组 '{zero_group}' 父级到原物体 '{original_object}'")
                        except Exception as e:
                            print(f"警告: 无法将 '{zero_group}' 父级到 '{original_object}': {e}")
    
    def find_controller_in_hierarchy(self, zero_group):
        """
        在层级结构中查找控制器
        """
        # 遍历zero_group的所有子级，查找控制器
        all_children = cmds.listRelatives(zero_group, allDescendents=True, type='transform') or []
        
        for child in all_children:
            if child.startswith('ctrl') and not child.startswith('ctrl_sub'):
                return child
        
        return None

    def update_controller_type(self, selected_type):
        type_map = {
            "球形 (Sphere)": "sphere", "立方体 (Cube)": "cube", "圆形 (Circle)": "circle",
            "箭头 (Arrow)": "arrow", "齿轮 (Gear)": "gear", "圆锥 (Cone)": "cone",
            "十字 (Cross)": "cross", "钻石 (Diamond)": "diamond", "矩形 (Rectangle)": "rectangle",
            "正方形 (Square)": "square"
        }
        self.controller_type = type_map.get(selected_type, "sphere")
        print(f"控制器类型已更新为: {self.controller_type}")

    def toggle_create_joint(self, state):
        self.create_joint_flag = state == Qt.Checked
        print(f"创建关节: {self.create_joint_flag}")

    def toggle_custom_group(self, state):
        self.enable_custom_group = state == Qt.Checked
        self.custom_group_input.setEnabled(self.enable_custom_group)
        print(f"启用自定义组: {self.enable_custom_group}")

    def toggle_create_controller(self, state):
        self.create_controller_flag = state == Qt.Checked
        print(f"创建控制器: {self.create_controller_flag}")
        # 如果控制器被禁用，子控制器也应该被禁用
        if not self.create_controller_flag:
            self.create_sub_controller_check.setChecked(False)
            self.create_sub_controller_check.setEnabled(False)
        else:
            self.create_sub_controller_check.setEnabled(True)

    def toggle_create_sub_controller(self, state):
        self.create_sub_controller_flag = state == Qt.Checked
        print(f"创建子控制器: {self.create_sub_controller_flag}")
    
    def toggle_controller_parent_original(self, state):
        """切换控制器作为原物体父级选项"""
        if state == 2:  # 选中状态
            self.original_parent_controller_check.setChecked(False)
    
    def toggle_original_parent_controller(self, state):
        """切换原物体作为控制器父级选项"""
        if state == 2:  # 选中状态
            self.controller_parent_original_check.setChecked(False)

    # def toggle_use_selection_count(self, state):
    #     self.use_selection_count_flag = state == Qt.Checked
    #     print(f"根据选择物体数量创建: {self.use_selection_count_flag}")

    def show_color_dialog(self):
        # 创建颜色对话框
        color_dialog = QColorDialog(QColor.fromRgbF(*self.color_rgb), self)
        
        # 设置对话框标题
        color_dialog.setWindowTitle("选择控制器颜色")
        
        # 启用自定义颜色并显示颜色代码编辑框
        color_dialog.setOptions(QColorDialog.ShowAlphaChannel | QColorDialog.DontUseNativeDialog)
        
        # 添加淡入淡出效果
        opacity_effect = QGraphicsOpacityEffect(color_dialog)
        color_dialog.setGraphicsEffect(opacity_effect)

        # 创建淡入动画
        fade_in = QPropertyAnimation(opacity_effect, b"opacity")
        fade_in.setDuration(250)  # 250毫秒
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InQuad)

        # 显示对话框前开始淡入动画
        fade_in.start()
        
        # 启用RGB和HSV颜色选择
        color_dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        
        # 添加常用或预设颜色列表
        common_colors = [
            QColor(255, 0, 0),      # 红色
            QColor(0, 0, 255),      # 蓝色
            QColor(255, 255, 0),    # 黄色
            QColor(0, 255, 0),      # 绿色
            QColor(255, 128, 0),    # 橙色
            QColor(128, 0, 128),    # 紫色
            QColor(0, 255, 255),    # 青色
            QColor(255, 0, 255),    # 品红色
            QColor(128, 128, 128),  # 灰色
            QColor(255, 255, 255),  # 白色
        ]
        color_dialog.setCustomColor(0, common_colors[0].rgb())
        color_dialog.setCustomColor(1, common_colors[1].rgb())
        color_dialog.setCustomColor(2, common_colors[2].rgb())
        color_dialog.setCustomColor(3, common_colors[3].rgb())
        color_dialog.setCustomColor(4, common_colors[4].rgb())
        color_dialog.setCustomColor(5, common_colors[5].rgb())
        color_dialog.setCustomColor(6, common_colors[6].rgb())
        color_dialog.setCustomColor(7, common_colors[7].rgb())
        color_dialog.setCustomColor(8, common_colors[8].rgb())
        color_dialog.setCustomColor(9, common_colors[9].rgb())

        # 显示颜色对话框并等待用户选择
        if color_dialog.exec_():
            color = color_dialog.currentColor()
            if color.isValid():
                self.color_rgb = [color.redF(), color.greenF(), color.blueF()]
                self.update_color_preview()
                print(f"已选择颜色: RGB ({int(color.red())}, {int(color.green())}, {int(color.blue())})")
                
                # 返回到颜色预览动画
                return True
        return False

    def set_color(self, rgb):
        """设置当前颜色并更新预览
        
        参数:
            rgb (list): 包含三个浮点数的列表，范围0-1，代表RGB颜色
        """
        self.color_rgb = rgb
        self.update_color_preview()
        r, g, b = [int(c * 255) for c in rgb]
        print(f"已选择自定义颜色: RGB ({r}, {g}, {b})")
    
    def set_preset_color(self, rgb):
        """设置预设颜色并更新预览
        
        参数:
            rgb (tuple): 包含三个浮点数的元组，范围0-1，代表RGB颜色
        """
        self.color_rgb = list(rgb)
        self.update_color_preview()
        r, g, b = [int(c * 255) for c in rgb]
        print(f"已选择预设颜色: RGB ({r}, {g}, {b})")

    @with_undo_support
    def set_color_index(self, index):
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            self.apply_color_index(ctrl, index)

        index_to_rgb = {13: [1.0, 0.0, 0.0], 17: [1.0, 1.0, 0.0], 6: [0.0, 0.0, 1.0]}
        self.color_rgb = index_to_rgb.get(index, [1.0, 1.0, 1.0])
        self.update_color_preview()

    @with_undo_support
    def apply_color_to_controller(self):
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideRGBColors", 1)
                cmds.setAttr(f"{shape}.overrideColorRGB", *self.color_rgb)
            print(f"控制器 '{ctrl}' 已应用颜色 RGB {self.color_rgb}。")

    @with_undo_support
    def reset_color(self):
        """重置颜色功能：将绘制覆盖从RGB改为索引，然后关闭启用覆盖"""
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                # 首先将RGB颜色模式改为索引颜色模式
                cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                # 然后关闭启用覆盖
                cmds.setAttr(f"{shape}.overrideEnabled", 0)
            print(f"控制器 '{ctrl}' 已重置颜色覆盖。")
        
        print(f"已重置 {len(selected_controllers)} 个控制器的颜色覆盖。")

    @with_undo_support
    def apply_random_colors(self):
        """调用随机颜色功能"""
        try:
            # 使用load_module函数加载并执行随机颜色模块
            load_module("随机颜色", os.path.join(TOOL_DIR, "随机颜色.py"), "assign_random_colors")
        except Exception as e:
            cmds.warning(f"执行随机颜色功能时出错: {str(e)}")
            print(f"错误详情: {str(e)}")
    
    def open_gradient_color_tool(self):
        """打开渐变颜色工具"""
        try:
            # 使用load_module函数加载并执行渐变颜色模块
            load_module("渐变颜色", os.path.join(TOOL_DIR, "渐变颜色.py"), "show_gradient_color_tool")
        except Exception as e:
            cmds.warning(f"打开渐变颜色工具时出错: {str(e)}")
            print(f"错误详情: {str(e)}")

    def toggle_match_position(self, state):
        self.match_position = state == Qt.Checked

    def toggle_match_rotation(self, state):
        self.match_rotation = state == Qt.Checked

    def toggle_match_scale(self, state):
        self.match_scale = state == Qt.Checked
        print(f"匹配缩放: {self.match_scale}")

    def update_group_prefix(self, selected_prefix):
        self.group_prefix = selected_prefix

    def update_custom_prefix(self, text):
        if text:
            self.group_prefix = text
            print(f"自定义前缀已更新为: {self.group_prefix}")
        else:
            self.group_prefix = "zero"
            print("未输入前缀，使用默认前缀 'zero'。")

    def toggle_remove_prefix(self, state):
        self.remove_prefix = state == Qt.Checked

    def toggle_use_existing_suffix(self, state):
        self.use_existing_suffix = state == Qt.Checked

    def toggle_freeze_scale(self, state):
        self.freeze_scale = state == Qt.Checked

    def toggle_hierarchy_logic(self, state):
        self.use_hierarchy_logic = state == Qt.Checked
        print(f"使用层级组逻辑: {self.use_hierarchy_logic}")

    def clean_object_name(self, name):
        if self.remove_prefix:
            name_without_prefix = re.sub(r"^[a-zA-Z0-9]+_", "", name)
        else:
            name_without_prefix = name

        match = re.search(r"(_\d+)$", name_without_prefix)
        if match:
            name_without_prefix = name_without_prefix[:match.start()]

        return name_without_prefix
    
    def extract_suffix_from_name(self, name):
        """从物体名称中提取后缀，如果没有后缀则返回默认值_001"""
        # 匹配末尾的数字后缀，如_001, _123等
        match = re.search(r"(_\d+)$", name)
        if match:
            return match.group(1)  # 返回包含下划线的后缀，如"_001"
        else:
            return "_001"  # 默认后缀

    def get_existing_suffix(self, name):
        match = re.search(r"(_\d+)$", name)
        return match.group(1) if match else None

    def get_next_available_suffix(self, base_name, prefix):
        existing_groups = cmds.ls(f"{prefix}_{base_name}_*", type="transform")
        max_suffix = 0
        for group in existing_groups:
            match = re.search(r"_(\d+)$", group)
            if match:
                suffix_num = int(match.group(1))
                if suffix_num > max_suffix:
                    max_suffix = suffix_num
        return f"_{max_suffix + 1:03d}"

    @with_undo_support
    def freeze_object_scale(self, obj_name):
        if self.freeze_scale:
            scale = cmds.getAttr(f"{obj_name}.scale")[0]
            if scale != (1.0, 1.0, 1.0):
                cmds.makeIdentity(obj_name, apply=True, scale=True)
                print(f"物体 '{obj_name}' 的缩放已冻结。")

    @with_undo_support
    def create_group_for_selected(self):
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        for obj_name in selected_objects:
            try:
                if self.freeze_scale:
                    self.freeze_object_scale(obj_name)

                clean_name = self.clean_object_name(obj_name)
                suffix = self.get_existing_suffix(
                    obj_name) if self.use_existing_suffix else self.get_next_available_suffix(clean_name,
                                                                                              self.group_prefix)
                if not suffix and self.use_existing_suffix:
                    suffix = self.get_next_available_suffix(clean_name, self.group_prefix)

                base_group_name = f"{self.group_prefix}_{clean_name}" if self.group_prefix else clean_name
                group_name = f"{base_group_name}{suffix}"

                parent_obj = cmds.listRelatives(obj_name, parent=True)
                group = cmds.group(em=True, name=group_name)
                cmds.matchTransform(group, obj_name)
                cmds.parent(obj_name, group)

                color_index = self.get_color_index_from_name(group_name)
                if color_index is not None and cmds.objectType(obj_name, isType="nurbsCurve"):
                    self.apply_color_index(obj_name, color_index)

                if parent_obj:
                    cmds.parent(group, parent_obj[0])

                print(f"组 '{group_name}' 已创建，物体 '{obj_name}' 已添加到组中。")

            except Exception as e:
                print(f"为 '{obj_name}' 创建组时出错: {e}")

    @with_undo_support
    def create_object_under(self):
        """为选中物体在其层级下创建locator或空组，匹配变换并保持层级结构"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        create_locator = self.create_locator_check.isChecked()
        object_type = "locator" if create_locator else "空组"
        
        for obj_name in selected_objects:
            try:
                # 获取物体的子物体
                children = cmds.listRelatives(obj_name, children=True, type='transform') or []
                
                # 创建对象名称
                clean_name = self.clean_object_name(obj_name)
                # 提取原物体的后缀，如果有后缀就使用它的后缀，没有就默认_001
                suffix = self.extract_suffix_from_name(obj_name)
                
                if create_locator:
                    obj_name_new = f"loc_{clean_name}{suffix}"
                else:
                    obj_name_new = f"grp_{clean_name}{suffix}"
                
                # 确保名称唯一
                if cmds.objExists(obj_name_new):
                    counter = 1
                    base_name = obj_name_new.rsplit('_', 1)[0]  # 移除最后的数字部分
                    while cmds.objExists(f"{base_name}_{counter:03d}"):
                        counter += 1
                    obj_name_new = f"{base_name}_{counter:03d}"
                
                # 创建对象
                if create_locator:
                    created_obj = cmds.spaceLocator(name=obj_name_new)[0]
                else:
                    created_obj = cmds.group(name=obj_name_new, empty=True)
                
                # 匹配变换到物体
                cmds.matchTransform(created_obj, obj_name, position=True, rotation=True, scale=True)
                
                # 将对象放到物体层级下
                cmds.parent(created_obj, obj_name)
                
                print(f"已为物体 '{obj_name}' 在其层级下创建{object_type} '{created_obj}'")
                
            except Exception as e:
                print(f"为 '{obj_name}' 创建{object_type}时出错: {e}")

    @with_undo_support
    def create_object_above(self):
        """为选中物体在其层级上创建locator或空组，匹配变换并保持层级结构"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        create_locator = self.create_locator_check.isChecked()
        object_type = "locator" if create_locator else "空组"
        
        for obj_name in selected_objects:
            try:
                # 获取物体的父物体
                parent_obj = cmds.listRelatives(obj_name, parent=True)
                
                # 创建对象名称
                clean_name = self.clean_object_name(obj_name)
                # 提取原物体的后缀，如果有后缀就使用它的后缀，没有就默认_001
                suffix = self.extract_suffix_from_name(obj_name)
                
                if create_locator:
                    obj_name_new = f"loc_{clean_name}{suffix}"
                else:
                    obj_name_new = f"grp_{clean_name}{suffix}"
                
                # 确保名称唯一
                if cmds.objExists(obj_name_new):
                    counter = 1
                    base_name = obj_name_new.rsplit('_', 1)[0]  # 移除最后的数字部分
                    while cmds.objExists(f"{base_name}_{counter:03d}"):
                        counter += 1
                    obj_name_new = f"{base_name}_{counter:03d}"
                
                # 创建对象
                if create_locator:
                    created_obj = cmds.spaceLocator(name=obj_name_new)[0]
                else:
                    created_obj = cmds.group(name=obj_name_new, empty=True)
                
                # 匹配变换到物体
                cmds.matchTransform(created_obj, obj_name, position=True, rotation=True, scale=True)
                
                # 将物体父级到创建的对象
                cmds.parent(obj_name, created_obj)
                
                # 如果原物体有父物体，将创建的对象放到原父物体下
                if parent_obj:
                    cmds.parent(created_obj, parent_obj[0])
                
                print(f"已为物体 '{obj_name}' 在其层级上创建{object_type} '{created_obj}'")
                
            except Exception as e:
                print(f"为 '{obj_name}' 创建{object_type}时出错: {e}")

    @with_undo_support
    def add_controller_hierarchy(self):
        controllers = cmds.ls(selection=True)
        if not controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in controllers:
            zero = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'zero_'))
            driven = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'driven_'), parent=zero)
            connect = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'connect_'), parent=driven)
            offset = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'offset_'), parent=connect)

            cmds.matchTransform(zero, ctrl, position=True, rotation=True)
            cmds.parent(ctrl, offset)
            print(f"控制器 '{ctrl}' 的层级已创建。")

    @with_undo_support
    def add_tag_attribute(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        selected_objects = cmds.ls(sl=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected_objects:
            if not cmds.objExists(f"{obj}.{tag_name}"):
                cmds.addAttr(obj, ln=tag_name, at="bool", dv=1)
                cmds.setAttr(f"{obj}.{tag_name}", keyable=False, channelBox=False)
                print(f"已为物体 '{obj}' 添加 Tag '{tag_name}'")
                if tag_name not in self.tag_history:
                    self.tag_history.append(tag_name)
                    self.update_tag_history_combo()
            else:
                print(f"物体 '{obj}' 已存在 Tag '{tag_name}'，跳过添加")

    def select_objects_with_tag(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        all_objects = cmds.ls(transforms=True)
        tagged_objects = [obj for obj in all_objects if cmds.attributeQuery(tag_name, node=obj, exists=True)]

        if not tagged_objects:
            cmds.warning(f"场景中没有物体具有 Tag '{tag_name}'！")
            return

        cmds.select(tagged_objects, replace=True)
        print(f"已选择 {len(tagged_objects)} 个具有 Tag '{tag_name}' 的物体：{tagged_objects}")

    @with_undo_support
    def remove_tag_attribute(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        objects_with_tag = [obj for obj in selected_objects
                            if cmds.attributeQuery(tag_name, node=obj, exists=True)]

        if not objects_with_tag:
            cmds.warning(f"选中的物体中没有包含 Tag '{tag_name}'！")
            return

        for obj in objects_with_tag:
            cmds.deleteAttr(f"{obj}.{tag_name}")
            print(f"已从物体 '{obj}' 删除 Tag '{tag_name}'")

        print(f"已从 {len(objects_with_tag)} 个物体删除 Tag '{tag_name}'。")

    def identify_object_tags(self):
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        identified_tags = set()
        for obj in selected_objects:
            attrs = cmds.listAttr(obj, userDefined=True) or []
            for attr in attrs:
                if cmds.getAttr(f"{obj}.{attr}", type=True) == "bool":
                    identified_tags.add(attr)

        if not identified_tags:
            cmds.warning("选中的物体没有自定义布尔属性！")
            return

        new_tags = [tag for tag in identified_tags if tag not in self.tag_history]
        if new_tags:
            self.tag_history.extend(new_tags)
            self.update_tag_history_combo()
            print(f"已识别并添加 {len(new_tags)} 个新 Tag 到历史记录：{new_tags}")
        else:
            print(f"识别到 {len(identified_tags)} 个 Tag，但均已存在于历史记录中：{identified_tags}")

    def on_tag_history_selected(self, tag):
        if tag != "无记录":
            self.tag_name_input.setText(tag)
            print(f"已从历史记录选择 Tag '{tag}'")

    @with_undo_support
    def clear_tag_history(self):
        self.tag_history.clear()
        self.update_tag_history_combo()
        print("已清空所有历史 Tag 记录。")

    @with_undo_support
    def reset_position(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.translateX", 0)
            cmds.setAttr(f"{obj}.translateY", 0)
            cmds.setAttr(f"{obj}.translateZ", 0)
            print(f"物体 '{obj}' 的位移已归零。")

    @with_undo_support
    def reset_rotation(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.rotateX", 0)
            cmds.setAttr(f"{obj}.rotateY", 0)
            cmds.setAttr(f"{obj}.rotateZ", 0)
            print(f"物体 '{obj}' 的旋转已归零。")

    @with_undo_support
    def reset_scale(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.scaleX", 1)
            cmds.setAttr(f"{obj}.scaleY", 1)
            cmds.setAttr(f"{obj}.scaleZ", 1)
            print(f"物体 '{obj}' 的缩放已归一。")















    def open_create_curve_from_joints(self):
        create_curve_file = os.path.join(TOOL_DIR, "create_curve_from_joints.py")
        if not os.path.exists(create_curve_file):
            cmds.warning(f"未找到 create_curve_from_joints.py 文件: {create_curve_file}")
            return

        try:
            import importlib
            module_name = "create_curve_from_joints"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            curve_module = sys.modules[module_name]

            if hasattr(curve_module, "create_curve_ui"):
                curve_module.create_curve_ui()
                print("已运行 create_curve_from_joints.py 中的 create_curve_ui 函数，显示骨骼曲线工具窗口")
            else:
                cmds.warning("create_curve_from_joints.py 中未找到 create_curve_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 create_curve_from_joints.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")
            
    def open_curve_toolbox(self):
        """打开曲线工具箱，调用toolsForCur.mel中的CurTools()函数"""
        curve_toolbox_file = os.path.join(TOOL_DIR, "toolsForCur.mel")
        if not os.path.exists(curve_toolbox_file):
            cmds.warning(f"未找到 toolsForCur.mel 文件: {curve_toolbox_file}")
            return
            
        try:
            # 使用maya.mel模块执行MEL脚本中的CurTools函数
            mel.eval("source \"" + curve_toolbox_file.replace("\\", "/") + "\";")
            mel.eval("CurTools()")
            print("已运行 toolsForCur.mel 中的 CurTools 函数，显示曲线工具箱")
        except Exception as e:
            cmds.warning(f"执行 toolsForCur.mel 中的 CurTools 函数失败: {str(e)}")
            print(f"错误详情: {str(e)}")







    def open_toggle_local_rotation(self):
        toggle_file = os.path.join(TOOL_DIR, "toggle_local_rotation_display.py")
        if not os.path.exists(toggle_file):
            cmds.warning(f"未找到 toggle_local_rotation_display.py 文件: {toggle_file}")
            return

        try:
            import importlib
            module_name = "toggle_local_rotation_display"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            toggle_module = sys.modules[module_name]

            if hasattr(toggle_module, "create_ui"):
                toggle_module.create_ui()
                print("已运行 toggle_local_rotation_display.py 中的 create_ui 函数，显示局部旋转显示控制窗口")
            else:
                cmds.warning("toggle_local_rotation_display.py 中未找到 create_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 toggle_local_rotation_display.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def open_create_controller_hierarchy(self):
        controller_file = os.path.join(TOOL_DIR, "create_controller.py")
        if not os.path.exists(controller_file):
            cmds.warning(f"未找到 create_controller.py 文件: {controller_file}")
            return

        try:
            import importlib
            module_name = "create_controller"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            controller_module = sys.modules[module_name]

            if hasattr(controller_module, "create_hierarchy"):
                controller_module.create_hierarchy()
                print("已运行 create_controller.py 中的 create_hierarchy 函数，创建层级结构")
            else:
                cmds.warning("create_controller.py 中未找到 create_hierarchy 函数")
        except Exception as e:
            cmds.warning(f"加载 create_controller.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_ctrl_connect(self):
        ctrl_connect_file = os.path.join(TOOL_DIR, "ctrl_connect.py")
        if not os.path.exists(ctrl_connect_file):
            cmds.warning(f"未找到 ctrl_connect.py 文件: {ctrl_connect_file}")
            return

        try:
            module_name = "ctrl_connect"
            module = load_module(module_name, ctrl_connect_file)
            if module:
                print("已成功加载 ctrl_connect.py，为选中的控制器创建层级结构和次级控制器")
        except Exception as e:
            cmds.warning(f"加载 ctrl_connect.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_object_creation_controller(self):
        obj_ctrl_file = os.path.join(TOOL_DIR, "Object_creation_controller.py")
        if not os.path.exists(obj_ctrl_file):
            cmds.warning(f"未找到 Object_creation_controller.py 文件: {obj_ctrl_file}")
            return

        try:
            import importlib
            module_name = "Object_creation_controller"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            obj_ctrl_module = sys.modules[module_name]

            if hasattr(obj_ctrl_module, "create_controller_for_selected_objects"):
                obj_ctrl_module.create_controller_for_selected_objects("Circle")
                print("已运行 Object_creation_controller.py，为选定的物体创建控制器")
            else:
                cmds.warning("Object_creation_controller.py 中未找到 create_controller_for_selected_objects 函数")
        except Exception as e:
            cmds.warning(f"加载 Object_creation_controller.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_object_center_curve(self):
        script_file = os.path.join(TOOL_DIR, "Object_center_generation_curve.py")
        if not os.path.exists(script_file):
            cmds.warning(f"未找到 Object_center_generation_curve.py 文件: {script_file}")
            return

        try:
            import importlib
            module_name = "Object_center_generation_curve"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 Object_center_generation_curve.py，生成物体中心曲线")
        except Exception as e:
            cmds.warning(f"加载 Object_center_generation_curve.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_blend_shape_conversion(self):
        script_file = os.path.join(TOOL_DIR, "blendShape_conversion.py")
        if not os.path.exists(script_file):
            cmds.warning(f"未找到 blendShape_conversion.py 文件: {script_file}")
            return

        try:
            import importlib
            module_name = "blendShape_conversion"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            blend_module = sys.modules[module_name]
            if hasattr(blend_module, "invertShapeUI"):
                blend_module.invertShapeUI()
                print("已成功打开 blendShape_conversion.py 的形状倒转工具窗口")
            else:
                cmds.warning("blendShape_conversion.py 中未找到 invertShapeUI 函数")
        except Exception as e:
            cmds.warning(f"加载 blendShape_conversion.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_joint_tag_v1(self):
        joint_tag_file = os.path.join(TOOL_DIR, "joint_TagV1.py")
        if not os.path.exists(joint_tag_file):
            cmds.warning(f"未找到 joint_TagV1.py 文件: {joint_tag_file}")
            return

        try:
            import importlib
            module_name = "joint_TagV1"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 joint_TagV1.py，为场景中的关节添加标签")
        except Exception as e:
            cmds.warning(f"加载 joint_TagV1.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_joint_tag_v2(self):
        joint_tag_file = os.path.join(TOOL_DIR, "joint_TagV2.py")
        if not os.path.exists(joint_tag_file):
            cmds.warning(f"未找到 joint_TagV2.py 文件: {joint_tag_file}")
            return

        try:
            import importlib
            module_name = "joint_TagV2"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 joint_TagV2.py，为场景中的所有关节添加通用标签")
        except Exception as e:
            cmds.warning(f"加载 joint_TagV2.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_mirror_curve_shape(self):
        mirror_file = os.path.join(TOOL_DIR, "MirrorCurveShape.py")
        if not os.path.exists(mirror_file):
            cmds.warning(f"未找到 MirrorCurveShape.py 文件: {mirror_file}")
            return

        try:
            import importlib
            module_name = "MirrorCurveShape"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            mirror_module = sys.modules[module_name]
            if hasattr(mirror_module, "MirrorCurveShape"):
                mirror_module.MirrorCurveShape()
                print("已运行 MirrorCurveShape.py 中的 MirrorCurveShape 函数，镜像曲线形状")
            else:
                cmds.warning("MirrorCurveShape.py 中未找到 MirrorCurveShape 函数")
        except Exception as e:
            cmds.warning(f"加载 MirrorCurveShape.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_trans_curve_shape(self):
        trans_file = os.path.join(TOOL_DIR, "trans_curve_shape.py")
        if not os.path.exists(trans_file):
            cmds.warning(f"未找到 trans_curve_shape.py 文件: {trans_file}")
            return

        try:
            import importlib
            module_name = "trans_curve_shape"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            trans_module = sys.modules[module_name]
            if hasattr(trans_module, "trans_curve_shape"):
                trans_module.trans_curve_shape()
                print("已运行 trans_curve_shape.py 中的 trans_curve_shape 函数，替换曲线形状")
            else:
                cmds.warning("trans_curve_shape.py 中未找到 trans_curve_shape 函数")
        except Exception as e:
            cmds.warning(f"加载 trans_curve_shape.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def load_module_from_file(self, module_name, file_path, description):
        if not os.path.exists(file_path):
            cmds.warning(f"未找到文件: {file_path}")
            return
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                cmds.warning(f"无法创建 {module_name} 的模块规格")
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            if hasattr(module, "show_ui"):
                module.show_ui()
                print(f"已运行 {file_path} 中的 show_ui 函数，{description}")
            else:
                cmds.warning(f"{file_path} 中未找到 show_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 {file_path} 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def reparent_shape_nodes(self):
        reparent_shape_file = os.path.join(TOOL_DIR, "reparentShapeNodes.py")
        if not os.path.exists(reparent_shape_file):
            cmds.warning(f"未找到 reparentShapeNodes.py 文件: {reparent_shape_file}")
            return

        try:
            import importlib.util
            module_name = "reparentShapeNodes"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                reparent_module = sys.modules[module_name]
                importlib.reload(reparent_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, reparent_shape_file)
                reparent_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = reparent_module
                spec.loader.exec_module(reparent_module)

            # 调用函数
            if hasattr(reparent_module, "reparent_shape_nodes"):
                reparent_module.reparent_shape_nodes()
                print("已运行 reparentShapeNodes.py 中的 reparent_shape_nodes 函数，添加形状节点")
            else:
                cmds.warning("reparentShapeNodes.py 中未找到 reparent_shape_nodes 函数")
        except Exception as e:
            cmds.warning(f"运行 reparentShapeNodes.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def auto_rename_curve_shapes(self):
        """调用曲线Shape重命名工具的自动全部命名功能"""
        curve_rename_file = os.path.join(TOOL_DIR, "曲线 Shape 重命名工具.py")
        if not os.path.exists(curve_rename_file):
            cmds.warning(f"未找到 曲线 Shape 重命名工具.py 文件: {curve_rename_file}")
            return

        try:
            # 直接执行Python文件
            with open(curve_rename_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 创建一个新的命名空间来执行代码
            namespace = {}
            exec(code, namespace)
            
            # 调用自动全部命名函数
            if "auto_rename_all" in namespace:
                namespace["auto_rename_all"]()
                print("已运行曲线Shape重命名工具的自动全部命名功能")
            else:
                cmds.warning("曲线 Shape 重命名工具.py 中未找到 auto_rename_all 函数")
        except Exception as e:
            cmds.warning(f"运行曲线Shape重命名工具失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def toggle_always_draw_on_top(self):
        """切换选中曲线的alwaysDrawOnTop属性"""
        selected = cmds.ls(selection=True, long=True)
        if not selected:
            cmds.warning('请先选择需要切换显示属性的曲线。')
            return

        modified_count = 0
        for obj in selected:
            # 获取对象的形状节点
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
            if not shapes:
                continue

            for shape in shapes:
                # 检查是否为曲线形状
                if cmds.nodeType(shape) == 'nurbsCurve':
                    try:
                        # 获取当前的alwaysDrawOnTop状态
                        current_state = cmds.getAttr(f"{shape}.alwaysDrawOnTop")
                        # 切换状态
                        new_state = not current_state
                        cmds.setAttr(f"{shape}.alwaysDrawOnTop", new_state)
                        
                        state_text = "开启" if new_state else "关闭"
                        print(f"曲线 {obj} 的显示在前面属性已{state_text}")
                        modified_count += 1
                    except Exception as e:
                        cmds.warning(f"无法修改 {obj} 的显示属性: {str(e)}")

        if modified_count > 0:
            cmds.inViewMessage(amg=f"<hl>完成！共修改 {modified_count} 个曲线的显示属性。</hl>", pos='midCenterTop', fade=True)
        else:
            cmds.warning('选择的物体中没有有效的曲线。')





    def show(self):
        if not self.isVisible():
            super().show()
        else:
            self.raise_()
            self.activateWindow()
        print("综合工具窗口已显示")

    def closeEvent(self, event):
        # 停止所有动画
        if hasattr(self.gif_label, 'movie') and self.gif_label.movie:
            self.gif_label.movie.stop()
        
        # 保存尺寸和其他窗口状态
        cmds.optionVar(floatValue=("CombinedToolWindowWidth", self.width()))
        cmds.optionVar(floatValue=("CombinedToolWindowHeight", self.height()))
        
        # 保存图标设置
        if hasattr(self, 'gif_label'):
            self.gif_label.save_settings()
        
        # 清理窗口资源
        self.deleteLater()
        
        # 移除实例引用，确保下次可以创建新的窗口
        # 注意：实际上不需要设置为None，因为get_instance会检查窗口存在性
        # 但为了清晰起见，我们仍然做这个操作
        CombinedTool._instance = None
        
        # 关闭所有子窗口
        if self.snap_to_pivot_tool:
            self.snap_to_pivot_tool.close()
        
        # 继续事件传递
        super().closeEvent(event)

    @with_undo_support
    def create_sub_controller(self, parent_ctrl, name, formatted_side, suffix):
        """
        创建子控制器并设置与父控制器的连接

        Args:
            parent_ctrl: 父控制器名称
            name: 基础名称
            formatted_side: 格式化的侧面字符串（如 "_l"）
            suffix: 后缀（如 "_001"）

        Returns:
            tuple: (子控制器名称, 输出组名称)
        """
        try:
            # 创建子控制器 - 直接使用父控制器名称+Sub
            sub_ctrl_name = f"{parent_ctrl}Sub"
            sub_ctrl = cmds.duplicate(parent_ctrl, name=sub_ctrl_name)[0]
            # 先临时将子控制器放在父控制器下
            cmds.parent(sub_ctrl, parent_ctrl)
            cmds.setAttr(f"{sub_ctrl}.scale", 0.9, 0.9, 0.9)
            cmds.makeIdentity(sub_ctrl, apply=True, scale=True)

            # 创建输出组
            output_name = parent_ctrl.replace(f"ctrl{formatted_side}_", f"output{formatted_side}_")
            
            # 检查输出组是否已存在，如果存在则删除
            if cmds.objExists(output_name):
                print(f"警告: 输出组 '{output_name}' 已存在，将被删除并重新创建")
                cmds.delete(output_name)
                
            # 创建输出组并立即父级到控制器下
            output = cmds.createNode('transform', name=output_name, parent=parent_ctrl)

            # 连接属性
            cmds.connectAttr(f"{sub_ctrl}.translate", f"{output_name}.translate")
            cmds.connectAttr(f"{sub_ctrl}.rotate", f"{output_name}.rotate")
            cmds.connectAttr(f"{sub_ctrl}.rotateOrder", f"{output_name}.rotateOrder")
            cmds.connectAttr(f"{sub_ctrl}.scale", f"{output_name}.scale")  # 添加缩放属性连接

            # 显示旋转顺序
            cmds.setAttr(f"{parent_ctrl}.rotateOrder", channelBox=True, keyable=True)
            cmds.setAttr(f"{sub_ctrl}.rotateOrder", channelBox=True, keyable=True)

            # 添加子控制器可见性属性 - 在锁定visibility之前添加
            if not cmds.attributeQuery("subCtrlVis", node=parent_ctrl, exists=True):
                cmds.addAttr(parent_ctrl, longName='subCtrlVis', attributeType='bool', defaultValue=False)
                cmds.setAttr(f"{parent_ctrl}.subCtrlVis", channelBox=True, keyable=False)
                # 设置为可以在通道框中显示但不可k帧
                print(f"已在 '{parent_ctrl}' 上添加 subCtrlVis 属性，并设置为通道框可见但不可关键帧")
            else:
                # 确保属性是不可关键帧的但在通道框可见
                cmds.setAttr(f"{parent_ctrl}.subCtrlVis", channelBox=True, keyable=False)
                
            # 连接子控制器可见性
            cmds.connectAttr(f"{parent_ctrl}.subCtrlVis", f"{sub_ctrl}.visibility")

            # 调整子控制器颜色 - 使用稍浅的颜色
            # 首先获取父控制器的形状节点颜色设置
            parent_shapes = cmds.listRelatives(parent_ctrl, shapes=True) or []
            parent_rgb_colors = None
            parent_index = None
            use_rgb = False

            # 获取父控制器的颜色设置
            if parent_shapes:
                parent_shape = parent_shapes[0]
                if cmds.getAttr(f"{parent_shape}.overrideEnabled"):
                    if cmds.getAttr(f"{parent_shape}.overrideRGBColors"):
                        # 父控制器使用RGB颜色
                        use_rgb = True
                        parent_rgb_colors = cmds.getAttr(f"{parent_shape}.overrideColorRGB")[0]
                    else:
                        # 父控制器使用索引颜色
                        parent_index = cmds.getAttr(f"{parent_shape}.overrideColor")

            # 应用颜色到子控制器
            shapes = cmds.listRelatives(sub_ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)

                if use_rgb and parent_rgb_colors:
                    # 如果父控制器使用RGB颜色，则子控制器也使用RGB但颜色更淡
                    cmds.setAttr(f"{shape}.overrideRGBColors", 1)
                    # 将RGB颜色调亮一些，但保持原始色调
                    lighter_rgb = [min(c * 1.3, 1.0) for c in parent_rgb_colors]
                    cmds.setAttr(f"{shape}.overrideColorRGB", *lighter_rgb)
                    print(f"子控制器 '{sub_ctrl_name}' 颜色设为淡化的RGB: {lighter_rgb}")
                elif parent_index is not None:
                    # 如果父控制器使用索引颜色，则子控制器使用更淡的索引颜色
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)

                    # Maya颜色索引映射表 - 从深色到浅色
                    color_map = {
                        # 红色系
                        4: 31,  # 暗红 -> 粉红
                        12: 31,  # 红棕 -> 粉红
                        13: 20,  # 红色 -> 浅红
                        24: 20,  # 红色 -> 浅红
                        31: 9,  # 粉红 -> 淡粉

                        # 蓝色系
                        5: 18,  # 深蓝 -> 浅蓝
                        6: 18,  # 蓝色 -> 浅蓝
                        15: 18,  # 海军蓝 -> 浅蓝
                        18: 29,  # 浅蓝 -> 淡蓝

                        # 绿色系
                        7: 19,  # 绿色 -> 浅绿
                        19: 29,  # 浅绿 -> 淡绿
                        23: 19,  # 深绿 -> 浅绿

                        # 黄色系
                        17: 22,  # 黄色 -> 浅黄
                        21: 22,  # 黄褐色 -> 浅黄
                        11: 21,  # 棕色 -> 黄褐色
                        10: 11,  # 深棕 -> 棕色

                        # 紫色系
                        8: 30,  # 紫色 -> 淡紫
                        9: 30,  # 淡紫红 -> 淡紫

                        # 青色系
                        14: 29,  # 亮蓝 -> 淡蓝
                        16: 29,  # 青色 -> 淡蓝绿

                        # 灰色系
                        0: 3,  # 黑色 -> 深灰
                        1: 3,  # 黑色 -> 深灰
                        2: 3,  # 深灰2 -> 深灰
                        3: 2,  # 深灰 -> 灰色
                        25: 22,  # 棕黄 -> 浅黄
                        26: 19,  # 草绿 -> 浅绿
                        27: 30,  # 深紫 -> 淡紫
                        28: 16,  # 褐色 -> 青色
                    }

                    # 使用映射表或简单加亮规则
                    if parent_index in color_map:
                        new_index = color_map[parent_index]
                    else:
                        # 默认规则：如果没有特定映射，使用索引+2 (限制在有效范围内)
                        new_index = min(parent_index + 2, 31)

                    cmds.setAttr(f"{shape}.overrideColor", new_index)
                    print(f"子控制器 '{sub_ctrl_name}' 颜色索引从 {parent_index} 改为 {new_index}")
                else:
                    # 如果父控制器没有设置颜色，使用默认淡蓝色
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                    cmds.setAttr(f"{shape}.overrideColor", 18)  # 浅蓝色
                    print(f"子控制器 '{sub_ctrl_name}' 设置默认颜色索引 18 (浅蓝色)")

            return sub_ctrl_name, output_name
        except Exception as e:
            print(f"创建子控制器时出错: {str(e)}")
            return None, None

    def center_icon_vertically(self):
        """将图标垂直居中显示在其容器中"""
        if hasattr(self, 'gif_label') and hasattr(self, 'gif_container'):
            # 计算居中位置
            container_height = self.gif_container.height()
            icon_height = self.gif_label.height()
            
            # 设置图标的垂直位置（水平位置保持不变）
            if container_height > icon_height:
                y_pos = (container_height - icon_height) // 2
                self.gif_label.move(self.gif_label.x(), y_pos)
                
                # 保存初始位置信息到图标对象
                self.gif_label.start_position = self.gif_label.pos()
                
            # 确保gif_label可以自由定位
            self.gif_label.setProperty("centered", True)

    def showMainContextMenu(self, pos):
        """显示主窗口右键菜单，用于控制图标显示"""
        context_menu = QMenu(self)
        
        # 根据图标当前状态添加显示/隐藏选项
        icon_visible = self.gif_label.is_visible if hasattr(self.gif_label, 'is_visible') else True
        toggle_action = QAction("隐藏图标" if icon_visible else "显示图标", self)
        toggle_action.triggered.connect(self.toggleIconVisibility)
        context_menu.addAction(toggle_action)
        
        # 添加图标设置选项
        settings_action = QAction("图标设置", self)
        settings_action.triggered.connect(lambda: self.gif_label.showSettingsDialog() if hasattr(self.gif_label, 'showSettingsDialog') else None)
        # 当图标隐藏时禁用设置选项
        settings_action.setEnabled(icon_visible)
        context_menu.addAction(settings_action)
        
        # 添加重置图标位置选项
        reset_pos_action = QAction("重置图标位置", self)
        reset_pos_action.triggered.connect(lambda: self.gif_label.resetPosition() if hasattr(self.gif_label, 'resetPosition') else None)
        # 当图标隐藏时禁用重置位置选项
        reset_pos_action.setEnabled(icon_visible)
        context_menu.addAction(reset_pos_action)
        
        # 显示菜单
        context_menu.exec_(self.mapToGlobal(pos))

    def adjustSize(self):
        """重写adjustSize方法，防止窗口自动调整大小"""
        # 获取滚动区域
        scroll_area = None
        for child in self.findChildren(QScrollArea):
            scroll_area = child
            break
        
        # 如果没有滚动区域，调用默认实现
        if not scroll_area or not scroll_area.widget():
            return super().adjustSize()
        
        # 仅更新内部布局，不调整窗口大小
        central_widget = self.centralWidget()
        if central_widget:
            central_widget.updateGeometry()
        
        # 更新内容布局
        content = scroll_area.widget()
        if content:
            content.updateGeometry()
            if content.layout():
                content.layout().invalidate()
                content.layout().activate()
        
        # 更新UI但不改变窗口大小
        self.update()

    def _apply_icon_visibility(self, visible):
        """应用图标可见性状态而不保存设置"""
        if not hasattr(self, 'gif_label'):
            return
            
        # 直接设置内部状态，避免循环调用toggleVisibility
        self.gif_label.is_visible = visible
        
        # 执行与toggleVisibility相同的显示/隐藏逻辑，但不保存设置
        if hasattr(self.gif_label, 'movie') and self.gif_label.movie:
            if visible:
                self.gif_container.setMinimumHeight(70)
                self.gif_label.movie.start()
                self.gif_label.setFixedSize(self.gif_label.current_size)
                self.gif_label.show()
            else:
                self.gif_label.movie.stop()
                self.gif_label.setFixedSize(0, 0)
                self.gif_container.setMinimumHeight(10)
        else:
            if visible:
                self.gif_container.setMinimumHeight(70)
                self.gif_label.setFixedSize(self.gif_label.current_size)
                self.gif_label.show()
            else:
                self.gif_label.setFixedSize(0, 0)
                self.gif_container.setMinimumHeight(10)
                
        # 更新布局
        self.gif_label.updateLayout()
        QTimer.singleShot(0, self.adjustSize)
        
        print(f"已应用可见性状态: {visible}")
    
    def toggleIconVisibility(self):
        """切换图标显示状态并调整UI"""
        if hasattr(self.gif_label, 'toggleVisibility'):
            # 调用toggleVisibility会自动保存状态
            self.gif_label.toggleVisibility()
            # 延迟调整主窗口大小和布局，以确保图标状态已更新
            QTimer.singleShot(100, self.adjustSize)
            # 打印当前状态以便调试
            print(f"图标状态已切换，当前可见性: {self.gif_label.is_visible}")

    def parse_object_name(self, object_name, ignore_suffix=True):
        """解析物体名称，提取控制器名称
        
        参数:
            object_name (str): 物体名称（支持骨骼、网格、组等任意Maya物体）
            ignore_suffix (bool): 是否忽略后缀，默认为True
            
        返回:
            str: 解析后的控制器基础名称
        """
        # 移除路径前缀，只保留节点名称
        clean_name = object_name.split("|")[-1]
        
        # 根据选项决定是否移除后缀
        if ignore_suffix:
            # 移除任何以下划线开头的后缀，使其更通用
            # 例如：_001, _abc, _L, _R, _ctrl等任意后缀
            name_without_suffix = re.sub(r'_[^_]*$', '', clean_name)
        else:
            # 不忽略后缀，使用原始名称
            name_without_suffix = clean_name
        
        # 检查是否符合标准命名格式（支持多种前缀）
        # 支持的格式：jnt_m_aaa, mesh_l_bbb, grp_r_ccc, ctrl_m_ddd等
        if ignore_suffix:
            pattern = r'^([a-zA-Z]+)_([lrcm])_([^_]+)$'
        else:
            pattern = r'^([a-zA-Z]+)_([lrcm])_([^_]+)(_.*)?$'
        
        match = re.match(pattern, name_without_suffix, re.IGNORECASE)
        
        if match:
            # 符合标准格式，提取前缀、侧面和名称部分
            prefix = match.group(1).lower()
            side = match.group(2).lower()
            name_part = match.group(3)
            if ignore_suffix:
                return f"{side}_{name_part}"
            else:
                # 保留后缀（如果有的话）
                suffix_part = match.group(4) if len(match.groups()) > 3 and match.group(4) else ""
                return f"{side}_{name_part}{suffix_part}"
        else:
            # 不符合标准格式，尝试识别常见前缀并移除
            result_name = name_without_suffix
            # 移除常见的Maya物体前缀
            common_prefixes = ['jnt_', 'joint_', 'mesh_', 'geo_', 'grp_', 'group_', 'ctrl_', 'control_', 'loc_', 'locator_']
            for prefix in common_prefixes:
                if result_name.lower().startswith(prefix):
                    result_name = result_name[len(prefix):]
                    break
            return result_name
    
    @with_undo_support
    def create_fk_hierarchy(self):
        """为选中的骨骼链创建FK控制器层级"""
        selected = cmds.ls(selection=True, type="joint")
        
        if not selected:
            cmds.warning("请先选择一个骨骼作为FK链的起始点")
            return
        
        root_joint = selected[0]
        
        # 获取骨骼链
        joint_chain = self.get_joint_chain(root_joint)
        
        if not joint_chain:
            cmds.warning(f"无法从 {root_joint} 获取有效的骨骼链")
            return
        
        # 如果需要排除最后一个骨骼，则移除
        exclude_last = self.exclude_last_joint_check.isChecked()
        if exclude_last and len(joint_chain) > 1:
            joint_chain.pop()
        
        # 检查是否启用物体名称识别
        use_auto_naming = self.auto_name_from_joint_check.isChecked()
        
        # 检查是否忽略后缀
        ignore_suffix = self.ignore_suffix_check.isChecked()
        
        # 从创建关节控制器组件获取设置
        custom_name = self.name_text.text()
        custom_sides = self.side_text.text().strip()
        # 解析用户输入的侧面，支持逗号分隔，例如 "l,r,m"
        sides_list = [s.strip() for s in custom_sides.split(',')] if custom_sides else []
        use_custom_side = len(sides_list) == 1  # 如果只有一个侧面，使用它替代从关节名提取的侧面
        
        create_joint_flag = self.create_joint_flag
        create_controller_flag = self.create_controller_flag
        create_sub_controller_flag = self.create_sub_controller_flag
        use_hierarchy_logic = self.use_hierarchy_logic
        controller_type = self.controller_type
        ctrl_size = self.size_spin.value()
        
        # 确定约束设置
        parent_constraint = self.parent_constraint_check.isChecked()
        parent_offset = self.parent_offset_check.isChecked()
        point_constraint = self.point_constraint_check.isChecked()
        point_offset = self.point_offset_check.isChecked()
        orient_constraint = self.orient_constraint_check.isChecked()
        orient_offset = self.orient_offset_check.isChecked()
        scale_constraint = self.scale_constraint_check.isChecked()
        scale_offset = self.scale_offset_check.isChecked()
        
        # ==== 修改逻辑：先创建所有控制器及组结构 ====
        
        # 存储创建的控制器和组的信息，以便后续处理
        controller_info = []
        controllers = []
        prev_ctrl = None
        
        # 第一步：创建所有控制器和组
        for i, joint in enumerate(joint_chain):
            # 获取关节名称信息
            joint_name = joint.split("|")[-1]  # 移除全路径
            
            # 根据是否启用物体名称识别来确定命名方式
            if use_auto_naming:
                # 使用物体名称识别功能
                parsed_name = self.parse_object_name(joint_name, ignore_suffix)
                
                # 检查解析结果是否包含侧面信息
                if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息，直接使用
                    side_and_name = parsed_name
                    formatted_side = ""
                    base_name = parsed_name
                else:
                    # 不包含侧面信息，使用原有逻辑确定侧面
                    side = ""
                    if use_custom_side and sides_list[0]:  # 使用用户指定的侧面
                        side = sides_list[0].lower()
                    elif "_" in joint_name:  # 从关节名称中提取侧面
                        parts = joint_name.split("_")
                        possible_side = parts[0].lower()
                        if possible_side in ["l", "r", "c", "m"]:
                            side = possible_side
                    
                    formatted_side = f"_{side}" if side else ""
                    base_name = parsed_name
                
                # 使用解析的名称，添加序号后缀
                suffix = f"_{i+1:03d}"  # 使用_001格式的后缀
                
                # 创建零组和控制器名称
                if "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    zero_group_name = f"zero_{base_name}{suffix}"
                    ctrl_name = f"ctrl_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    zero_group_name = f"zero{formatted_side}_{base_name}{suffix}"
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
            else:
                # 使用原有的命名逻辑
                # 确定侧面信息
                side = ""
                if use_custom_side and sides_list[0]:  # 使用用户指定的侧面
                    side = sides_list[0].lower()
                elif "_" in joint_name:  # 从关节名称中提取侧面
                    parts = joint_name.split("_")
                    possible_side = parts[0].lower()
                    if possible_side in ["l", "r", "c", "m"]:
                        side = possible_side
                
                # 确定使用的控制器基础名称和后缀
                suffix = f"_{i+1:03d}"  # 使用_001格式的后缀
                
                if custom_name:
                    base_name = custom_name  # 使用用户指定的名称
                else:
                    # 使用关节名称的最后一部分作为基础名称
                    base_name = joint_name.split("_")[-1] if "_" in joint_name else joint_name
                
                formatted_side = f"_{side}" if side else ""
                
                # 创建零组和控制器，采用基础名称+后缀的命名方式
                zero_group_name = f"zero{formatted_side}_{base_name}{suffix}"
                ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
            
            # 创建组层级结构
            if use_hierarchy_logic:
                zero_group = cmds.group(name=zero_group_name, empty=True)
                
                # 根据命名方式确定其他组的名称
                if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    driven_group_name = f"driven_{base_name}{suffix}"
                    connect_group_name = f"connect_{base_name}{suffix}"
                    offset_group_name = f"offset_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    driven_group_name = f"driven{formatted_side}_{base_name}{suffix}"
                    connect_group_name = f"connect{formatted_side}_{base_name}{suffix}"
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"
                
                driven_group = cmds.group(name=driven_group_name, empty=True, parent=zero_group)
                connect_group = cmds.group(name=connect_group_name, empty=True, parent=driven_group)
                offset_group = cmds.group(name=offset_group_name, empty=True, parent=connect_group)
                last_group = offset_group
            else:
                zero_group = cmds.group(name=zero_group_name, empty=True)
                
                # 根据命名方式确定offset组的名称
                if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    offset_group_name = f"offset_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"
                    
                offset_group = cmds.group(name=offset_group_name, empty=True, parent=zero_group)
                last_group = offset_group
            
            # 创建控制器
            if create_controller_flag:
                ctrl = controller_shapes.create_custom_controller(
                    ctrl_name=ctrl_name, 
                    controller_type=controller_type, 
                    size=ctrl_size
                )
                
                # 设置控制器颜色
                controller_shapes.apply_color_to_controller(ctrl, self.color_rgb)
                
                # 为控制器形状节点重命名为"曲线名称_Shape"格式
                controller_shapes.rename_controller_shape(ctrl)
                
                # 父级控制器到最后一个组
                cmds.parent(ctrl, last_group)
                
                # 确保旋转顺序是可见的和可关键帧的
                cmds.setAttr(f"{ctrl}.rotateOrder", channelBox=True, keyable=True)
                
                # 如果启用了子控制器选项，创建子控制器
                sub_ctrl = None
                output_group = None
                if create_sub_controller_flag:
                    # 创建子控制器
                    sub_ctrl_name = f"{ctrl_name}_sub"
                    sub_ctrl = controller_shapes.create_custom_controller(
                        ctrl_name=sub_ctrl_name,
                        controller_type=controller_type,
                        size=ctrl_size * 0.8
                    )
                    
                    # 为子控制器形状节点重命名为"曲线名称_Shape"格式
                    controller_shapes.rename_controller_shape(sub_ctrl)
                    
                    # 设置子控制器颜色 (稍微暗一点)
                    sub_color = tuple(c * 0.8 for c in self.color_rgb)
                    controller_shapes.apply_color_to_controller(sub_ctrl, sub_color)
                    
                    # 创建输出组 - 这将用于连接FK链和约束
                    if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                        # 已包含侧面信息的情况
                        output_name = f"output_{base_name}{suffix}"
                    else:
                        # 不包含侧面信息的情况
                        output_name = f"output{formatted_side}_{base_name}{suffix}"
                    output_group = cmds.group(name=output_name, empty=True)
                    
                    # 重要：将子控制器和输出组都放在控制器下面
                    cmds.parent(sub_ctrl, ctrl)
                    cmds.parent(output_group, ctrl)
                    
                    # 添加调试输出
                    print(f"层级结构: 已创建子控制器 '{sub_ctrl}' 和输出组 '{output_group}'，并放置在控制器 '{ctrl}' 下")
                    
                    # 添加子控制器可见性属性，默认设置为不可见
                    cmds.addAttr(ctrl, longName="subCtrlVis", attributeType="bool", defaultValue=0)
                    cmds.setAttr(f"{ctrl}.subCtrlVis", channelBox=True, keyable=False)
                    cmds.connectAttr(f"{ctrl}.subCtrlVis", f"{sub_ctrl}.visibility")
                    print(f"可见性: 子控制器 '{sub_ctrl}' 默认设置为隐藏，可在通道框中显示但不可关键帧")
                    
                    # 确保子控制器的旋转顺序是可见的和可关键帧的
                    cmds.setAttr(f"{sub_ctrl}.rotateOrder", channelBox=True, keyable=True)
                    
                    # 连接子控制器到输出组 - 确保子控制器驱动输出组
                    cmds.connectAttr(f"{sub_ctrl}.translate", f"{output_group}.translate")
                    cmds.connectAttr(f"{sub_ctrl}.rotate", f"{output_group}.rotate")
                    cmds.connectAttr(f"{sub_ctrl}.rotateOrder", f"{output_group}.rotateOrder")
                    cmds.connectAttr(f"{sub_ctrl}.scale", f"{output_group}.scale")
                    print(f"连接: 已将子控制器 '{sub_ctrl}' 变换连接到输出组 '{output_group}'")
            else:
                # 如果不创建控制器，创建一个空组作为控制器
                ctrl = cmds.group(name=ctrl_name, empty=True, parent=last_group)
                sub_ctrl = None
                output_group = None
            
            # 存储控制器信息
            controller_info.append({
                'joint': joint,
                'zero_group': zero_group,
                'ctrl': ctrl,
                'sub_ctrl': sub_ctrl,
                'output_group': output_group,
                'last_group': last_group
            })
            
            controllers.append(ctrl)
        
        # 第二步：建立FK层级关系（使第一个控制器保持在世界空间，其余控制器成为链）
        for i in range(1, len(controller_info)):
            prev_info = controller_info[i-1]
            curr_info = controller_info[i]
            
            # 重要：当启用子控制器时，确保零组连接到前一个控制器的output组
            if prev_info['output_group']:
                # 有output组，连接到output组
                prev_output = prev_info['output_group']
                parent_type = "output组"
            else:
                # 没有output组，连接到控制器本身
                prev_output = prev_info['ctrl']
                parent_type = "控制器"
            
            # 将当前zero组父级到确定的节点（output组或控制器）
            cmds.parent(curr_info['zero_group'], prev_output)
            
            # 添加调试输出
            print(f"FK链接: 将 '{curr_info['zero_group']}' 父级到前一个{parent_type} '{prev_output}'")
        
        # 第三步：匹配位置和旋转，应用约束
        for info in controller_info:
            joint = info['joint']
            zero_group = info['zero_group']
            ctrl = info['ctrl']
            sub_ctrl = info['sub_ctrl']
            output_group = info['output_group']
            
            # 匹配zero组到关节位置
            cmds.matchTransform(zero_group, joint, position=True, rotation=True)
            
            # 如果有子控制器和输出组，匹配它们到控制器
            if sub_ctrl and output_group:
                cmds.matchTransform(sub_ctrl, ctrl, position=True, rotation=True)
                cmds.matchTransform(output_group, ctrl, position=True, rotation=True)
                
                # 应用约束到骨骼
                constraint_target = output_group
                print(f"将使用输出组 '{output_group}' 约束骨骼 '{joint}'")
            else:
                constraint_target = ctrl
                print(f"将使用控制器 '{ctrl}' 约束骨骼 '{joint}'")
            
            # 应用约束
            if parent_constraint:
                constraint = cmds.parentConstraint(constraint_target, joint, maintainOffset=parent_offset)
                print(f"已创建父子约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
            else:
                if point_constraint:
                    constraint = cmds.pointConstraint(constraint_target, joint, maintainOffset=point_offset)
                    print(f"已创建点约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
                if orient_constraint:
                    constraint = cmds.orientConstraint(constraint_target, joint, maintainOffset=orient_offset)
                    print(f"已创建方向约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
            
            if scale_constraint:
                constraint = cmds.scaleConstraint(constraint_target, joint, maintainOffset=scale_offset)
                print(f"已创建缩放约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
        
        # 如果成功创建控制器，选择第一个控制器
        if controllers:
            # 确保所有控制器的subCtrlVis属性是不可关键帧的
            for ctrl in controllers:
                if cmds.attributeQuery("subCtrlVis", node=ctrl, exists=True):
                    try:
                        cmds.setAttr(f"{ctrl}.subCtrlVis", channelBox=True, keyable=False)
                        print(f"确保FK控制器 '{ctrl}.subCtrlVis' 属性在通道框中可见但不可关键帧")
                    except Exception as e:
                        print(f"无法设置 '{ctrl}.subCtrlVis' 属性: {str(e)}")
                        
            cmds.select(controllers[0])
            print(f"✅ 成功创建FK层级链，共 {len(controllers)} 个控制器")
        else:
            cmds.warning("创建FK层级链失败")

    def get_joint_chain(self, root_joint):
        """获取从指定根骨骼开始的骨骼链
        
        参数:
            root_joint (str): 根骨骼名称
            
        返回:
            list: 骨骼链列表
        """
        joint_chain = [root_joint]
        current = root_joint
        
        # 循环查找子骨骼，直到没有子骨骼为止
        while True:
            children = cmds.listRelatives(current, children=True, type="joint") or []
            
            # 如果没有子骨骼或有多个子骨骼，停止
            if not children or len(children) > 1:
                break
            
            # 添加到链中并更新当前骨骼
            joint_chain.append(children[0])
            current = children[0]
        
        return joint_chain

    def update_font_size(self, font_size):
        """更新整个UI的字体大小"""
        # 保存当前字体大小设置
        self.font_size = font_size
        
        # 更新样式表
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QWidget {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QPushButton {{
                background-color: #3E3E42;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 22px;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: #505054;
                border-color: #6A6A6A;
            }}
            QPushButton:pressed {{
                background-color: #2A2A2A;
                border-color: #777777;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                selection-background-color: #264F78;
                font-size: {font_size}px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                min-height: 20px;
                font-size: {font_size}px;
            }}
            QComboBox:hover {{
                border-color: #6A6A6A;
            }}
            QComboBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QCheckBox {{
                color: #E0E0E0;
                spacing: 6px;
                font-size: {font_size}px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid #555555;
                border-radius: 2px;
                background-color: #333337;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0078D7;
                border-color: #0078D7;
            }}
            QCheckBox::indicator:hover {{
                border-color: #6A6A6A;
            }}
            QLabel {{
                color: #E0E0E0;
                font-size: {font_size}px;
            }}
            QScrollArea {{
                background-color: #2D2D30;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: #2D2D30;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555555;
                min-height: 20px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #6A6A6A;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: #2D2D30;
            }}
            QToolTip {{
                background-color: #2D2D30;
                color: #E0E0E0;
                border: 1px solid #555555;
                padding: 4px;
                opacity: 220;
                font-size: {font_size}px;
            }}
            QFrame[frameShape="4"] {{ /* 分隔线 */
                background-color: #555555;
                height: 1px;
                max-height: 1px;
            }}
        """)
        
        # 更新所有CollapsibleGroupBox的字体大小
        for group_box in self.findChildren(CollapsibleGroupBox):
            # 更新按钮样式
            group_box.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3A3A3A;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 12px;
                    text-align: left;
                    font-weight: bold;
                    font-size: {font_size}px;
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: #4A4A4A;
                }}
                QPushButton:pressed {{
                    background-color: #353535;
                }}
            """)
            
        # 保存设置到Maya optionVar
        cmds.optionVar(intValue=("CKTool_FontSize", font_size))
        
        # 调整窗口大小以适应新的字体大小
        QTimer.singleShot(100, self.adjustSize)

    @with_undo_support
    def match_selected_transforms(self):
        """匹配选中物体的变换到最后一个选中的物体"""
        selected_objects = cmds.ls(selection=True)
        if len(selected_objects) < 2:
            cmds.warning("请选择至少两个物体，最后一个选中的物体将作为目标")
            return

        target_obj = selected_objects[-1]
        source_objects = selected_objects[:-1]

        for obj in source_objects:
            cmds.matchTransform(obj, target_obj,
                              pos=self.match_position,
                              rot=self.match_rotation,
                              scl=self.match_scale)
        print(f"已将 {len(source_objects)} 个物体匹配到 '{target_obj}' 的变换")


# 运行工具
def run_tool():
    try:
        # 使用get_instance方法获取窗口实例，不需要在这里额外检查窗口是否存在
        # get_instance已经包含了完整的窗口唯一性处理逻辑
        window = CombinedTool.get_instance()
        window.show()
        window.raise_()  # 将窗口置于前台
        window.activateWindow()  # 激活窗口
        return window
    except Exception as e:
        print(f"运行工具时出错: {str(e)}")
        print("请确保在Maya环境中运行此工具")
        return None


if __name__ == "__main__":
    try:
        # 尝试导入maya.cmds
        from maya import cmds
        run_tool()
    except ImportError:
        print("=" * 50)
        print("错误: 此工具需要在Maya环境中运行")
        print("请使用Maya的script editor或通过Maya的Python解释器运行此脚本")
        print("=" * 50)
    except Exception as e:
        print(f"工具启动失败: {str(e)}")
        print("请确保在Maya环境中运行此工具")from maya import cmds
import maya.mel as mel
import re
import math
import os
import sys  # 用于动态添加路径
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
                               QColorDialog, QLabel, QGridLayout, QScrollArea, QToolTip, QFrame,
                               QGraphicsOpacityEffect, QListWidget, QListWidgetItem,
                               QGroupBox, QRadioButton, QFileDialog, QTabWidget, QMessageBox,
                               QSizePolicy, QDialog, QSlider, QMenu, QAction)
from PySide2.QtGui import QColor, QPalette, QFont, QPixmap, QPainter, QImage, QCursor, QMovie
from PySide2.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QSize, QRect, QSequentialAnimationGroup
import shiboken2
from maya import OpenMayaUI
from functools import wraps  # 用于装饰器
import importlib
import json
import time
from datetime import datetime

# 导入控制器形状模块
from controllers import controller_shapes


# 导入通用工具模块
def get_script_path():
    try:
        # 首先尝试使用__file__变量（在脚本文件执行时可用）
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # 在Maya控制台中直接执行时，使用Maya的脚本路径
        import inspect
        return os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


sys.path.append(os.path.join(get_script_path(), "tool"))
from common_utils import reload_module


# 辅助函数：加载模块
def load_module(module_name, file_path=None, function_name=None, *args, **kwargs):
    """
    通用模块加载函数，用于导入或重载指定的模块，并可选择性地执行其中的函数

    参数:
        module_name (str): 要导入或重载的模块名称
        file_path (str, 可选): 模块文件的完整路径
        function_name (str, 可选): 要执行的函数名称
        *args, **kwargs: 传递给函数的参数

    返回:
        module: 导入或重载后的模块对象
    """
    try:
        # 使用reload_module函数加载或重载模块
        module = reload_module(module_name, file_path)

        # 如果指定了函数名，则执行该函数
        if function_name and hasattr(module, function_name):
            func = getattr(module, function_name)
            func(*args, **kwargs)
            print(f"已运行 {module_name}.py 中的 {function_name} 函数")
        elif function_name:
            cmds.warning(f"{module_name}.py 中未找到 {function_name} 函数")

        return module
    except Exception as e:
        cmds.warning(f"加载 {module_name}.py 失败: {str(e)}")
        print(f"错误详情: {str(e)}")
        return None


# 动态路径设置
SCRIPT_DIR = get_script_path()
TOOL_DIR = os.path.join(SCRIPT_DIR, "tool")
if TOOL_DIR not in sys.path:
    sys.path.append(TOOL_DIR)

# 确保controllers目录也在路径中
CONTROLLERS_DIR = os.path.join(SCRIPT_DIR, "controllers")
if CONTROLLERS_DIR not in sys.path:
    sys.path.append(CONTROLLERS_DIR)


# 获取 Maya 主窗口作为 PySide2 小部件
def get_maya_main_window():
    main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
    if main_window_ptr is not None:
        return shiboken2.wrapInstance(int(main_window_ptr), QWidget)
    return None


# 确保 PySide2 应用实例存在
if QApplication.instance() is None:
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()


# 全局撤销装饰器
def with_undo_support(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            cmds.undoInfo(openChunk=True)
            result = func(self, *args, **kwargs)
            if func.__name__ not in ["show", "closeEvent"]:
                print(f"'{func.__name__}' 操作完成。按 Ctrl+Z 可撤销此操作。")
            return result
        except Exception as e:
            print(f"'{func.__name__}' 操作出错: {e}")
            raise
        finally:
            cmds.undoInfo(closeChunk=True)

    return wrapper


# 自定义按钮类，带延迟工具提示
class DelayedToolTipButton(QPushButton):
    def __init__(self, text, tooltip_text="", parent=None):
        super().__init__(text, parent)
        
        # 保存工具提示文本，但不立即设置
        self.tooltip_text = tooltip_text
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.showToolTipDelayed)
        
        # 设置工具提示政策
        self.setToolTipDuration(5000)  # 设置工具提示显示5秒
        
        # 找到主窗口以获取字体大小
        self.main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if isinstance(parent_widget, CombinedTool):
                self.main_window = parent_widget
                break
            parent_widget = parent_widget.parent()
        
        # 获取字体大小并应用
        font_size = 11
        if self.main_window and hasattr(self.main_window, 'font_size'):
            font_size = self.main_window.font_size
        
        # 将字体大小应用到按钮
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)

    def enterEvent(self, event):
        self.hover_timer.start(300)  # 设置300毫秒延迟
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def showToolTipDelayed(self):
        """延迟显示工具提示"""
        if not self.underMouse():
            return
            
        # 显示工具提示
        if self.tooltip_text:
            # 获取屏幕上当前鼠标位置
            cursor_pos = QCursor.pos()
            QToolTip.showText(cursor_pos, self.tooltip_text, self)


# 交互式图标标签类，支持拖动、缩放和设置
class InteractiveIconLabel(QLabel):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.dragging = False
        self.drag_start_position = None
        self.default_size = QSize(60, 60)
        self.current_size = self.default_size
        self.main_window = main_window  # 保存主窗口引用
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("双击打开设置 | 滚轮缩放 | 拖动移动位置 | 右键菜单切换显示 | 按住缩放")
        self.setMinimumSize(30, 30)
        # 默认启用窗口缩放效果
        self.enable_window_scaling = True
        # 默认显示图标
        self.is_visible = True
        # 默认字体大小
        self.font_size = 11
        # 允许绝对定位
        self.setStyleSheet("QLabel { background: transparent; }")
        
        # 设置上下文菜单策略，接受右键事件
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        
        # 加载保存的配置
        self.load_settings()
        
        # 移除按住时缩放动画的参数
        
    def load_settings(self):
        """从Maya optionVar加载设置"""
        if cmds.optionVar(exists="CKTool_IconSize"):
            size = cmds.optionVar(query="CKTool_IconSize")
            self.current_size = QSize(size, size)
        
        if cmds.optionVar(exists="CKTool_IconScaling"):
            self.enable_window_scaling = bool(cmds.optionVar(query="CKTool_IconScaling"))
            
        if cmds.optionVar(exists="CKTool_IconVisible"):
            self.is_visible = bool(cmds.optionVar(query="CKTool_IconVisible"))
            
        if cmds.optionVar(exists="CKTool_IconPath"):
            self.icon_path = cmds.optionVar(query="CKTool_IconPath")
        else:
            # 默认图标路径
            self.icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "siri.gif")
        
        # 加载字体大小设置
        if cmds.optionVar(exists="CKTool_FontSize"):
            self.font_size = cmds.optionVar(query="CKTool_FontSize")
        else:
            # 默认字体大小设置为11
            self.font_size = 11
    
    def save_settings(self):
        """保存设置到Maya optionVar"""
        cmds.optionVar(intValue=("CKTool_IconSize", self.current_size.width()))
        cmds.optionVar(intValue=("CKTool_IconScaling", int(self.enable_window_scaling)))
        cmds.optionVar(intValue=("CKTool_IconVisible", int(self.is_visible)))
        
        if hasattr(self, 'icon_path') and self.icon_path:
            cmds.optionVar(stringValue=("CKTool_IconPath", self.icon_path))
            
        # 保存字体大小设置
        if hasattr(self, 'font_size'):
            cmds.optionVar(intValue=("CKTool_FontSize", self.font_size))
            
        # 如果有位置信息，也保存它
        if self.pos():
            cmds.optionVar(intValue=("CKTool_IconX", self.pos().x()))
            cmds.optionVar(intValue=("CKTool_IconY", self.pos().y()))
            
        # 调试信息 - 打印保存的设置
        print(f"保存设置: 大小={self.current_size.width()}, 可见={self.is_visible}, 图标路径={self.icon_path if hasattr(self, 'icon_path') else '无'}")
    
    def showContextMenu(self, pos):
        """显示右键菜单"""
        context_menu = QMenu(self)
        
        # 根据当前可见状态添加切换选项
        toggle_action = QAction("隐藏图标" if self.is_visible else "显示图标", self)
        toggle_action.triggered.connect(self.toggleVisibility)
        context_menu.addAction(toggle_action)
        
        # 添加设置选项
        settings_action = QAction("图标设置", self)
        settings_action.triggered.connect(self.showSettingsDialog)
        context_menu.addAction(settings_action)
        
        # 添加重置位置选项
        reset_pos_action = QAction("重置位置", self)
        reset_pos_action.triggered.connect(self.resetPosition)
        context_menu.addAction(reset_pos_action)
        
        # 显示菜单
        context_menu.exec_(self.mapToGlobal(pos))
    
    def toggleVisibility(self):
        """切换图标显示状态"""
        self.is_visible = not self.is_visible
        
        # 获取父容器以便调整
        parent_container = self.parent()
        
        # 批量处理UI更新，避免多次重绘
        self.setUpdatesEnabled(False)
        
        if hasattr(self, 'movie') and self.movie:
            if self.is_visible:
                # 恢复容器高度
                if parent_container:
                    parent_container.setMinimumHeight(70)
                # 启动动画并显示
                self.movie.start()
                self.setFixedSize(self.current_size)
                self.show()
            else:
                # 停止动画并隐藏
                self.movie.stop()
                self.setFixedSize(0, 0)
                # 减小容器高度
                if parent_container:
                    parent_container.setMinimumHeight(10)
        else:
            # 如果不是动画，使用普通显示/隐藏
            if self.is_visible:
                if parent_container:
                    parent_container.setMinimumHeight(70)
                self.setFixedSize(self.current_size)
                self.show()
            else:
                self.setFixedSize(0, 0)
                if parent_container:
                    parent_container.setMinimumHeight(10)
        
        # 恢复UI更新
        self.setUpdatesEnabled(True)
        
        # 更新布局，确保所有父级布局都能正确重新计算
        self.updateLayout()
        
        # 立即保存可见性状态
        self.save_settings()
        
        # 通知主窗口布局变化，以便整体调整
        if self.main_window:
            # 使用单一延迟调整
            QTimer.singleShot(50, self.main_window.adjustSize)
    
    def resetPosition(self):
        """重置图标位置到容器中央"""
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = (parent_rect.height() - self.height()) // 2
            self.move(x, y)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_position = event.pos()
            # 记录全局鼠标位置和当前控件位置
            self.start_global_pos = event.globalPos()
            self.start_position = self.pos()
            
            # 移除缩放动画功能
            
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.dragging and (event.buttons() & Qt.LeftButton):
            # 使用全局坐标计算相对移动距离，减少抽搐
            global_pos = event.globalPos()
            delta = global_pos - self.start_global_pos
            # 允许在水平和垂直方向上移动
            new_pos = self.start_position + delta
            
            # 确保不会移出父控件的边界
            parent_rect = self.parent().rect()
            new_x = max(0, min(parent_rect.width() - self.width(), new_pos.x()))
            new_y = max(0, min(parent_rect.height() - self.height(), new_pos.y()))
            self.move(new_x, new_y)
            
            # 移除了离中心越远越小的功能
            # 图标大小保持不变，无论其位置如何
            
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        self.dragging = False
        
        # 移除缩放动画恢复功能
            
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        # 打开设置对话框
        self.showSettingsDialog()
        super().mouseDoubleClickEvent(event)
        
    def wheelEvent(self, event):
        # 使用滚轮调整大小
        delta = event.angleDelta().y()
        scale_factor = 1.05 if delta > 0 else 0.95
        
        # 记录旧尺寸和当前位置
        old_size = self.current_size
        current_pos = self.pos()
        
        # 计算新尺寸
        new_width = max(30, min(200, int(self.current_size.width() * scale_factor)))
        new_height = max(30, min(200, int(self.current_size.height() * scale_factor)))
        self.current_size = QSize(new_width, new_height)
        
        # 应用新尺寸到动画
        if hasattr(self, 'movie') and self.movie:
            self.movie.setScaledSize(self.current_size)
        
        # 调整UI布局，而不是整个窗口大小
        if self.main_window and self.enable_window_scaling:
            # 通知布局调整
            self.updateLayout()
    
    def updateLayout(self):
        """优化的布局更新方法"""
        # 获取父布局
        if not self.parent() or not self.parent().layout():
            return
            
        # 强制更新一次布局
        self.parent().layout().activate()
        
        # 查找滚动区域
        scroll_area = self.findScrollArea(self.main_window)
        if scroll_area and scroll_area.widget() and scroll_area.widget().layout():
            content = scroll_area.widget()
            
            # 根据图标状态设置合适的边距
            if self.is_visible:
                size_ratio = min(2.0, max(0.5, self.current_size.width() / 60.0))
                margin = min(25, max(5, int(10 * size_ratio)))
                spacing = max(3, int(6 * size_ratio))
            else:
                margin = 5
                spacing = 3
            
            # 批量更新布局属性
            content.layout().setContentsMargins(margin, margin, margin, margin)
            content.layout().setSpacing(spacing)
            
            # 一次性触发布局更新
            content.layout().invalidate()
            content.layout().activate()
    
    def findScrollArea(self, widget):
        """递归查找窗口中的第一个QScrollArea"""
        if isinstance(widget, QScrollArea):
            return widget
            
        for child in widget.findChildren(QWidget):
            if isinstance(child, QScrollArea):
                return child
                
        return None

    def showSettingsDialog(self):
        # 创建设置对话框
        dialog = QDialog(self.window())
        dialog.setWindowTitle("图标设置")
        dialog.setMinimumWidth(300)
        dialog_layout = QVBoxLayout(dialog)
        
        # 添加图标选择部分
        icon_group = QGroupBox("图标选择")
        icon_layout = QVBoxLayout(icon_group)
        
        # 添加内置图标选择
        built_in_layout = QHBoxLayout()
        built_in_layout.addWidget(QLabel("内置图标:"))
        built_in_combo = QComboBox()
        built_in_combo.addItems(["标准动画", "控制版本", "控制Alt版本", "控制Shift版本", "猫咪动画"])
        # 尝试根据当前图标路径设置选中状态
        if hasattr(self, 'icon_path'):
            if "siri.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(0)
            elif "siri_ctrl.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(1)
            elif "siri_ctrlAlt.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(2)
            elif "siri_ctrlShift.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(3)
            elif "cat.gif" in self.icon_path:
                built_in_combo.setCurrentIndex(4)
                
        built_in_layout.addWidget(built_in_combo)
        icon_layout.addLayout(built_in_layout)
        
        # 添加自定义图标选择
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("自定义图标:"))
        custom_path = QLineEdit()
        custom_path.setReadOnly(True)
        # 如果是自定义图标，显示路径
        if hasattr(self, 'icon_path') and os.path.exists(self.icon_path):
            icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
            if not self.icon_path.startswith(icons_dir):
                custom_path.setText(self.icon_path)
                
        custom_layout.addWidget(custom_path)
        browse_button = QPushButton("浏览...")
        
        def browse_icon():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "选择图标文件", "", 
                "图像文件 (*.png *.jpg *.gif *.svg)"
            )
            if file_path:
                custom_path.setText(file_path)
        
        browse_button.clicked.connect(browse_icon)
        custom_layout.addWidget(browse_button)
        icon_layout.addLayout(custom_layout)
        
        # 添加窗口缩放效果选项
        effect_group = QGroupBox("UI效果")
        effect_layout = QVBoxLayout(effect_group)
        
        # 窗口缩放效果复选框
        scale_window_check = QCheckBox("图标缩放时调整界面布局")
        scale_window_check.setChecked(self.enable_window_scaling)
        effect_layout.addWidget(scale_window_check)
        
        # 添加字体大小调整
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("字体大小:"))
        font_size_slider = QSlider(Qt.Horizontal)
        font_size_slider.setMinimum(8)
        font_size_slider.setMaximum(32)  # 增加最大值，移除上限
        font_size_slider.setValue(self.font_size)
        font_size_layout.addWidget(font_size_slider)
        font_size_label = QLabel(f"{font_size_slider.value()}px")
        font_size_layout.addWidget(font_size_label)
        
        def update_font_size(value):
            font_size_label.setText(f"{value}px")
            # 创建新的字体并设置大小
            new_font = QFont()
            new_font.setPointSize(value)
            # 实时应用到主窗口
            if self.main_window:
                # 使用主窗口的更新字体大小方法
                self.main_window.update_font_size(value)
            
        font_size_slider.valueChanged.connect(update_font_size)
        effect_layout.addLayout(font_size_layout)
        
        # 添加窗口透明度调整
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("窗口透明度:"))
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setMinimum(50)
        opacity_slider.setMaximum(100)
        opacity_slider.setValue(int(self.main_window.windowOpacity() * 100) if self.main_window else 100)
        opacity_layout.addWidget(opacity_slider)
        opacity_label = QLabel(f"{opacity_slider.value()}%")
        opacity_layout.addWidget(opacity_label)
        
        def update_opacity(value):
            opacity_label.setText(f"{value}%")
            if self.main_window:
                self.main_window.setWindowOpacity(value / 100.0)
                
        opacity_slider.valueChanged.connect(update_opacity)
        effect_layout.addLayout(opacity_layout)
        
        # 添加尺寸调整部分
        size_group = QGroupBox("图标尺寸")
        size_layout = QVBoxLayout(size_group)
        
        size_slider_layout = QHBoxLayout()
        size_slider_layout.addWidget(QLabel("尺寸:"))
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setMinimum(30)
        size_slider.setMaximum(200)
        size_slider.setValue(self.current_size.width())
        size_slider_layout.addWidget(size_slider)
        size_label = QLabel(f"{self.current_size.width()}px")
        size_slider_layout.addWidget(size_label)
        
        def update_size_label(value):
            size_label.setText(f"{value}px")
            
        size_slider.valueChanged.connect(update_size_label)
        size_layout.addLayout(size_slider_layout)
        
        # 添加重置按钮
        reset_button = QPushButton("重置到默认值")
        
        def reset_to_default():
            size_slider.setValue(60)
            built_in_combo.setCurrentIndex(0)
            custom_path.setText("")
            opacity_slider.setValue(100)
            scale_window_check.setChecked(True)
            font_size_slider.setValue(11)  # 重置字体大小到默认值11px
            
        reset_button.clicked.connect(reset_to_default)
        
        # 添加确定和取消按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        def apply_settings():
            # 保存当前尺寸
            self.current_size = QSize(size_slider.value(), size_slider.value())
            
            # 保存窗口缩放设置
            self.enable_window_scaling = scale_window_check.isChecked()
            
            # 保存字体大小设置
            self.font_size = font_size_slider.value()
            
            # 应用选择的图标
            icon_path = ""
            if custom_path.text():
                icon_path = custom_path.text()
            else:
                # 根据内置图标选择相应文件
                icon_index = built_in_combo.currentIndex()
                icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
                if icon_index == 0:
                    icon_path = os.path.join(icons_dir, "siri.gif")
                elif icon_index == 1:
                    icon_path = os.path.join(icons_dir, "siri_ctrl.gif")  # 蓝色图标
                elif icon_index == 2:
                    icon_path = os.path.join(icons_dir, "siri_ctrlAlt.gif")  # 绿色图标
                elif icon_index == 3:
                    icon_path = os.path.join(icons_dir, "siri_ctrlShift.gif")  # 红色图标
                elif icon_index == 4:
                    icon_path = os.path.join(icons_dir, "cat.gif")  # 猫咪动画
            
            # 保存图标路径
            self.icon_path = icon_path
            
            # 加载新图标
            if os.path.exists(icon_path):
                if hasattr(self, 'movie') and self.movie:
                    self.movie.stop()
                
                # 根据文件类型选择加载方式
                if icon_path.lower().endswith(('.gif')):
                    movie = QMovie(icon_path)
                    movie.setScaledSize(self.current_size)
                    self.setMovie(movie)
                    self.movie = movie
                    movie.start()
                else:
                    pixmap = QPixmap(icon_path)
                    pixmap = pixmap.scaled(
                        self.current_size, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    self.setPixmap(pixmap)
                    if hasattr(self, 'movie'):
                        self.movie = None
            
            # 更新全局字体大小
            if self.main_window:
                self.main_window.update_font_size(self.font_size)
                        
            # 触发UI布局调整
            if scale_window_check.isChecked() and self.main_window:
                self.updateLayout()
            
            # 保存设置到Maya optionVar
            self.save_settings()
            
            dialog.accept()
            
        ok_button.clicked.connect(apply_settings)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 组装对话框
        dialog_layout.addWidget(icon_group)
        dialog_layout.addWidget(effect_group)
        dialog_layout.addWidget(size_group)
        dialog_layout.addLayout(button_layout)
        
        # 显示对话框
        dialog.exec_()


class CollapsibleGroupBox(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        
        # 创建切换按钮
        self.toggle_button = QPushButton(f"▼ {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        
        # 创建内容部件
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(2)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_widget)
        self.is_collapsed = False

        # 标题为骨骼Tag或FK层级设置的折叠组增加额外的最小高度
        self.special_group = title in ["骨骼Tag", "FK层级设置"]
        
        # 避免内容闪烁，初始设置不可见
        self.content_widget.setVisible(False)
        
        # 创建更复杂的动画系统
        # 1. 高度动画
        self.height_animation = QPropertyAnimation(self.content_widget, b"maximumHeight")
        self.height_animation.setDuration(200)  # 稍微增加时长，使动画更平滑
        self.height_animation.setEasingCurve(QEasingCurve.OutCubic)  # 使用更平滑的缓动效果
        
        # 2. 透明度动画
        self.opacity_effect = QGraphicsOpacityEffect(self.content_widget)
        self.opacity_effect.setOpacity(1.0)
        self.content_widget.setGraphicsEffect(self.opacity_effect)
        
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(150)  # 透明度动画比高度动画稍快
        
        # 3. 创建动画组
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(self.height_animation)
        self.animation_group.addAnimation(self.opacity_animation)
        self.animation_group.finished.connect(self.on_animation_finished)
        
        # 添加缓存内容高度，避免重复计算
        self._cached_content_height = 0
        
        # 确保内容高度为0
        self.content_widget.setMaximumHeight(0)
        
        # 延迟初始化，确保初始状态正确
        QTimer.singleShot(5, self.toggle_collapsed)

    def toggle_collapsed(self):
        # 停止所有正在进行的动画
        self.animation_group.stop()
        
        # 更新折叠状态
        self.is_collapsed = not self.is_collapsed

        # 设置文本和图标
        original_text = self.toggle_button.text().lstrip('▶▼ ')
        self.toggle_button.setText(
            f"{'▼' if not self.is_collapsed else '▶'} {original_text}"
        )
        
        # 获取主窗口实例以获取字体大小设置
        main_window = None
        parent_widget = self.parent()
        while parent_widget:
            if isinstance(parent_widget, CombinedTool):
                main_window = parent_widget
                break
            parent_widget = parent_widget.parent()
            
        # 获取字体大小，默认为12
        font_size = 12
        if main_window and hasattr(main_window, 'font_size'):
            font_size = main_window.font_size
            
        # 更新按钮样式
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #3A3A3A;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
                font-size: {font_size}px;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: #4A4A4A;
            }}
            QPushButton:pressed {{
                background-color: #353535;
            }}
        """)

        # 如果展开，先设置内容为可见
        if not self.is_collapsed:
            self.content_widget.setVisible(True)
            self.opacity_effect.setOpacity(0.0)
        
        # 计算内容高度
        if self._cached_content_height > 0 and not self.is_collapsed:
            content_height = self._cached_content_height
        else:
            # 计算内容的实际高度
            self.content_widget.adjustSize()
            content_height = self.content_layout.sizeHint().height() + 8
            
            # 如果是特殊组件，确保最小高度足够
            if self.special_group and not self.is_collapsed:
                content_height = max(content_height, 180)
                
            # 缓存计算结果
            if not self.is_collapsed:
                self._cached_content_height = content_height

        # 确保动画结束值不为0
        if not self.is_collapsed and content_height <= 0:
            content_height = 50
            self._cached_content_height = content_height
            
        # 设置高度动画参数
        self.height_animation.setStartValue(0 if not self.is_collapsed else content_height)
        self.height_animation.setEndValue(content_height if not self.is_collapsed else 0)
        
        # 设置透明度动画参数
        self.opacity_animation.setStartValue(0.0 if not self.is_collapsed else 1.0)
        self.opacity_animation.setEndValue(1.0 if not self.is_collapsed else 0.0)
        
        # 开始动画
        self.animation_group.start()
        
        # 更新布局
        self.updateGeometry()
        if self.parentWidget():
            self.parentWidget().updateGeometry()

    def on_animation_finished(self):
        """动画完成后的处理"""
        # 根据折叠状态设置最终状态
        if self.is_collapsed:
            self.content_widget.setVisible(False)
        else:
            self.content_widget.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        
        # 更新布局
        self.updateGeometry()
        if self.parentWidget():
            self.parentWidget().updateGeometry()

    def setLayout(self, layout):
        """设置内容布局"""
        # 清除旧布局内容
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # 添加新布局
        self.content_layout.addLayout(layout)
        
        # 重置缓存高度
        self._cached_content_height = 0
        
        # 如果当前未折叠，立即更新高度
        if not self.is_collapsed:
            self.content_widget.adjustSize()
            content_height = self.content_layout.sizeHint().height() + 8
            
            if self.special_group:
                content_height = max(content_height, 180)
                
            self.content_widget.setMaximumHeight(content_height)
            self._cached_content_height = content_height
            
            self.updateGeometry()
            if self.parentWidget():
                self.parentWidget().updateGeometry()


class CombinedTool(QMainWindow):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = CombinedTool()
        return cls._instance

    def __init__(self):
        super().__init__(parent=get_maya_main_window())
        self.setWindowTitle("综合工具")
        self.setObjectName("CombinedToolWindow")
        self.resize(420, 500)  # 设置默认窗口大小
        
        # 设置窗口标志
        try:
            self.setWindowFlags(Qt.Window)  # 移除 Qt.WindowStaysOnTopHint
        except:
            # 如果设置失败（可能是旧版本的Qt）
            pass

        # 重载controller_shapes模块以获取最新的形状
        try:
            importlib.reload(controller_shapes)
        except:
            # 导入失败时继续
            pass
        
        # 尝试恢复之前保存的窗口大小
        if cmds.optionVar(exists="CombinedToolWindowWidth") and cmds.optionVar(exists="CombinedToolWindowHeight"):
            width = cmds.optionVar(query="CombinedToolWindowWidth")
            height = cmds.optionVar(query="CombinedToolWindowHeight")
            if width > 200 and height > 300:  # 确保合理的最小大小
                self.resize(width, height)

        # 默认设置
        self.group_prefix = "zero"
        self.remove_prefix = True
        self.use_existing_suffix = True
        self.freeze_scale = True
        self.match_position = True
        self.match_rotation = True
        self.match_scale = False
        self.color_rgb = [1.0, 1.0, 1.0]
        self.use_hierarchy_logic = True
        self.controller_type = "sphere"
        self.create_joint_flag = False
        self.create_controller_flag = True
        self.create_sub_controller_flag = False
        self.enable_custom_group = False
        self.use_selection_count_flag = True
        self.tag_history = []
        self.custom_group_name = ""

        # 用于保存外部工具的实例
        
        # 获取保存的字体大小设置
        self.font_size = 11  # 默认字体大小
        if cmds.optionVar(exists="CKTool_FontSize"):
            self.font_size = cmds.optionVar(query="CKTool_FontSize")

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QWidget {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QPushButton {{
                background-color: #3E3E42;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 22px;
                font-size: {self.font_size}px;
            }}
            QPushButton:hover {{
                background-color: #505054;
                border-color: #6A6A6A;
            }}
            QPushButton:pressed {{
                background-color: #2A2A2A;
                border-color: #777777;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                selection-background-color: #264F78;
                font-size: {self.font_size}px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                min-height: 20px;
                font-size: {self.font_size}px;
            }}
            QComboBox:hover {{
                border-color: #6A6A6A;
            }}
            QComboBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QCheckBox {{
                color: #E0E0E0;
                spacing: 6px;
                font-size: {self.font_size}px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid #555555;
                border-radius: 2px;
                background-color: #333337;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0078D7;
                border-color: #0078D7;
            }}
            QCheckBox::indicator:hover {{
                border-color: #6A6A6A;
            }}
            QLabel {{
                color: #E0E0E0;
                font-size: {self.font_size}px;
            }}
            QScrollArea {{
                background-color: #2D2D30;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: #2D2D30;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555555;
                min-height: 20px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #6A6A6A;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: #2D2D30;
            }}
            QToolTip {{
                background-color: #2D2D30;
                color: #E0E0E0;
                border: 1px solid #555555;
                padding: 4px;
                opacity: 220;
                font-size: {self.font_size}px;
            }}
            QFrame[frameShape="4"] {{ /* 分隔线 */
                background-color: #555555;
                height: 1px;
                max-height: 1px;
            }}
        """)
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 添加可交互GIF动画
        self.gif_container = QWidget()
        # 设置最小高度，确保有足够的空间显示图标
        self.gif_container.setMinimumHeight(70)
        # 设置尺寸策略，允许收缩但优先保持最小高度
        self.gif_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        # 使用绝对定位布局，允许图标自由移动
        container_layout = QHBoxLayout(self.gif_container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.setContentsMargins(0, 0, 0, 0)
        # 添加对象名便于识别和样式化
        self.gif_container.setObjectName("gifContainer")
        
        # 创建交互式图标标签
        self.gif_label = InteractiveIconLabel(main_window=self)
        container_layout.addWidget(self.gif_label)
        
        # 先获取可见性状态，以便后续处理
        is_visible = self.gif_label.is_visible
        print(f"加载的可见性状态: {is_visible}")
        
        # 加载GIF - 使用保存的图标路径
        if hasattr(self.gif_label, 'icon_path') and os.path.exists(self.gif_label.icon_path):
            if self.gif_label.icon_path.lower().endswith('.gif'):
                movie = QMovie(self.gif_label.icon_path)
                movie.setScaledSize(self.gif_label.current_size)
                self.gif_label.setMovie(movie)
                self.gif_label.movie = movie
                movie.start()
            else:
                pixmap = QPixmap(self.gif_label.icon_path)
                pixmap = pixmap.scaled(
                    self.gif_label.current_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.gif_label.setPixmap(pixmap)
                self.gif_label.movie = None
        else:
            # 默认图标
            gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "siri.gif")
            if os.path.exists(gif_path):
                movie = QMovie(gif_path)
                movie.setScaledSize(self.gif_label.current_size)
                self.gif_label.setMovie(movie)
                self.gif_label.movie = movie
                movie.start()
                self.gif_label.icon_path = gif_path
            
        # 设置图标在容器中的初始垂直位置
        # 在布局更新后用QTimer延迟执行，确保容器大小已经计算好
        QTimer.singleShot(100, self.center_icon_vertically)
        
        # 如果之前保存了位置信息，恢复位置
        if cmds.optionVar(exists="CKTool_IconX") and cmds.optionVar(exists="CKTool_IconY"):
            x = cmds.optionVar(query="CKTool_IconX")
            y = cmds.optionVar(query="CKTool_IconY")
            QTimer.singleShot(200, lambda: self.gif_label.move(x, y))
        
        # 确保图标容器有正确的初始状态
        if is_visible:
            self.gif_container.setMinimumHeight(70)
        else:
            self.gif_container.setMinimumHeight(10)
        
        # 最后处理图标隐藏状态
        if not is_visible:
            # 使用单次计时器确保在UI完全初始化后再处理隐藏
            QTimer.singleShot(500, lambda: self._apply_icon_visibility(False))
        
        # 将GIF容器添加到主布局
        main_layout.addWidget(self.gif_container)
        
        # 为整个主窗口添加右键菜单功能
        main_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        main_widget.customContextMenuRequested.connect(self.showMainContextMenu)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("QFrame { border: 0.5px double #000000; }")
        main_layout.addWidget(separator)

        # 创建固定在顶部的控制区域
        fixed_controls_widget = QWidget()
        fixed_controls_layout = QVBoxLayout(fixed_controls_widget)
        fixed_controls_layout.setSpacing(5)
        fixed_controls_layout.setContentsMargins(10, 5, 10, 5)
        
        # 分隔线样式
        separator_style = "QFrame { border: 0.5px double #000000; }"

        # 添加控制器大小调整控件
        controller_size_layout = QHBoxLayout()
        controller_size_label = QLabel("曲线大小:")
        controller_size_label.setFixedWidth(80)
        self.scale_factor_input = QDoubleSpinBox()
        self.scale_factor_input.setRange(0.1, 10.0)
        self.scale_factor_input.setValue(1)
        self.scale_factor_input.setSingleStep(0.1)
        self.scale_factor_input.setDecimals(2)
        self.scale_factor_input.setToolTip("输入缩放倍率（0.1-10.0）")
        scale_up_button = DelayedToolTipButton("变大", "按倍率放大控制顶点，要保证输入不小于1")
        scale_up_button.clicked.connect(self.scale_cv_handles_up)
        scale_down_button = DelayedToolTipButton("变小", "按倍率缩小控制顶点，要保证输入不小于1")
        scale_down_button.clicked.connect(self.scale_cv_handles_down)
        controller_size_layout.addWidget(controller_size_label)
        controller_size_layout.addWidget(self.scale_factor_input)
        controller_size_layout.addWidget(scale_up_button)
        controller_size_layout.addWidget(scale_down_button)
        fixed_controls_layout.addLayout(controller_size_layout)

        # 添加曲线粗细调整控件
        curve_width_layout = QHBoxLayout()
        curve_width_label = QLabel("曲线粗细:")
        curve_width_label.setFixedWidth(80)
        self.curve_width_input = QSpinBox()
        self.curve_width_input.setRange(1, 20)
        self.curve_width_input.setValue(1)
        self.curve_width_input.setSingleStep(1)
        self.curve_width_input.setToolTip("设置曲线粗细值（1-20）")
        apply_curve_width_button = DelayedToolTipButton("应用粗细", "为选中的曲线设置指定的粗细值")
        apply_curve_width_button.clicked.connect(self.apply_curve_width)
        curve_width_layout.addWidget(curve_width_label)
        curve_width_layout.addWidget(self.curve_width_input)
        curve_width_layout.addWidget(apply_curve_width_button)
        fixed_controls_layout.addLayout(curve_width_layout)

        # 添加位移旋转缩放重置按钮
        reset_layout = QHBoxLayout()
        reset_pos_button = DelayedToolTipButton("位移归0", "将选中物体的平移值重置为 (0, 0, 0)")
        reset_pos_button.clicked.connect(self.reset_position)
        reset_layout.addWidget(reset_pos_button)
        reset_rot_button = DelayedToolTipButton("旋转归0", "将选中物体的旋转值重置为 (0, 0, 0)")
        reset_rot_button.clicked.connect(self.reset_rotation)
        reset_layout.addWidget(reset_rot_button)
        reset_scale_button = DelayedToolTipButton("缩放归1", "将选中物体的缩放值重置为 (1, 1, 1)")
        reset_scale_button.clicked.connect(self.reset_scale)
        reset_layout.addWidget(reset_scale_button)
        fixed_controls_layout.addLayout(reset_layout)
        
        # 将固定控制区域添加到主布局
        main_layout.addWidget(fixed_controls_widget)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        main_layout.addWidget(separator)

        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        scroll_layout.addWidget(separator)

        # 控制器颜色 - 移动到创建关节与控制器组件的上面
        color_group = CollapsibleGroupBox("控制器颜色")
        color_layout = QGridLayout()
        color_layout.setSpacing(5)
        # 移除颜色选择按钮和标签
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(100, 24)  # 略微增大尺寸
        self.color_preview.setStyleSheet("""
            border: 1px solid #666666; 
            border-radius: 5px;
            background-color: transparent;
        """)
        self.color_preview.setCursor(Qt.PointingHandCursor)  # 添加手型光标
        self.color_preview.mousePressEvent = lambda event: self.show_color_dialog()  # 使组件可点击

        # 添加悬停效果
        def preview_enter_event(event):
            r, g, b = [int(c * 255) for c in self.color_rgb]
            hex_color = QColor(r, g, b).name().upper()
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
            
            self.color_preview.setStyleSheet(f"""
                background-color: {hex_color}; 
                border: 2px solid #0078D7; 
                border-radius: 5px;
                color: {text_color};
                font-size: 10px;
                text-align: center;
                padding: 2px;
            """)

        def preview_leave_event(event):
            r, g, b = [int(c * 255) for c in self.color_rgb]
            hex_color = QColor(r, g, b).name().upper()
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
            
            self.color_preview.setStyleSheet(f"""
                background-color: {hex_color}; 
                border: 1px solid #666666; 
                border-radius: 5px;
                color: {text_color};
                font-size: 10px;
                text-align: center;
                padding: 2px;
            """)

        self.color_preview.enterEvent = preview_enter_event
        self.color_preview.leaveEvent = preview_leave_event

        self.update_color_preview()
        color_layout.addWidget(QLabel("颜色:"), 0, 0)
        color_layout.addWidget(self.color_preview, 0, 1)
        color_layout.addWidget(QLabel("预设颜色："), 1, 0)
        
        # 从颜色选择器.py引用颜色数组
        preset_colors = [
            # 第一行
            (0.5, 0.5, 0.5), (0, 0, 0), (0.247, 0.247, 0.247), (0.498, 0.498, 0.498),
            (0.608, 0, 0.157), (0, 0.16, 0.376), (0, 0, 1), (0, 0.275, 0.094),
            # 第二行
            (0.149, 0, 0.263), (0.78, 0, 0.78), (0.537, 0.278, 0.2), (0.243, 0.133, 0.121),
            (0.6, 0.145, 0), (1, 0, 0), (0, 1, 0), (0, 0.2549, 0.6),
            # 第三行
            (1, 1, 1), (1, 1, 0), (0.388, 0.863, 1), (0.263, 1, 0.639),
            (1, 0.686, 0.686), (0.89, 0.674, 0.474), (1, 1, 0.388), (0, 0.6, 0.329),
            # 第四行
            (0.627, 0.411, 0.188), (0.619, 0.627, 0.188), (0.408, 0.631, 0.188), (0.188, 0.631, 0.365),
            (0.188, 0.627, 0.627), (0.188, 0.403, 0.627), (0.434, 0.188, 0.627), (0.627, 0.188, 0.411)
        ]
        
        # 创建颜色网格布局，8列4行
        preset_grid_layout = QGridLayout()
        preset_grid_layout.setSpacing(2)
        
        for i, color in enumerate(preset_colors):
            row = i // 8
            col = i % 8
            
            # 将RGB值转换为十六进制颜色
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(color[0] * 255),
                int(color[1] * 255),
                int(color[2] * 255)
            )
            
            color_button = DelayedToolTipButton("", f"应用颜色 {hex_color}")
            color_button.setFixedSize(20, 20)
            color_button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #666666; padding: 0px; min-width: 20px; min-height: 20px; max-width: 20px; max-height: 20px;")
            color_button.clicked.connect(lambda checked=False, rgb=color: (self.set_preset_color(rgb), self.apply_color_to_controller()))
            
            preset_grid_layout.addWidget(color_button, row, col)
        
        color_layout.addLayout(preset_grid_layout, 1, 1)
        apply_color_button = DelayedToolTipButton("应用颜色", "将当前颜色应用到选中的控制器")
        apply_color_button.clicked.connect(self.apply_color_to_controller)
        color_layout.addWidget(apply_color_button, 2, 0, 1, 2)
        
        # 应用颜色和重置颜色按钮 - 横向平均分布
        apply_reset_layout = QHBoxLayout()
        apply_reset_layout.setSpacing(5)  # 设置按钮间距
        
        reset_color_button = DelayedToolTipButton("重置颜色", "将绘制覆盖从RGB改为索引，然后关闭启用覆盖")
        reset_color_button.clicked.connect(self.reset_color)
        apply_reset_layout.addWidget(reset_color_button, 1)  # stretch factor = 1
        
        color_layout.addLayout(apply_reset_layout, 3, 0, 1, 2)
        
        # 随机颜色和渐变颜色按钮 - 横向平均分布
        color_buttons_layout = QHBoxLayout()
        color_buttons_layout.setSpacing(5)  # 设置按钮间距
        
        random_color_button = DelayedToolTipButton("随机颜色", "为选中的物体赋予随机颜色材质")
        random_color_button.clicked.connect(self.apply_random_colors)
        color_buttons_layout.addWidget(random_color_button, 1)  # stretch factor = 1
        
        gradient_color_button = DelayedToolTipButton("渐变颜色", "打开渐变颜色工具，为选中的物体应用渐变色彩效果")
        gradient_color_button.clicked.connect(self.open_gradient_color_tool)
        color_buttons_layout.addWidget(gradient_color_button, 1)  # stretch factor = 1
        
        color_layout.addLayout(color_buttons_layout, 4, 0, 1, 2)
        
        color_group.setLayout(color_layout)
        scroll_layout.addWidget(color_group)

        # 关节与控制器创建
        joint_ctrl_group = CollapsibleGroupBox("创建关节与控制器")
        joint_ctrl_layout = QVBoxLayout()
        joint_ctrl_layout.setSpacing(5)

        custom_group_layout = QHBoxLayout()
        custom_group_label = QLabel("自定义组名称:")
        self.custom_group_input = QLineEdit()
        self.custom_group_input.setPlaceholderText("输入组名（创建的控制器放入的位置）")
        self.enable_custom_group_check = QCheckBox("启用自定义组")
        self.enable_custom_group_check.setChecked(False)
        self.enable_custom_group_check.stateChanged.connect(self.toggle_custom_group)
        custom_group_layout.addWidget(custom_group_label)
        custom_group_layout.addWidget(self.custom_group_input)
        custom_group_layout.addWidget(self.enable_custom_group_check)
        joint_ctrl_layout.addLayout(custom_group_layout)

        main_settings_layout = QGridLayout()
        main_settings_layout.addWidget(QLabel("名称："), 0, 0)
        self.name_text = QLineEdit("")
        main_settings_layout.addWidget(self.name_text, 0, 1)
        main_settings_layout.addWidget(QLabel("侧面："), 0, 2)
        self.side_text = QLineEdit("")
        self.side_text.setToolTip("可用逗号隔开来创建多个侧面，例如 'l,r,m'")  # 添加工具提示
        main_settings_layout.addWidget(self.side_text, 0, 3)
        main_settings_layout.addWidget(QLabel("控制器大小："), 1, 0)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setMinimum(0.1)
        self.size_spin.setValue(1.0)
        main_settings_layout.addWidget(self.size_spin, 1, 1)
        main_settings_layout.addWidget(QLabel("数量："), 1, 2)
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setValue(1)
        main_settings_layout.addWidget(self.count_spin, 1, 3)
        main_settings_layout.addWidget(QLabel("控制器类型："), 2, 0)
        self.controller_combo = QComboBox()
        self.controller_combo.addItems(["球形 (Sphere)", "立方体 (Cube)", "圆形 (Circle)",
                                        "箭头 (Arrow)", "齿轮 (Gear)", "圆锥 (Cone)",
                                        "十字 (Cross)", "钻石 (Diamond)", "矩形 (Rectangle)",
                                        "正方形 (Square)"])
        self.controller_combo.currentTextChanged.connect(self.update_controller_type)
        main_settings_layout.addWidget(self.controller_combo, 2, 1, 1, 3)
        # 创建关节选项行，包含识别物体名称和忽略后缀选项
        joint_options_layout = QHBoxLayout()
        self.create_joint_check = QCheckBox("创建关节")
        self.create_joint_check.setChecked(False)
        self.create_joint_check.stateChanged.connect(self.toggle_create_joint)
        joint_options_layout.addWidget(self.create_joint_check)
        
        # 物体名称识别选项
        self.auto_name_from_joint_check = QCheckBox("识别物体名称")
        self.auto_name_from_joint_check.setChecked(False)
        self.auto_name_from_joint_check.setToolTip("自动从选中物体名称识别控制器名称\n支持骨骼格式：jnt_m_aaa_001 -> ctrl_m_aaa_001\n支持其他物体：任意物体名称都可识别\n如果不符合格式则使用完整物体名称")
        joint_options_layout.addWidget(self.auto_name_from_joint_check)
        
        joint_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(joint_options_layout, 3, 0, 1, 4)
        
        # 创建控制器选项行，包含忽略后缀选项
        controller_options_layout = QHBoxLayout()
        self.create_controller_check = QCheckBox("创建控制器")
        self.create_controller_check.setChecked(True)
        self.create_controller_check.stateChanged.connect(self.toggle_create_controller)
        controller_options_layout.addWidget(self.create_controller_check)
        
        # 忽略后缀选项
        self.ignore_suffix_check = QCheckBox("忽略后缀")
        self.ignore_suffix_check.setChecked(True)
        self.ignore_suffix_check.setToolTip("识别物体名称时忽略末尾的后缀\n例如：object_001、object1、object_a 都会被识别为 object")
        controller_options_layout.addWidget(self.ignore_suffix_check)
        
        controller_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(controller_options_layout, 4, 0, 1, 4)
        
        # 创建层级关系选项行
        hierarchy_options_layout = QHBoxLayout()
        self.controller_parent_original_check = QCheckBox("控制器作为原物体父级")
        self.controller_parent_original_check.setChecked(False)
        self.controller_parent_original_check.setToolTip("生成后原物体会在控制器的子级")
        self.controller_parent_original_check.stateChanged.connect(self.toggle_controller_parent_original)
        hierarchy_options_layout.addWidget(self.controller_parent_original_check)
        
        self.original_parent_controller_check = QCheckBox("原物体作为控制器父级")
        self.original_parent_controller_check.setChecked(False)
        self.original_parent_controller_check.setToolTip("生成后控制器会在原物体的子级")
        self.original_parent_controller_check.stateChanged.connect(self.toggle_original_parent_controller)
        hierarchy_options_layout.addWidget(self.original_parent_controller_check)
        
        hierarchy_options_layout.addStretch()  # 添加弹性空间
        main_settings_layout.addLayout(hierarchy_options_layout, 5, 0, 1, 4)
        
        self.create_sub_controller_check = QCheckBox("创建子控制器")
        self.create_sub_controller_check.setChecked(False)
        self.create_sub_controller_check.stateChanged.connect(self.toggle_create_sub_controller)
        main_settings_layout.addWidget(self.create_sub_controller_check, 6, 0, 1, 2)
        self.hierarchy_check = QCheckBox("使用层级组逻辑")
        self.hierarchy_check.setChecked(True)
        self.hierarchy_check.stateChanged.connect(self.toggle_hierarchy_logic)
        main_settings_layout.addWidget(self.hierarchy_check, 6, 2, 1, 2)
        
        # 根据选择物体数量创建选项 - 默认开启，不显示UI
        # self.use_selection_count_check = QCheckBox("根据选择物体数量创建")
        # self.use_selection_count_check.setChecked(True)
        # self.use_selection_count_check.setToolTip("启用后，将根据当前选择的物体数量创建对应数量的关节和控制器\n例如：选择5个物体就创建5个关节控制器组合")
        # self.use_selection_count_check.stateChanged.connect(self.toggle_use_selection_count)
        # main_settings_layout.addWidget(self.use_selection_count_check, 6, 0, 1, 4)
        
        joint_ctrl_layout.addLayout(main_settings_layout)

        match_group = CollapsibleGroupBox("匹配变换")
        match_layout = QGridLayout()
        match_layout.setSpacing(5)
        self.match_position_check = QCheckBox("匹配平移")
        self.match_position_check.setChecked(True)
        self.match_position_check.stateChanged.connect(self.toggle_match_position)
        match_layout.addWidget(self.match_position_check, 0, 0)
        self.match_rotation_check = QCheckBox("匹配旋转")
        self.match_rotation_check.setChecked(True)
        self.match_rotation_check.stateChanged.connect(self.toggle_match_rotation)
        match_layout.addWidget(self.match_rotation_check, 1, 0)
        self.match_scale_check = QCheckBox("匹配缩放")
        self.match_scale_check.setChecked(False)
        self.match_scale_check.stateChanged.connect(self.toggle_match_scale)
        match_layout.addWidget(self.match_scale_check, 2, 0)

        # 添加匹配变换按钮
        match_button = DelayedToolTipButton("应用匹配", "将选中的物体匹配到最后一个选中的物体")
        match_button.clicked.connect(self.match_selected_transforms)
        match_layout.addWidget(match_button, 3, 0)

        match_group.setLayout(match_layout)
        joint_ctrl_layout.addWidget(match_group)

        create_button = DelayedToolTipButton("创建", "根据选择数量创建关节和/或控制器，根据匹配变换设置匹配变换")
        create_button.clicked.connect(self.create_joint_and_controller)
        joint_ctrl_layout.addWidget(create_button)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        joint_ctrl_layout.addWidget(separator)

        # 第一行：镜像曲线形状、替换曲线形状、添加形状节点
        first_row_layout = QHBoxLayout()
        first_row_layout.setSpacing(5)  # 设置按钮间距
        
        mirror_curve_button = DelayedToolTipButton("镜像曲线形状",
                                                   "选择两个曲线，将第一个曲线的形状沿 X 轴镜像到第二个")
        mirror_curve_button.clicked.connect(self.open_mirror_curve_shape)
        first_row_layout.addWidget(mirror_curve_button, 1)  # stretch factor = 1
        
        trans_curve_button = DelayedToolTipButton("替换曲线形状", "将源曲线的形状复制到目标曲线，替换目标曲线的现有形状")
        trans_curve_button.clicked.connect(self.open_trans_curve_shape)
        first_row_layout.addWidget(trans_curve_button, 1)  # stretch factor = 1
        
        reparent_shape_button = DelayedToolTipButton("添加形状节点",
                                                     "将选中物体的形状节点添加到最后一个选中的目标物体下")
        reparent_shape_button.clicked.connect(self.reparent_shape_nodes)
        first_row_layout.addWidget(reparent_shape_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(first_row_layout)
        
        # 第二行：曲线Shape重命名、切换显示在前面
        second_row_layout = QHBoxLayout()
        second_row_layout.setSpacing(5)  # 设置按钮间距
        
        rename_curve_shapes_button = DelayedToolTipButton("曲线Shape重命名",
                                                          "自动识别场景中所有曲线并重命名其Shape节点")
        rename_curve_shapes_button.clicked.connect(self.auto_rename_curve_shapes)
        second_row_layout.addWidget(rename_curve_shapes_button, 1)  # stretch factor = 1
        
        always_draw_on_top_button = DelayedToolTipButton("切换显示在前面",
                                                         "切换选中曲线的alwaysDrawOnTop属性，使其显示在其他物体前面")
        always_draw_on_top_button.clicked.connect(self.toggle_always_draw_on_top)
        second_row_layout.addWidget(always_draw_on_top_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(second_row_layout)
        
        # 第三行：结合曲线、拆分曲线
        third_row_layout = QHBoxLayout()
        third_row_layout.setSpacing(5)  # 设置按钮间距
        
        combine_curves_button = DelayedToolTipButton("结合曲线",
                                                     "将选中的多个曲线合并为一个曲线对象")
        combine_curves_button.clicked.connect(self.combine_selected_curves)
        third_row_layout.addWidget(combine_curves_button, 1)  # stretch factor = 1
        
        separate_curves_button = DelayedToolTipButton("拆分曲线",
                                                      "将包含多个形状的曲线拆分为独立的曲线对象")
        separate_curves_button.clicked.connect(self.separate_selected_curves)
        third_row_layout.addWidget(separate_curves_button, 1)  # stretch factor = 1
        joint_ctrl_layout.addLayout(third_row_layout)

        # 添加FK层级功能
        fk_hierarchy_separator = QFrame()
        fk_hierarchy_separator.setFrameShape(QFrame.HLine)
        fk_hierarchy_separator.setStyleSheet(separator_style)
        joint_ctrl_layout.addWidget(fk_hierarchy_separator)

        fk_hierarchy_group = CollapsibleGroupBox("FK层级设置")
        fk_hierarchy_layout = QVBoxLayout()
        fk_hierarchy_layout.setSpacing(8)  # 增加间距使布局更清晰
        
        # 添加提示信息
        info_label = QLabel("注：FK层级将使用上方「创建关节与控制器」的设置")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #999999; font-style: italic;")
        fk_hierarchy_layout.addWidget(info_label)
        
        # 排除最后一个骨骼选项
        self.exclude_last_joint_check = QCheckBox("排除最后一个骨骼")
        self.exclude_last_joint_check.setChecked(True)
        self.exclude_last_joint_check.setToolTip("创建FK层级时排除骨骼链中的最后一个骨骼")
        fk_hierarchy_layout.addWidget(self.exclude_last_joint_check)
        
        
        # 创建约束框架
        constraints_group = QGroupBox("")
        constraints_layout = QGridLayout()
        constraints_layout.setVerticalSpacing(6)  # 增加垂直间距防止文字重叠
        constraints_layout.setHorizontalSpacing(10)  # 调整水平间距
        constraints_layout.setContentsMargins(10, 8, 10, 8)  # 增加边距

        # 使用两列布局：左侧是约束类型，右侧是偏移设置
        constraint_types = [
            ("父子约束", "parent_constraint_check", "parent_offset_check"),
            ("点约束", "point_constraint_check", "point_offset_check"),
            ("方向约束", "orient_constraint_check", "orient_offset_check"),
            ("缩放约束", "scale_constraint_check", "scale_offset_check")
        ]
        
        # 创建约束类型和偏移复选框
        for row, (label, constraint_attr, offset_attr) in enumerate(constraint_types):
            # 约束类型
            setattr(self, constraint_attr, QCheckBox(label))
            constraint_check = getattr(self, constraint_attr)
            constraint_check.setMinimumWidth(80)  # 确保有足够宽度显示文字
            constraints_layout.addWidget(constraint_check, row, 0)
            
            # 如果是父子约束，默认选中
            if constraint_attr == "parent_constraint_check":
                constraint_check.setChecked(True)
            
            # 偏移设置
            setattr(self, offset_attr, QCheckBox("保持偏移"))
            offset_check = getattr(self, offset_attr)
            offset_check.setMinimumWidth(80)  # 确保有足够宽度显示文字
            constraints_layout.addWidget(offset_check, row, 1)

        constraints_group.setLayout(constraints_layout)
        fk_hierarchy_layout.addWidget(constraints_group)

        # 创建FK层级按钮 - 使其更醒目
        create_fk_hierarchy_button = DelayedToolTipButton("创建FK层级", "为选中的骨骼链创建FK控制器层级")
        create_fk_hierarchy_button.setMinimumHeight(30)  # 增加按钮高度
        create_fk_hierarchy_button.setStyleSheet("""
            QPushButton {
                background-color: #4d90fe; 
                color: white; 
                border-radius: 3px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3c7ae6;
            }
            QPushButton:pressed {
                background-color: #356ac3;
            }
        """)
        create_fk_hierarchy_button.clicked.connect(self.create_fk_hierarchy)
        fk_hierarchy_layout.addWidget(create_fk_hierarchy_button)

        fk_hierarchy_group.setLayout(fk_hierarchy_layout)
        joint_ctrl_layout.addWidget(fk_hierarchy_group)

        joint_ctrl_group.setLayout(joint_ctrl_layout)
        scroll_layout.addWidget(joint_ctrl_group)

        # 分组与前缀设置
        group_prefix_group = CollapsibleGroupBox("分组与前缀设置")
        group_prefix_layout = QGridLayout()
        group_prefix_layout.setSpacing(5)
        group_prefix_layout.addWidget(QLabel("自定义前缀："), 0, 0)
        self.prefix_text = QLineEdit()
        self.prefix_text.textChanged.connect(self.update_custom_prefix)
        group_prefix_layout.addWidget(self.prefix_text, 0, 1)
        group_prefix_layout.addWidget(QLabel("预设前缀："), 1, 0)
        self.prefix_combo = QComboBox()
        self.prefix_combo.addItems(["zero", "driven", "connect", "offset", "space"])
        self.prefix_combo.currentTextChanged.connect(self.update_group_prefix)
        group_prefix_layout.addWidget(self.prefix_combo, 1, 1)
        group_prefix_layout.addWidget(QLabel("分组与层级："), 2, 0)
        self.remove_prefix_check = QCheckBox("去除前缀")
        self.remove_prefix_check.setChecked(True)
        self.remove_prefix_check.stateChanged.connect(self.toggle_remove_prefix)
        group_prefix_layout.addWidget(self.remove_prefix_check, 2, 1)
        self.use_existing_suffix_check = QCheckBox("使用现有后缀")
        self.use_existing_suffix_check.setChecked(True)
        self.use_existing_suffix_check.stateChanged.connect(self.toggle_use_existing_suffix)
        group_prefix_layout.addWidget(self.use_existing_suffix_check, 3, 1)
        self.freeze_scale_check = QCheckBox("冻结缩放")
        self.freeze_scale_check.setChecked(True)
        self.freeze_scale_check.stateChanged.connect(self.toggle_freeze_scale)
        group_prefix_layout.addWidget(self.freeze_scale_check, 4, 1)
        create_group_button = DelayedToolTipButton("创建组", "为选中的物体创建组并匹配变换")
        create_group_button.clicked.connect(self.create_group_for_selected)
        group_prefix_layout.addWidget(create_group_button, 5, 0, 1, 2)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(separator_style)
        group_prefix_layout.addWidget(separator, 6, 0, 1, 2)

        # 创建控制器层级操作按钮 - 双排布局，平均分布
        # 第一行：添加控制器层级、控制器层级次级控制器
        controller_first_row_layout = QHBoxLayout()
        controller_first_row_layout.setSpacing(5)  # 设置按钮间距
        add_hierarchy_button = DelayedToolTipButton("添加控制器层级", "为选中的控制器添加层级结构")
        add_hierarchy_button.clicked.connect(self.add_controller_hierarchy)
        controller_first_row_layout.addWidget(add_hierarchy_button, 1)  # 使用stretch factor平均分布
        
        ctrl_connect_button = DelayedToolTipButton("控制器层级次级控制器", "为选中的控制器创建层级结构和次级控制器")
        ctrl_connect_button.clicked.connect(self.open_ctrl_connect)
        controller_first_row_layout.addWidget(ctrl_connect_button, 1)  # 使用stretch factor平均分布
        
        # 第二行：选定物体创建控制器、基础层级
        controller_second_row_layout = QHBoxLayout()
        controller_second_row_layout.setSpacing(5)  # 设置按钮间距
        create_obj_ctrl_button = DelayedToolTipButton("选定物体创建控制器", "为选定的物体创建控制器并匹配变换")
        create_obj_ctrl_button.clicked.connect(self.open_object_creation_controller)
        controller_second_row_layout.addWidget(create_obj_ctrl_button, 1)  # 使用stretch factor平均分布
        
        create_controller_hierarchy_button = DelayedToolTipButton("基础层级", "创建包含控制器和层级结构的骨骼系统")
        create_controller_hierarchy_button.clicked.connect(self.open_create_controller_hierarchy)
        controller_second_row_layout.addWidget(create_controller_hierarchy_button, 1)  # 使用stretch factor平均分布
        
        # 将两行布局添加到主布局中
        group_prefix_layout.addLayout(controller_first_row_layout, 7, 0, 1, 2)
        group_prefix_layout.addLayout(controller_second_row_layout, 8, 0, 1, 2)
        # 添加父子物体创建折叠组件到分组与前缀设置中
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet(separator_style)
        group_prefix_layout.addWidget(separator2, 9, 0, 1, 2)
        
        # 创建父子物体创建折叠组件
        parent_child_group = CollapsibleGroupBox("父子物体创建")
        parent_child_layout = QVBoxLayout()
        parent_child_layout.setSpacing(5)
        
        # 添加创建类型选择复选框
        self.create_locator_check = QCheckBox("创建Locator")
        self.create_locator_check.setChecked(True)
        self.create_locator_check.setToolTip("勾选创建Locator，取消勾选创建空组")
        parent_child_layout.addWidget(self.create_locator_check)
        
        create_under_button = DelayedToolTipButton("在物体层级下创建", "为选中物体在其层级下创建locator或空组，匹配变换并保持层级结构")
        create_under_button.clicked.connect(self.create_object_under)
        parent_child_layout.addWidget(create_under_button)
        
        create_above_button = DelayedToolTipButton("在物体层级上创建", "为选中物体在其层级上创建locator或空组，匹配变换并保持层级结构")
        create_above_button.clicked.connect(self.create_object_above)
        parent_child_layout.addWidget(create_above_button)
        
        parent_child_group.setLayout(parent_child_layout)
        group_prefix_layout.addWidget(parent_child_group, 16, 0, 1, 2)
        
        group_prefix_group.setLayout(group_prefix_layout)
        scroll_layout.addWidget(group_prefix_group)

        # 创建Tag并选择
        tag_group = CollapsibleGroupBox("创建Tag并选择")
        tag_layout = QVBoxLayout()
        tag_layout.setSpacing(5)

        tag_name_layout = QHBoxLayout()
        tag_name_label = QLabel("Tag 名称:")
        tag_name_layout.addWidget(tag_name_label)
        self.tag_name_input = QLineEdit("isCtrl")
        tag_name_layout.addWidget(self.tag_name_input)
        tag_layout.addLayout(tag_name_layout)

        # 第一行：添加Tag、选择有tag的物体
        tag_first_row_layout = QHBoxLayout()
        tag_first_row_layout.setSpacing(5)  # 设置按钮间距
        
        add_tag_button = DelayedToolTipButton("添加Tag", "为选中的物体添加指定的 Tag 属性")
        add_tag_button.clicked.connect(self.add_tag_attribute)
        tag_first_row_layout.addWidget(add_tag_button, 1)  # stretch factor = 1

        select_tag_button = DelayedToolTipButton("选择有tag的物体", "选择场景中具有指定 Tag 的所有物体")
        select_tag_button.clicked.connect(self.select_objects_with_tag)
        tag_first_row_layout.addWidget(select_tag_button, 1)  # stretch factor = 1
        
        tag_layout.addLayout(tag_first_row_layout)
        
        # 第二行：删除Tag、识别选中物体的Tag
        tag_second_row_layout = QHBoxLayout()
        tag_second_row_layout.setSpacing(5)  # 设置按钮间距

        remove_tag_button = DelayedToolTipButton("删除 Tag", "从选中的物体上删除指定的 Tag 属性")
        remove_tag_button.clicked.connect(self.remove_tag_attribute)
        tag_second_row_layout.addWidget(remove_tag_button, 1)  # stretch factor = 1

        identify_tag_button = DelayedToolTipButton("识别选中物体的 Tag", "识别并列出选中物体的所有布尔 Tag")
        identify_tag_button.clicked.connect(self.identify_object_tags)
        tag_second_row_layout.addWidget(identify_tag_button, 1)  # stretch factor = 1
        
        tag_layout.addLayout(tag_second_row_layout)

        tag_history_label = QLabel("历史 Tag 记录:")
        tag_layout.addWidget(tag_history_label)
        self.tag_history_combo = QComboBox()
        self.tag_history_combo.addItem("无记录")
        self.tag_history_combo.currentTextChanged.connect(self.on_tag_history_selected)
        tag_layout.addWidget(self.tag_history_combo)

        clear_history_button = DelayedToolTipButton("清空历史 Tag 记录", "清空所有保存的历史 Tag 记录")
        clear_history_button.clicked.connect(self.clear_tag_history)
        tag_layout.addWidget(clear_history_button)

        tag_layout.addSpacing(5)

        tag_group.setLayout(tag_layout)
        scroll_layout.addWidget(tag_group)

        # 添加独立的骨骼Tag组件
        joint_tag_group = CollapsibleGroupBox("骨骼Tag")
        joint_tag_layout = QVBoxLayout()
        joint_tag_layout.setSpacing(5)
        joint_tag_v1_button = DelayedToolTipButton("骨骼绘制标签", "切换骨骼的绘制标签显示开关，优先对选中骨骼操作，无选择时对所有骨骼操作")
        joint_tag_v1_button.clicked.connect(self.open_joint_tag_v1)
        joint_tag_layout.addWidget(joint_tag_v1_button)
        joint_tag_v2_button = DelayedToolTipButton("通用骨骼Tag", "运行 joint_TagV2.py，为场景中所有关节添加通用标签")
        joint_tag_v2_button.clicked.connect(self.open_joint_tag_v2)
        joint_tag_layout.addWidget(joint_tag_v2_button)
        joint_tag_group.setLayout(joint_tag_layout)
        scroll_layout.addWidget(joint_tag_group)



    @with_undo_support
    def scale_cv_handles_up(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = self.scale_factor_input.value()
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        scaled_vector = [v * scale_factor for v in vector]
                        new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                        cmds.xform(cv, worldSpace=True, translation=new_pos)
                print(f"已将控制器 '{ctrl}' 的控制顶点按倍率 {scale_factor} 放大")
            else:
                print(f"物体 '{ctrl}' 不是 NURBS 曲线，跳过调整")

    @with_undo_support
    def scale_cv_handles_down(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = 1.0 / self.scale_factor_input.value()
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        scaled_vector = [v * scale_factor for v in vector]
                        new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                        cmds.xform(cv, worldSpace=True, translation=new_pos)
                print(f"已将控制器 '{ctrl}' 的控制顶点按倍率 {1.0 / scale_factor} 缩小")
            else:
                print(f"物体 '{ctrl}' 不是 NURBS 曲线，跳过调整")

    def get_cv_handle_scale(self):
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            print("未选择任何控制器，返回默认值 50")
            return 50.0

        total_scale = 0.0
        count = 0
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls(f"{ctrl}.cv[*]", flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        magnitude = math.sqrt(sum(v * v for v in vector))
                        total_scale += magnitude * 50.0
                        count += 1

        if count > 0:
            avg_scale = total_scale / count
            print(f"计算得到控制器平均缩放值: {avg_scale}")
            return avg_scale
        else:
            print("未找到任何控制顶点，返回默认值 50")
            return 50.0

    @with_undo_support
    def apply_curve_width(self):
        """为选中的曲线设置指定的粗细值"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return
        
        width_value = self.curve_width_input.value()
        
        try:
            # 遍历所有选择的对象，查找它们的shape节点
            shape_nodes = []
            for obj in selected_objects:
                # 检查对象是否为transform节点
                if cmds.objectType(obj) == 'transform':
                    # 获取transform下的所有shape节点
                    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
                    shape_nodes.extend(shapes)
                # 如果对象本身就是shape节点
                elif cmds.objectType(obj, isAType='shape'):
                    shape_nodes.append(obj)
            
            # 设置所有shape节点的lineWidth属性
            for shape in shape_nodes:
                if cmds.objExists(f'{shape}.lineWidth'):
                    cmds.setAttr(f'{shape}.lineWidth', width_value)
                    print(f"已将 '{shape}' 的线宽设置为 {width_value}")
        except Exception as e:
            cmds.warning(f"设置曲线粗细失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    @with_undo_support
    def combine_selected_curves(self):
        """结合选中的曲线"""
        combine_file = os.path.join(TOOL_DIR, "结合曲线.py")
        if not os.path.exists(combine_file):
            cmds.warning(f"未找到 结合曲线.py 文件: {combine_file}")
            return

        try:
            import importlib.util
            module_name = "结合曲线"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                combine_module = sys.modules[module_name]
                importlib.reload(combine_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, combine_file)
                combine_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = combine_module
                spec.loader.exec_module(combine_module)

            # 调用函数
            if hasattr(combine_module, "selected_curves_combine"):
                combine_module.selected_curves_combine()
                print("已运行 结合曲线.py 中的 selected_curves_combine 函数，结合选中的曲线")
            else:
                cmds.warning("结合曲线.py 中未找到 selected_curves_combine 函数")
        except Exception as e:
            cmds.warning(f"运行 结合曲线.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    @with_undo_support
    def separate_selected_curves(self):
        """拆分选中的曲线"""
        separate_file = os.path.join(TOOL_DIR, "拆分曲线.py")
        if not os.path.exists(separate_file):
            cmds.warning(f"未找到 拆分曲线.py 文件: {separate_file}")
            return

        try:
            import importlib.util
            module_name = "拆分曲线"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                separate_module = sys.modules[module_name]
                importlib.reload(separate_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, separate_file)
                separate_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = separate_module
                spec.loader.exec_module(separate_module)

            # 调用函数
            if hasattr(separate_module, "selected_curves_separate"):
                separate_module.selected_curves_separate()
                print("已运行 拆分曲线.py 中的 selected_curves_separate 函数，拆分选中的曲线")
            else:
                cmds.warning("拆分曲线.py 中未找到 selected_curves_separate 函数")
        except Exception as e:
            cmds.warning(f"运行 拆分曲线.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def update_color_preview(self):
        # 创建一个属性动画用于颜色变换
        animation = QPropertyAnimation(self.color_preview, b"palette")
        animation.setDuration(300)  # 300毫秒的动画时长
        animation.setEasingCurve(QEasingCurve.InOutQuad)

        # 获取当前调色板
        old_palette = self.color_preview.palette()
        new_palette = QPalette(old_palette)

        # 设置新的颜色
        new_color = QColor.fromRgbF(*self.color_rgb)
        new_palette.setColor(QPalette.Window, new_color)

        # 设置动画属性
        animation.setStartValue(old_palette)
        animation.setEndValue(new_palette)

        # 获取RGB值的十六进制表示
        hex_color = new_color.name().upper()
        
        # 计算亮度以确定文字颜色
        brightness = (0.299 * new_color.red() + 0.587 * new_color.green() + 0.114 * new_color.blue()) / 255
        text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
        
        # 设置样式以显示颜色和颜色值
        self.color_preview.setStyleSheet(f"""
            background-color: {hex_color}; 
            border: 1px solid #666666; 
            border-radius: 5px;
            color: {text_color};
            font-size: 10px;
            text-align: center;
            padding: 2px;
        """)
        
        # 显示RGB值
        self.color_preview.setText(f"{hex_color}")
        
        # 添加工具提示显示RGB值
        r, g, b = [int(c * 255) for c in self.color_rgb]
        self.color_preview.setToolTip(f"RGB: {r}, {g}, {b}\n点击修改颜色")
        
        # 启动动画
        self.color_preview.setAutoFillBackground(True)
        
        # 创建大小变化的动画效果
        size_animation = QPropertyAnimation(self.color_preview, b"minimumSize")
        size_animation.setDuration(150)
        size_animation.setStartValue(QSize(80, 20))
        size_animation.setEndValue(QSize(84, 22))
        size_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        size_animation2 = QPropertyAnimation(self.color_preview, b"minimumSize")
        size_animation2.setDuration(150)
        size_animation2.setStartValue(QSize(84, 22))
        size_animation2.setEndValue(QSize(80, 20))
        size_animation2.setEasingCurve(QEasingCurve.InQuad)
        
        # 创建动画组
        animation_group = QSequentialAnimationGroup()
        animation_group.addAnimation(size_animation)
        animation_group.addAnimation(size_animation2)
        
        # 启动所有动画
        animation.start()
        animation_group.start()

    def update_tag_history_combo(self):
        self.tag_history_combo.clear()
        if not self.tag_history:
            self.tag_history_combo.addItem("无记录")
        else:
            self.tag_history_combo.addItems(self.tag_history)

    def generate_unique_name(self, base_name, start_index=1):
        index = start_index
        unique_name = f"{base_name}_{index:03d}"
        while cmds.objExists(unique_name):
            index += 1
            unique_name = f"{base_name}_{index:03d}"
        return unique_name

    def get_color_index_from_name(self, name):
        name_lower = name.lower()
        if "_l_" in name_lower:
            return 6  # 蓝色（左侧）
        elif "_r_" in name_lower:
            return 13  # 红色（右侧）
        elif "_m_" in name_lower:
            return 17  # 黄色（中线）
        return None

    @with_undo_support
    def apply_color_index(self, obj, color_index):
        shapes = cmds.listRelatives(obj, shapes=True) or []
        for shape in shapes:
            cmds.setAttr(f"{shape}.overrideEnabled", 1)
            cmds.setAttr(f"{shape}.overrideRGBColors", 0)
            cmds.setAttr(f"{shape}.overrideColor", color_index)
        print(f"物体 '{obj}' 已应用颜色索引 {color_index}。")

    @with_undo_support
    def create_joint(self, prefix, name, side, index, translation, rotation, scale, orient="xyz", sec_axis_orient="yup",
                     preferred_angles=(0, 0, 0), joint_set=None):
        formatted_side = f"_{side}" if side and side.lower() != "none" else ""
        base_name = f"{prefix}{formatted_side}_{name}"
        joint_name = self.generate_unique_name(base_name, start_index=index or 1)

        cmds.select(clear=True)
        joint = cmds.joint(name=joint_name)
        cmds.joint(joint, edit=True, oj=orient, sao=sec_axis_orient, ch=True, zso=True)
        cmds.xform(joint, scale=scale, ws=True, a=True, translation=translation, rotation=rotation)
        cmds.setAttr(f"{joint}.preferredAngle", *preferred_angles)

        if joint_set:
            if not cmds.objExists(joint_set) or cmds.nodeType(joint_set) != "objectSet":
                joint_set = cmds.sets(name=joint_set, empty=True)
            cmds.sets(joint, edit=True, forceElement=joint_set)

        return joint_name

    @with_undo_support
    def create_custom_controller(self, name, side, index, size=1, color_rgb=(1.0, 1.0, 1.0),
                                 translation=(0, 0, 0), rotation=(0, 0, 0),
                                 controller_type="sphere"):
        formatted_side = f"_{side}" if side and side.lower() != "none" else ""
        base_name = f"ctrl{formatted_side}_{name}"
        ctrl_name = self.generate_unique_name(base_name, start_index=index or 1)

        # 添加调试输出
        print(f"DEBUG: controllers模块路径: {os.path.abspath(os.path.dirname(controller_shapes.__file__))}")
        print(f"DEBUG: controller_shapes模块包含的函数: {dir(controller_shapes)}")
        print(f"DEBUG: 尝试创建控制器类型: {controller_type}, 大小: {size}")
        
        # 使用外部模块创建控制器
        try:
            ctrl = controller_shapes.create_custom_controller(ctrl_name, controller_type, size)
            print(f"DEBUG: 控制器创建成功: {ctrl}")
        except Exception as e:
            print(f"ERROR: 创建控制器失败: {str(e)}")
            # 如果创建失败，使用默认的圆形控制器
            ctrl = cmds.circle(name=ctrl_name, radius=size, normal=(0, 1, 0))[0]
            print(f"DEBUG: 已改用默认圆形控制器: {ctrl}")
        
        # 设置变换
        cmds.xform(ctrl, translation=translation, rotation=rotation, worldSpace=True)
        
        # 应用颜色
        controller_shapes.apply_color_to_controller(ctrl, color_rgb)
        
        # 重命名形状节点
        controller_shapes.rename_controller_shape(ctrl)

        # 处理颜色索引（如果有）
        color_index = self.get_color_index_from_name(ctrl_name)
        if color_index is not None:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                cmds.setAttr(f"{shape}.overrideColor", color_index)
            print(f"物体 '{ctrl_name}' 已应用颜色索引 {color_index}。")

        return ctrl_name

    @with_undo_support
    def create_joint_and_controller(self):
        """
        创建关节和控制器组件，支持逗号分隔的侧面输入（例如 "l,r,m"），并根据数量生成对应组件。
        """
        name = self.name_text.text()
        side_input = self.side_text.text()  # 获取侧面输入，例如 "l,r,m"
        count = self.count_spin.value()
        size = self.size_spin.value()
        joint_set = "Skin_Joints_Set"
        
        # 如果启用了根据选择物体数量创建功能，则覆盖count值
        if self.use_selection_count_flag:
            selected_objects = cmds.ls(selection=True)
            if selected_objects:
                count = len(selected_objects)
                print(f"根据选择物体数量创建: 选择了{count}个物体，将创建{count}个关节/控制器")
            else:
                print("根据选择物体数量创建: 未选择任何物体，使用默认数量")
        else:
            selected_objects = cmds.ls(selection=True)
        
        # 检查是否启用物体名称识别
        use_auto_naming = self.auto_name_from_joint_check.isChecked()
        ignore_suffix = self.ignore_suffix_check.isChecked()
        
        # 如果启用了物体名称识别且选择了物体，则从物体名称解析名称和侧面
        selected_objects = cmds.ls(selection=True)
        target_obj = selected_objects[0] if selected_objects else None
        
        if use_auto_naming and target_obj:
            # 从物体名称解析控制器名称（支持任意类型的Maya物体）
            parsed_name = self.parse_object_name(target_obj, ignore_suffix)
            
            # 检查解析的名称是否包含侧面信息
            if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                # 包含侧面信息，分离侧面和名称
                side_part, name_part = parsed_name.split("_", 1)
                name = name_part
                side_input = side_part.lower()
                print(f"从物体名称识别: 物体='{target_obj}', 名称='{name}', 侧面='{side_input}'")
            else:
                # 不包含侧面信息，使用解析的名称作为控制器名称
                name = parsed_name
                print(f"从物体名称识别: 物体='{target_obj}', 名称='{name}'")

        if not name:
            cmds.warning("请输入名称！")
            return

        # 解析侧面输入，支持逗号分隔
        sides = [s.strip() for s in side_input.split(',')] if side_input else ["none"]
        created_groups = []

        self.custom_group_name = self.custom_group_input.text().strip() if self.enable_custom_group else ""

        # 为每个侧面创建指定数量的组件
        for side in sides:
            # 转换为小写并验证侧面输入是否有效
            side = side.lower()
            if side and side not in ["l", "r", "m", "none"]:
                cmds.warning(f"无效的侧面输入 '{side}'，应为 l, r, m 或 none，已跳过")
                continue

            for i in range(count):
                # 如果启用了根据选择物体数量创建功能且启用了识别物体名称，使用对应物体的名称
                if self.use_selection_count_flag and selected_objects and i < len(selected_objects) and use_auto_naming:
                    current_object = selected_objects[i]
                    # 使用parse_object_name方法解析物体名称
                    parsed_name = self.parse_object_name(current_object, self.ignore_suffix_check.isChecked())
                    
                    # 检查解析的名称是否包含侧面信息
                    if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                        # 包含侧面信息，分离侧面和名称
                        object_side, object_name = parsed_name.split("_", 1)
                        base_name = object_name
                        current_side = object_side.lower()
                        formatted_side = f"_{current_side}"
                        print(f"从物体名称识别: 物体='{current_object}', 名称='{base_name}', 侧面='{current_side}'")
                    else:
                        # 不包含侧面信息，使用解析的名称作为基础名称，保持原侧面
                        base_name = parsed_name
                        formatted_side = f"_{side}" if side != "none" else ""
                        print(f"从物体名称识别: 物体='{current_object}', 名称='{base_name}'")
                else:
                    # 使用统一的名称和侧面
                    base_name = f"{name}"
                    formatted_side = f"_{side}" if side != "none" else ""

                # 生成唯一的 zero 组名称并提取后缀
                zero_base_name = f"zero{formatted_side}_{base_name}"
                zero_group_name = self.generate_unique_name(zero_base_name, start_index=i + 1)
                # 提取后缀（例如 "_001"）
                suffix = re.search(r"_(\d+)$", zero_group_name).group(0) if re.search(r"_(\d+)$",
                                                                                      zero_group_name) else f"_{i + 1:03d}"

                ctrl = None
                joint = None
                last_group = None

                # 创建层级结构，所有层级使用相同的后缀
                if self.use_hierarchy_logic:
                    zero_group = cmds.group(name=zero_group_name, empty=True)
                    driven_group_name = f"driven{formatted_side}_{base_name}{suffix}"
                    connect_group_name = f"connect{formatted_side}_{base_name}{suffix}"
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"

                    driven_group = cmds.group(name=driven_group_name, empty=True, parent=zero_group)
                    connect_group = cmds.group(name=connect_group_name, empty=True, parent=driven_group)
                    offset_group = cmds.group(name=offset_group_name, empty=True, parent=connect_group)
                    last_group = offset_group
                else:
                    zero_group = cmds.group(name=zero_group_name, empty=True)
                    offset_group_name = f"grpOffset{formatted_side}_{base_name}{suffix}"
                    offset_group = cmds.group(name=offset_group_name, empty=True, parent=zero_group)
                    last_group = offset_group

                # 创建控制器或空组，使用相同的后缀
                if self.create_controller_flag:
                    ctrl_base = f"ctrl{formatted_side}_{base_name}"
                    ctrl_name = f"{ctrl_base}{suffix}"
                    ctrl = self.create_custom_controller(
                        name=name,
                        side=side,
                        index=None,
                        size=size,
                        color_rgb=self.color_rgb,
                        translation=(0, 0, 0),
                        controller_type=self.controller_type
                    )
                    ctrl = cmds.rename(ctrl, ctrl_name)  # 重命名以确保后缀一致
                    cmds.parent(ctrl, offset_group)
                    
                    # 确保控制器的旋转顺序是可见和可关键帧的
                    cmds.setAttr(f"{ctrl}.rotateOrder", channelBox=True, keyable=True)

                    # 如果启用了子控制器选项，创建子控制器和输出组
                    if self.create_sub_controller_flag:
                        # 使用单独方法创建子控制器
                        sub_ctrl_name, output_name = self.create_sub_controller(
                            parent_ctrl=ctrl,
                            name=name,
                            formatted_side=formatted_side,
                            suffix=suffix
                        )

                        if sub_ctrl_name and output_name:
                            # 层级关系和属性连接已在create_sub_controller方法中完成
                            print(f"已设置控制器层级: '{sub_ctrl_name}' 和 '{output_name}' 作为 '{ctrl}' 的子级")

                elif not self.create_joint_flag and not self.create_controller_flag:
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
                    ctrl = cmds.group(name=ctrl_name, empty=True)
                    cmds.parent(ctrl, offset_group)
                elif self.create_joint_flag and not self.use_hierarchy_logic:
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
                    ctrl = cmds.group(name=ctrl_name, empty=True)
                    cmds.parent(ctrl, offset_group)

                # 创建关节，使用相同的后缀
                if self.create_joint_flag:
                    joint_base = f"jntSkin{formatted_side}_{base_name}"
                    joint_name = f"{joint_base}{suffix}"
                    joint = self.create_joint(
                        prefix="jntSkin",
                        name=name,
                        side=side,
                        index=None,
                        translation=(0, 0, 0),
                        rotation=(0, 0, 0),
                        scale=(1, 1, 1),
                        orient="xyz",
                        sec_axis_orient="yup",
                        preferred_angles=(0, 0, 0),
                        joint_set=joint_set
                    )
                    joint = cmds.rename(joint, joint_name)  # 重命名以确保后缀一致

                    # 如果创建了控制器且创建了子控制器，则将关节父级到output组
                    if ctrl and self.create_controller_flag and self.create_sub_controller_flag:
                        # 找到与控制器关联的output组
                        output_name = ctrl.replace(f"ctrl{formatted_side}_", f"output{formatted_side}_")
                        if cmds.objExists(output_name):
                            # 确保output组是ctrl的子级
                            if not cmds.listRelatives(output_name, parent=True) or cmds.listRelatives(output_name, parent=True)[0] != ctrl:
                                cmds.parent(output_name, ctrl)
                                print(f"已将输出组 '{output_name}' 父级到控制器 '{ctrl}'")
                            
                            # 将关节放到output组下
                            cmds.parent(joint, output_name)
                            print(f"已将关节 '{joint}' 父级到输出组 '{output_name}'")
                        else:
                            cmds.parent(joint, ctrl)
                    elif ctrl:  # 如果 ctrl 存在（控制器或空组），关节父级到 ctrl
                        cmds.parent(joint, ctrl)
                    else:  # 否则父级到 offset_group
                        cmds.parent(joint, offset_group)

                created_groups.append(zero_group)
                
                # 如果启用了根据选择物体数量创建功能，立即匹配到对应的选择物体
                if self.use_selection_count_flag and selected_objects:
                    # 计算当前组件对应的选择物体索引
                    current_index = len(created_groups) - 1
                    if current_index < len(selected_objects):
                        target_transform = selected_objects[current_index]
                        # 保存当前选择
                        current_selection = cmds.ls(selection=True)
                        
                        # 清除选择并选择零组
                        cmds.select(clear=True)
                        cmds.select(zero_group)
                        
                        # 执行匹配变换
                        cmds.matchTransform(zero_group, target_transform,
                                            pos=self.match_position,
                                            rot=self.match_rotation,
                                            scl=self.match_scale)
                        
                        # 恢复之前的选择状态
                        cmds.select(clear=True)
                        if current_selection:
                            cmds.select(current_selection)
                        
                        print(f"已将组件 '{zero_group}' 匹配到物体 '{target_transform}' 的变换")

        # 处理自定义组
        if self.enable_custom_group and self.custom_group_name:
            custom_group = self.custom_group_name
            if not cmds.objExists(custom_group):
                custom_group = cmds.group(empty=True, name=custom_group)
                print(f"已创建自定义组 '{custom_group}'")
            for zero_group in created_groups:
                cmds.parent(zero_group, custom_group)
                print(f"已将 '{zero_group}' 父级到自定义组 '{custom_group}'")

        # 在所有组件创建完成后，将zero组匹配到目标物体
        # 如果启用了根据选择物体数量创建功能，则跳过统一匹配（已在创建过程中完成个别匹配）
        if target_obj and not (self.use_selection_count_flag and selected_objects):
            for group in created_groups:
                # 保存当前选择
                current_selection = cmds.ls(selection=True)
                
                # 清除选择并选择零组
                cmds.select(clear=True)
                cmds.select(group)
                
                # 执行匹配变换
                cmds.matchTransform(group, target_obj,
                                    pos=self.match_position,
                                    rot=self.match_rotation,
                                    scl=self.match_scale)
                
                # 恢复之前的选择状态
                cmds.select(clear=True)
                if current_selection:
                    cmds.select(current_selection)
            
            print(f"已将 {len(created_groups)} 个 zero 组匹配到 '{target_obj}' 的变换。")
        elif self.use_selection_count_flag and selected_objects:
            print(f"已完成根据选择物体数量创建: 每个组件已匹配到对应选择物体的变换。")

        # 处理新的层级关系选项
        if selected_objects and (self.controller_parent_original_check.isChecked() or self.original_parent_controller_check.isChecked()):
            self.apply_hierarchy_relationships(created_groups, selected_objects)
        
        print(
            f"已完成创建：共 {len(sides)} 个侧面 ({','.join(sides)})，每个侧面 {count} 个组件，总计 {len(created_groups)} 个组")

    def apply_hierarchy_relationships(self, created_groups, selected_objects):
        """
        应用新的层级关系选项
        """
        controller_parent_original = self.controller_parent_original_check.isChecked()
        original_parent_controller = self.original_parent_controller_check.isChecked()
        
        # 如果两个选项都选中，给出警告并优先使用第一个选项
        if controller_parent_original and original_parent_controller:
            cmds.warning("两个层级关系选项都被选中，将优先使用'控制器作为原物体父级'选项")
            original_parent_controller = False
        
        for i, zero_group in enumerate(created_groups):
            if i < len(selected_objects):
                original_object = selected_objects[i]
                
                # 查找与zero_group相关的控制器
                controller = self.find_controller_in_hierarchy(zero_group)
                
                if controller and cmds.objExists(original_object):
                    if controller_parent_original:
                        # 控制器作为原物体父级：原物体成为控制器的子级
                        try:
                            cmds.parent(original_object, controller)
                            print(f"层级关系: 已将原物体 '{original_object}' 父级到控制器 '{controller}'")
                        except Exception as e:
                            print(f"警告: 无法将 '{original_object}' 父级到 '{controller}': {e}")
                    
                    elif original_parent_controller:
                        # 原物体作为控制器父级：控制器成为原物体的子级
                        try:
                            cmds.parent(zero_group, original_object)
                            print(f"层级关系: 已将控制器组 '{zero_group}' 父级到原物体 '{original_object}'")
                        except Exception as e:
                            print(f"警告: 无法将 '{zero_group}' 父级到 '{original_object}': {e}")
    
    def find_controller_in_hierarchy(self, zero_group):
        """
        在层级结构中查找控制器
        """
        # 遍历zero_group的所有子级，查找控制器
        all_children = cmds.listRelatives(zero_group, allDescendents=True, type='transform') or []
        
        for child in all_children:
            if child.startswith('ctrl') and not child.startswith('ctrl_sub'):
                return child
        
        return None

    def update_controller_type(self, selected_type):
        type_map = {
            "球形 (Sphere)": "sphere", "立方体 (Cube)": "cube", "圆形 (Circle)": "circle",
            "箭头 (Arrow)": "arrow", "齿轮 (Gear)": "gear", "圆锥 (Cone)": "cone",
            "十字 (Cross)": "cross", "钻石 (Diamond)": "diamond", "矩形 (Rectangle)": "rectangle",
            "正方形 (Square)": "square"
        }
        self.controller_type = type_map.get(selected_type, "sphere")
        print(f"控制器类型已更新为: {self.controller_type}")

    def toggle_create_joint(self, state):
        self.create_joint_flag = state == Qt.Checked
        print(f"创建关节: {self.create_joint_flag}")

    def toggle_custom_group(self, state):
        self.enable_custom_group = state == Qt.Checked
        self.custom_group_input.setEnabled(self.enable_custom_group)
        print(f"启用自定义组: {self.enable_custom_group}")

    def toggle_create_controller(self, state):
        self.create_controller_flag = state == Qt.Checked
        print(f"创建控制器: {self.create_controller_flag}")
        # 如果控制器被禁用，子控制器也应该被禁用
        if not self.create_controller_flag:
            self.create_sub_controller_check.setChecked(False)
            self.create_sub_controller_check.setEnabled(False)
        else:
            self.create_sub_controller_check.setEnabled(True)

    def toggle_create_sub_controller(self, state):
        self.create_sub_controller_flag = state == Qt.Checked
        print(f"创建子控制器: {self.create_sub_controller_flag}")
    
    def toggle_controller_parent_original(self, state):
        """切换控制器作为原物体父级选项"""
        if state == 2:  # 选中状态
            self.original_parent_controller_check.setChecked(False)
    
    def toggle_original_parent_controller(self, state):
        """切换原物体作为控制器父级选项"""
        if state == 2:  # 选中状态
            self.controller_parent_original_check.setChecked(False)

    # def toggle_use_selection_count(self, state):
    #     self.use_selection_count_flag = state == Qt.Checked
    #     print(f"根据选择物体数量创建: {self.use_selection_count_flag}")

    def show_color_dialog(self):
        # 创建颜色对话框
        color_dialog = QColorDialog(QColor.fromRgbF(*self.color_rgb), self)
        
        # 设置对话框标题
        color_dialog.setWindowTitle("选择控制器颜色")
        
        # 启用自定义颜色并显示颜色代码编辑框
        color_dialog.setOptions(QColorDialog.ShowAlphaChannel | QColorDialog.DontUseNativeDialog)
        
        # 添加淡入淡出效果
        opacity_effect = QGraphicsOpacityEffect(color_dialog)
        color_dialog.setGraphicsEffect(opacity_effect)

        # 创建淡入动画
        fade_in = QPropertyAnimation(opacity_effect, b"opacity")
        fade_in.setDuration(250)  # 250毫秒
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InQuad)

        # 显示对话框前开始淡入动画
        fade_in.start()
        
        # 启用RGB和HSV颜色选择
        color_dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        
        # 添加常用或预设颜色列表
        common_colors = [
            QColor(255, 0, 0),      # 红色
            QColor(0, 0, 255),      # 蓝色
            QColor(255, 255, 0),    # 黄色
            QColor(0, 255, 0),      # 绿色
            QColor(255, 128, 0),    # 橙色
            QColor(128, 0, 128),    # 紫色
            QColor(0, 255, 255),    # 青色
            QColor(255, 0, 255),    # 品红色
            QColor(128, 128, 128),  # 灰色
            QColor(255, 255, 255),  # 白色
        ]
        color_dialog.setCustomColor(0, common_colors[0].rgb())
        color_dialog.setCustomColor(1, common_colors[1].rgb())
        color_dialog.setCustomColor(2, common_colors[2].rgb())
        color_dialog.setCustomColor(3, common_colors[3].rgb())
        color_dialog.setCustomColor(4, common_colors[4].rgb())
        color_dialog.setCustomColor(5, common_colors[5].rgb())
        color_dialog.setCustomColor(6, common_colors[6].rgb())
        color_dialog.setCustomColor(7, common_colors[7].rgb())
        color_dialog.setCustomColor(8, common_colors[8].rgb())
        color_dialog.setCustomColor(9, common_colors[9].rgb())

        # 显示颜色对话框并等待用户选择
        if color_dialog.exec_():
            color = color_dialog.currentColor()
            if color.isValid():
                self.color_rgb = [color.redF(), color.greenF(), color.blueF()]
                self.update_color_preview()
                print(f"已选择颜色: RGB ({int(color.red())}, {int(color.green())}, {int(color.blue())})")
                
                # 返回到颜色预览动画
                return True
        return False

    def set_color(self, rgb):
        """设置当前颜色并更新预览
        
        参数:
            rgb (list): 包含三个浮点数的列表，范围0-1，代表RGB颜色
        """
        self.color_rgb = rgb
        self.update_color_preview()
        r, g, b = [int(c * 255) for c in rgb]
        print(f"已选择自定义颜色: RGB ({r}, {g}, {b})")
    
    def set_preset_color(self, rgb):
        """设置预设颜色并更新预览
        
        参数:
            rgb (tuple): 包含三个浮点数的元组，范围0-1，代表RGB颜色
        """
        self.color_rgb = list(rgb)
        self.update_color_preview()
        r, g, b = [int(c * 255) for c in rgb]
        print(f"已选择预设颜色: RGB ({r}, {g}, {b})")

    @with_undo_support
    def set_color_index(self, index):
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            self.apply_color_index(ctrl, index)

        index_to_rgb = {13: [1.0, 0.0, 0.0], 17: [1.0, 1.0, 0.0], 6: [0.0, 0.0, 1.0]}
        self.color_rgb = index_to_rgb.get(index, [1.0, 1.0, 1.0])
        self.update_color_preview()

    @with_undo_support
    def apply_color_to_controller(self):
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideRGBColors", 1)
                cmds.setAttr(f"{shape}.overrideColorRGB", *self.color_rgb)
            print(f"控制器 '{ctrl}' 已应用颜色 RGB {self.color_rgb}。")

    @with_undo_support
    def reset_color(self):
        """重置颜色功能：将绘制覆盖从RGB改为索引，然后关闭启用覆盖"""
        selected_controllers = cmds.ls(selection=True)
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True) or []
            for shape in shapes:
                # 首先将RGB颜色模式改为索引颜色模式
                cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                # 然后关闭启用覆盖
                cmds.setAttr(f"{shape}.overrideEnabled", 0)
            print(f"控制器 '{ctrl}' 已重置颜色覆盖。")
        
        print(f"已重置 {len(selected_controllers)} 个控制器的颜色覆盖。")

    @with_undo_support
    def apply_random_colors(self):
        """调用随机颜色功能"""
        try:
            # 使用load_module函数加载并执行随机颜色模块
            load_module("随机颜色", os.path.join(TOOL_DIR, "随机颜色.py"), "assign_random_colors")
        except Exception as e:
            cmds.warning(f"执行随机颜色功能时出错: {str(e)}")
            print(f"错误详情: {str(e)}")
    
    def open_gradient_color_tool(self):
        """打开渐变颜色工具"""
        try:
            # 使用load_module函数加载并执行渐变颜色模块
            load_module("渐变颜色", os.path.join(TOOL_DIR, "渐变颜色.py"), "show_gradient_color_tool")
        except Exception as e:
            cmds.warning(f"打开渐变颜色工具时出错: {str(e)}")
            print(f"错误详情: {str(e)}")

    def toggle_match_position(self, state):
        self.match_position = state == Qt.Checked

    def toggle_match_rotation(self, state):
        self.match_rotation = state == Qt.Checked

    def toggle_match_scale(self, state):
        self.match_scale = state == Qt.Checked
        print(f"匹配缩放: {self.match_scale}")

    def update_group_prefix(self, selected_prefix):
        self.group_prefix = selected_prefix

    def update_custom_prefix(self, text):
        if text:
            self.group_prefix = text
            print(f"自定义前缀已更新为: {self.group_prefix}")
        else:
            self.group_prefix = "zero"
            print("未输入前缀，使用默认前缀 'zero'。")

    def toggle_remove_prefix(self, state):
        self.remove_prefix = state == Qt.Checked

    def toggle_use_existing_suffix(self, state):
        self.use_existing_suffix = state == Qt.Checked

    def toggle_freeze_scale(self, state):
        self.freeze_scale = state == Qt.Checked

    def toggle_hierarchy_logic(self, state):
        self.use_hierarchy_logic = state == Qt.Checked
        print(f"使用层级组逻辑: {self.use_hierarchy_logic}")

    def clean_object_name(self, name):
        if self.remove_prefix:
            name_without_prefix = re.sub(r"^[a-zA-Z0-9]+_", "", name)
        else:
            name_without_prefix = name

        match = re.search(r"(_\d+)$", name_without_prefix)
        if match:
            name_without_prefix = name_without_prefix[:match.start()]

        return name_without_prefix
    
    def extract_suffix_from_name(self, name):
        """从物体名称中提取后缀，如果没有后缀则返回默认值_001"""
        # 匹配末尾的数字后缀，如_001, _123等
        match = re.search(r"(_\d+)$", name)
        if match:
            return match.group(1)  # 返回包含下划线的后缀，如"_001"
        else:
            return "_001"  # 默认后缀

    def get_existing_suffix(self, name):
        match = re.search(r"(_\d+)$", name)
        return match.group(1) if match else None

    def get_next_available_suffix(self, base_name, prefix):
        existing_groups = cmds.ls(f"{prefix}_{base_name}_*", type="transform")
        max_suffix = 0
        for group in existing_groups:
            match = re.search(r"_(\d+)$", group)
            if match:
                suffix_num = int(match.group(1))
                if suffix_num > max_suffix:
                    max_suffix = suffix_num
        return f"_{max_suffix + 1:03d}"

    @with_undo_support
    def freeze_object_scale(self, obj_name):
        if self.freeze_scale:
            scale = cmds.getAttr(f"{obj_name}.scale")[0]
            if scale != (1.0, 1.0, 1.0):
                cmds.makeIdentity(obj_name, apply=True, scale=True)
                print(f"物体 '{obj_name}' 的缩放已冻结。")

    @with_undo_support
    def create_group_for_selected(self):
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        for obj_name in selected_objects:
            try:
                if self.freeze_scale:
                    self.freeze_object_scale(obj_name)

                clean_name = self.clean_object_name(obj_name)
                suffix = self.get_existing_suffix(
                    obj_name) if self.use_existing_suffix else self.get_next_available_suffix(clean_name,
                                                                                              self.group_prefix)
                if not suffix and self.use_existing_suffix:
                    suffix = self.get_next_available_suffix(clean_name, self.group_prefix)

                base_group_name = f"{self.group_prefix}_{clean_name}" if self.group_prefix else clean_name
                group_name = f"{base_group_name}{suffix}"

                parent_obj = cmds.listRelatives(obj_name, parent=True)
                group = cmds.group(em=True, name=group_name)
                cmds.matchTransform(group, obj_name)
                cmds.parent(obj_name, group)

                color_index = self.get_color_index_from_name(group_name)
                if color_index is not None and cmds.objectType(obj_name, isType="nurbsCurve"):
                    self.apply_color_index(obj_name, color_index)

                if parent_obj:
                    cmds.parent(group, parent_obj[0])

                print(f"组 '{group_name}' 已创建，物体 '{obj_name}' 已添加到组中。")

            except Exception as e:
                print(f"为 '{obj_name}' 创建组时出错: {e}")

    @with_undo_support
    def create_object_under(self):
        """为选中物体在其层级下创建locator或空组，匹配变换并保持层级结构"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        create_locator = self.create_locator_check.isChecked()
        object_type = "locator" if create_locator else "空组"
        
        for obj_name in selected_objects:
            try:
                # 获取物体的子物体
                children = cmds.listRelatives(obj_name, children=True, type='transform') or []
                
                # 创建对象名称
                clean_name = self.clean_object_name(obj_name)
                # 提取原物体的后缀，如果有后缀就使用它的后缀，没有就默认_001
                suffix = self.extract_suffix_from_name(obj_name)
                
                if create_locator:
                    obj_name_new = f"loc_{clean_name}{suffix}"
                else:
                    obj_name_new = f"grp_{clean_name}{suffix}"
                
                # 确保名称唯一
                if cmds.objExists(obj_name_new):
                    counter = 1
                    base_name = obj_name_new.rsplit('_', 1)[0]  # 移除最后的数字部分
                    while cmds.objExists(f"{base_name}_{counter:03d}"):
                        counter += 1
                    obj_name_new = f"{base_name}_{counter:03d}"
                
                # 创建对象
                if create_locator:
                    created_obj = cmds.spaceLocator(name=obj_name_new)[0]
                else:
                    created_obj = cmds.group(name=obj_name_new, empty=True)
                
                # 匹配变换到物体
                cmds.matchTransform(created_obj, obj_name, position=True, rotation=True, scale=True)
                
                # 将对象放到物体层级下
                cmds.parent(created_obj, obj_name)
                
                print(f"已为物体 '{obj_name}' 在其层级下创建{object_type} '{created_obj}'")
                
            except Exception as e:
                print(f"为 '{obj_name}' 创建{object_type}时出错: {e}")

    @with_undo_support
    def create_object_above(self):
        """为选中物体在其层级上创建locator或空组，匹配变换并保持层级结构"""
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        create_locator = self.create_locator_check.isChecked()
        object_type = "locator" if create_locator else "空组"
        
        for obj_name in selected_objects:
            try:
                # 获取物体的父物体
                parent_obj = cmds.listRelatives(obj_name, parent=True)
                
                # 创建对象名称
                clean_name = self.clean_object_name(obj_name)
                # 提取原物体的后缀，如果有后缀就使用它的后缀，没有就默认_001
                suffix = self.extract_suffix_from_name(obj_name)
                
                if create_locator:
                    obj_name_new = f"loc_{clean_name}{suffix}"
                else:
                    obj_name_new = f"grp_{clean_name}{suffix}"
                
                # 确保名称唯一
                if cmds.objExists(obj_name_new):
                    counter = 1
                    base_name = obj_name_new.rsplit('_', 1)[0]  # 移除最后的数字部分
                    while cmds.objExists(f"{base_name}_{counter:03d}"):
                        counter += 1
                    obj_name_new = f"{base_name}_{counter:03d}"
                
                # 创建对象
                if create_locator:
                    created_obj = cmds.spaceLocator(name=obj_name_new)[0]
                else:
                    created_obj = cmds.group(name=obj_name_new, empty=True)
                
                # 匹配变换到物体
                cmds.matchTransform(created_obj, obj_name, position=True, rotation=True, scale=True)
                
                # 将物体父级到创建的对象
                cmds.parent(obj_name, created_obj)
                
                # 如果原物体有父物体，将创建的对象放到原父物体下
                if parent_obj:
                    cmds.parent(created_obj, parent_obj[0])
                
                print(f"已为物体 '{obj_name}' 在其层级上创建{object_type} '{created_obj}'")
                
            except Exception as e:
                print(f"为 '{obj_name}' 创建{object_type}时出错: {e}")

    @with_undo_support
    def add_controller_hierarchy(self):
        controllers = cmds.ls(selection=True)
        if not controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        for ctrl in controllers:
            zero = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'zero_'))
            driven = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'driven_'), parent=zero)
            connect = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'connect_'), parent=driven)
            offset = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'offset_'), parent=connect)

            cmds.matchTransform(zero, ctrl, position=True, rotation=True)
            cmds.parent(ctrl, offset)
            print(f"控制器 '{ctrl}' 的层级已创建。")

    @with_undo_support
    def add_tag_attribute(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        selected_objects = cmds.ls(sl=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected_objects:
            if not cmds.objExists(f"{obj}.{tag_name}"):
                cmds.addAttr(obj, ln=tag_name, at="bool", dv=1)
                cmds.setAttr(f"{obj}.{tag_name}", keyable=False, channelBox=False)
                print(f"已为物体 '{obj}' 添加 Tag '{tag_name}'")
                if tag_name not in self.tag_history:
                    self.tag_history.append(tag_name)
                    self.update_tag_history_combo()
            else:
                print(f"物体 '{obj}' 已存在 Tag '{tag_name}'，跳过添加")

    def select_objects_with_tag(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        all_objects = cmds.ls(transforms=True)
        tagged_objects = [obj for obj in all_objects if cmds.attributeQuery(tag_name, node=obj, exists=True)]

        if not tagged_objects:
            cmds.warning(f"场景中没有物体具有 Tag '{tag_name}'！")
            return

        cmds.select(tagged_objects, replace=True)
        print(f"已选择 {len(tagged_objects)} 个具有 Tag '{tag_name}' 的物体：{tagged_objects}")

    @with_undo_support
    def remove_tag_attribute(self):
        tag_name = self.tag_name_input.text().strip()
        if not tag_name:
            cmds.warning("请输入 Tag 名称！")
            return

        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        objects_with_tag = [obj for obj in selected_objects
                            if cmds.attributeQuery(tag_name, node=obj, exists=True)]

        if not objects_with_tag:
            cmds.warning(f"选中的物体中没有包含 Tag '{tag_name}'！")
            return

        for obj in objects_with_tag:
            cmds.deleteAttr(f"{obj}.{tag_name}")
            print(f"已从物体 '{obj}' 删除 Tag '{tag_name}'")

        print(f"已从 {len(objects_with_tag)} 个物体删除 Tag '{tag_name}'。")

    def identify_object_tags(self):
        selected_objects = cmds.ls(selection=True)
        if not selected_objects:
            cmds.warning("请至少选择一个物体！")
            return

        identified_tags = set()
        for obj in selected_objects:
            attrs = cmds.listAttr(obj, userDefined=True) or []
            for attr in attrs:
                if cmds.getAttr(f"{obj}.{attr}", type=True) == "bool":
                    identified_tags.add(attr)

        if not identified_tags:
            cmds.warning("选中的物体没有自定义布尔属性！")
            return

        new_tags = [tag for tag in identified_tags if tag not in self.tag_history]
        if new_tags:
            self.tag_history.extend(new_tags)
            self.update_tag_history_combo()
            print(f"已识别并添加 {len(new_tags)} 个新 Tag 到历史记录：{new_tags}")
        else:
            print(f"识别到 {len(identified_tags)} 个 Tag，但均已存在于历史记录中：{identified_tags}")

    def on_tag_history_selected(self, tag):
        if tag != "无记录":
            self.tag_name_input.setText(tag)
            print(f"已从历史记录选择 Tag '{tag}'")

    @with_undo_support
    def clear_tag_history(self):
        self.tag_history.clear()
        self.update_tag_history_combo()
        print("已清空所有历史 Tag 记录。")

    @with_undo_support
    def reset_position(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.translateX", 0)
            cmds.setAttr(f"{obj}.translateY", 0)
            cmds.setAttr(f"{obj}.translateZ", 0)
            print(f"物体 '{obj}' 的位移已归零。")

    @with_undo_support
    def reset_rotation(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.rotateX", 0)
            cmds.setAttr(f"{obj}.rotateY", 0)
            cmds.setAttr(f"{obj}.rotateZ", 0)
            print(f"物体 '{obj}' 的旋转已归零。")

    @with_undo_support
    def reset_scale(self):
        selected = cmds.ls(sl=True) or []
        if not selected:
            cmds.warning("请至少选择一个物体！")
            return

        for obj in selected:
            cmds.setAttr(f"{obj}.scaleX", 1)
            cmds.setAttr(f"{obj}.scaleY", 1)
            cmds.setAttr(f"{obj}.scaleZ", 1)
            print(f"物体 '{obj}' 的缩放已归一。")















    def open_create_curve_from_joints(self):
        create_curve_file = os.path.join(TOOL_DIR, "create_curve_from_joints.py")
        if not os.path.exists(create_curve_file):
            cmds.warning(f"未找到 create_curve_from_joints.py 文件: {create_curve_file}")
            return

        try:
            import importlib
            module_name = "create_curve_from_joints"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            curve_module = sys.modules[module_name]

            if hasattr(curve_module, "create_curve_ui"):
                curve_module.create_curve_ui()
                print("已运行 create_curve_from_joints.py 中的 create_curve_ui 函数，显示骨骼曲线工具窗口")
            else:
                cmds.warning("create_curve_from_joints.py 中未找到 create_curve_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 create_curve_from_joints.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")
            
    def open_curve_toolbox(self):
        """打开曲线工具箱，调用toolsForCur.mel中的CurTools()函数"""
        curve_toolbox_file = os.path.join(TOOL_DIR, "toolsForCur.mel")
        if not os.path.exists(curve_toolbox_file):
            cmds.warning(f"未找到 toolsForCur.mel 文件: {curve_toolbox_file}")
            return
            
        try:
            # 使用maya.mel模块执行MEL脚本中的CurTools函数
            mel.eval("source \"" + curve_toolbox_file.replace("\\", "/") + "\";")
            mel.eval("CurTools()")
            print("已运行 toolsForCur.mel 中的 CurTools 函数，显示曲线工具箱")
        except Exception as e:
            cmds.warning(f"执行 toolsForCur.mel 中的 CurTools 函数失败: {str(e)}")
            print(f"错误详情: {str(e)}")







    def open_toggle_local_rotation(self):
        toggle_file = os.path.join(TOOL_DIR, "toggle_local_rotation_display.py")
        if not os.path.exists(toggle_file):
            cmds.warning(f"未找到 toggle_local_rotation_display.py 文件: {toggle_file}")
            return

        try:
            import importlib
            module_name = "toggle_local_rotation_display"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            toggle_module = sys.modules[module_name]

            if hasattr(toggle_module, "create_ui"):
                toggle_module.create_ui()
                print("已运行 toggle_local_rotation_display.py 中的 create_ui 函数，显示局部旋转显示控制窗口")
            else:
                cmds.warning("toggle_local_rotation_display.py 中未找到 create_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 toggle_local_rotation_display.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def open_create_controller_hierarchy(self):
        controller_file = os.path.join(TOOL_DIR, "create_controller.py")
        if not os.path.exists(controller_file):
            cmds.warning(f"未找到 create_controller.py 文件: {controller_file}")
            return

        try:
            import importlib
            module_name = "create_controller"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            controller_module = sys.modules[module_name]

            if hasattr(controller_module, "create_hierarchy"):
                controller_module.create_hierarchy()
                print("已运行 create_controller.py 中的 create_hierarchy 函数，创建层级结构")
            else:
                cmds.warning("create_controller.py 中未找到 create_hierarchy 函数")
        except Exception as e:
            cmds.warning(f"加载 create_controller.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_ctrl_connect(self):
        ctrl_connect_file = os.path.join(TOOL_DIR, "ctrl_connect.py")
        if not os.path.exists(ctrl_connect_file):
            cmds.warning(f"未找到 ctrl_connect.py 文件: {ctrl_connect_file}")
            return

        try:
            module_name = "ctrl_connect"
            module = load_module(module_name, ctrl_connect_file)
            if module:
                print("已成功加载 ctrl_connect.py，为选中的控制器创建层级结构和次级控制器")
        except Exception as e:
            cmds.warning(f"加载 ctrl_connect.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_object_creation_controller(self):
        obj_ctrl_file = os.path.join(TOOL_DIR, "Object_creation_controller.py")
        if not os.path.exists(obj_ctrl_file):
            cmds.warning(f"未找到 Object_creation_controller.py 文件: {obj_ctrl_file}")
            return

        try:
            import importlib
            module_name = "Object_creation_controller"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            obj_ctrl_module = sys.modules[module_name]

            if hasattr(obj_ctrl_module, "create_controller_for_selected_objects"):
                obj_ctrl_module.create_controller_for_selected_objects("Circle")
                print("已运行 Object_creation_controller.py，为选定的物体创建控制器")
            else:
                cmds.warning("Object_creation_controller.py 中未找到 create_controller_for_selected_objects 函数")
        except Exception as e:
            cmds.warning(f"加载 Object_creation_controller.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_object_center_curve(self):
        script_file = os.path.join(TOOL_DIR, "Object_center_generation_curve.py")
        if not os.path.exists(script_file):
            cmds.warning(f"未找到 Object_center_generation_curve.py 文件: {script_file}")
            return

        try:
            import importlib
            module_name = "Object_center_generation_curve"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 Object_center_generation_curve.py，生成物体中心曲线")
        except Exception as e:
            cmds.warning(f"加载 Object_center_generation_curve.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_blend_shape_conversion(self):
        script_file = os.path.join(TOOL_DIR, "blendShape_conversion.py")
        if not os.path.exists(script_file):
            cmds.warning(f"未找到 blendShape_conversion.py 文件: {script_file}")
            return

        try:
            import importlib
            module_name = "blendShape_conversion"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            blend_module = sys.modules[module_name]
            if hasattr(blend_module, "invertShapeUI"):
                blend_module.invertShapeUI()
                print("已成功打开 blendShape_conversion.py 的形状倒转工具窗口")
            else:
                cmds.warning("blendShape_conversion.py 中未找到 invertShapeUI 函数")
        except Exception as e:
            cmds.warning(f"加载 blendShape_conversion.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_joint_tag_v1(self):
        joint_tag_file = os.path.join(TOOL_DIR, "joint_TagV1.py")
        if not os.path.exists(joint_tag_file):
            cmds.warning(f"未找到 joint_TagV1.py 文件: {joint_tag_file}")
            return

        try:
            import importlib
            module_name = "joint_TagV1"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 joint_TagV1.py，为场景中的关节添加标签")
        except Exception as e:
            cmds.warning(f"加载 joint_TagV1.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_joint_tag_v2(self):
        joint_tag_file = os.path.join(TOOL_DIR, "joint_TagV2.py")
        if not os.path.exists(joint_tag_file):
            cmds.warning(f"未找到 joint_TagV2.py 文件: {joint_tag_file}")
            return

        try:
            import importlib
            module_name = "joint_TagV2"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print("已成功运行 joint_TagV2.py，为场景中的所有关节添加通用标签")
        except Exception as e:
            cmds.warning(f"加载 joint_TagV2.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_mirror_curve_shape(self):
        mirror_file = os.path.join(TOOL_DIR, "MirrorCurveShape.py")
        if not os.path.exists(mirror_file):
            cmds.warning(f"未找到 MirrorCurveShape.py 文件: {mirror_file}")
            return

        try:
            import importlib
            module_name = "MirrorCurveShape"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            mirror_module = sys.modules[module_name]
            if hasattr(mirror_module, "MirrorCurveShape"):
                mirror_module.MirrorCurveShape()
                print("已运行 MirrorCurveShape.py 中的 MirrorCurveShape 函数，镜像曲线形状")
            else:
                cmds.warning("MirrorCurveShape.py 中未找到 MirrorCurveShape 函数")
        except Exception as e:
            cmds.warning(f"加载 MirrorCurveShape.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def open_trans_curve_shape(self):
        trans_file = os.path.join(TOOL_DIR, "trans_curve_shape.py")
        if not os.path.exists(trans_file):
            cmds.warning(f"未找到 trans_curve_shape.py 文件: {trans_file}")
            return

        try:
            import importlib
            module_name = "trans_curve_shape"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)

            trans_module = sys.modules[module_name]
            if hasattr(trans_module, "trans_curve_shape"):
                trans_module.trans_curve_shape()
                print("已运行 trans_curve_shape.py 中的 trans_curve_shape 函数，替换曲线形状")
            else:
                cmds.warning("trans_curve_shape.py 中未找到 trans_curve_shape 函数")
        except Exception as e:
            cmds.warning(f"加载 trans_curve_shape.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def load_module_from_file(self, module_name, file_path, description):
        if not os.path.exists(file_path):
            cmds.warning(f"未找到文件: {file_path}")
            return
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                cmds.warning(f"无法创建 {module_name} 的模块规格")
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            if hasattr(module, "show_ui"):
                module.show_ui()
                print(f"已运行 {file_path} 中的 show_ui 函数，{description}")
            else:
                cmds.warning(f"{file_path} 中未找到 show_ui 函数")
        except Exception as e:
            cmds.warning(f"加载 {file_path} 失败: {str(e)}")
            print(f"错误详情: {str(e)}")



    def reparent_shape_nodes(self):
        reparent_shape_file = os.path.join(TOOL_DIR, "reparentShapeNodes.py")
        if not os.path.exists(reparent_shape_file):
            cmds.warning(f"未找到 reparentShapeNodes.py 文件: {reparent_shape_file}")
            return

        try:
            import importlib.util
            module_name = "reparentShapeNodes"

            # 如果模块已加载，重新加载以确保最新状态
            if module_name in sys.modules:
                reparent_module = sys.modules[module_name]
                importlib.reload(reparent_module)
            else:
                # 动态加载模块
                spec = importlib.util.spec_from_file_location(module_name, reparent_shape_file)
                reparent_module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = reparent_module
                spec.loader.exec_module(reparent_module)

            # 调用函数
            if hasattr(reparent_module, "reparent_shape_nodes"):
                reparent_module.reparent_shape_nodes()
                print("已运行 reparentShapeNodes.py 中的 reparent_shape_nodes 函数，添加形状节点")
            else:
                cmds.warning("reparentShapeNodes.py 中未找到 reparent_shape_nodes 函数")
        except Exception as e:
            cmds.warning(f"运行 reparentShapeNodes.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def auto_rename_curve_shapes(self):
        """调用曲线Shape重命名工具的自动全部命名功能"""
        curve_rename_file = os.path.join(TOOL_DIR, "曲线 Shape 重命名工具.py")
        if not os.path.exists(curve_rename_file):
            cmds.warning(f"未找到 曲线 Shape 重命名工具.py 文件: {curve_rename_file}")
            return

        try:
            # 直接执行Python文件
            with open(curve_rename_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 创建一个新的命名空间来执行代码
            namespace = {}
            exec(code, namespace)
            
            # 调用自动全部命名函数
            if "auto_rename_all" in namespace:
                namespace["auto_rename_all"]()
                print("已运行曲线Shape重命名工具的自动全部命名功能")
            else:
                cmds.warning("曲线 Shape 重命名工具.py 中未找到 auto_rename_all 函数")
        except Exception as e:
            cmds.warning(f"运行曲线Shape重命名工具失败: {str(e)}")
            print(f"错误详情: {str(e)}")

    def toggle_always_draw_on_top(self):
        """切换选中曲线的alwaysDrawOnTop属性"""
        selected = cmds.ls(selection=True, long=True)
        if not selected:
            cmds.warning('请先选择需要切换显示属性的曲线。')
            return

        modified_count = 0
        for obj in selected:
            # 获取对象的形状节点
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
            if not shapes:
                continue

            for shape in shapes:
                # 检查是否为曲线形状
                if cmds.nodeType(shape) == 'nurbsCurve':
                    try:
                        # 获取当前的alwaysDrawOnTop状态
                        current_state = cmds.getAttr(f"{shape}.alwaysDrawOnTop")
                        # 切换状态
                        new_state = not current_state
                        cmds.setAttr(f"{shape}.alwaysDrawOnTop", new_state)
                        
                        state_text = "开启" if new_state else "关闭"
                        print(f"曲线 {obj} 的显示在前面属性已{state_text}")
                        modified_count += 1
                    except Exception as e:
                        cmds.warning(f"无法修改 {obj} 的显示属性: {str(e)}")

        if modified_count > 0:
            cmds.inViewMessage(amg=f"<hl>完成！共修改 {modified_count} 个曲线的显示属性。</hl>", pos='midCenterTop', fade=True)
        else:
            cmds.warning('选择的物体中没有有效的曲线。')





    def show(self):
        if not self.isVisible():
            super().show()
        else:
            self.raise_()
            self.activateWindow()
        print("综合工具窗口已显示")

    def closeEvent(self, event):
        # 停止所有动画
        if hasattr(self.gif_label, 'movie') and self.gif_label.movie:
            self.gif_label.movie.stop()
        
        # 保存尺寸和其他窗口状态
        cmds.optionVar(floatValue=("CombinedToolWindowWidth", self.width()))
        cmds.optionVar(floatValue=("CombinedToolWindowHeight", self.height()))
        
        # 保存图标设置
        if hasattr(self, 'gif_label'):
            self.gif_label.save_settings()
        
        # 清理窗口资源
        self.deleteLater()
        
        # 移除实例引用，确保下次可以创建新的窗口
        # 注意：实际上不需要设置为None，因为get_instance会检查窗口存在性
        # 但为了清晰起见，我们仍然做这个操作
        CombinedTool._instance = None
        
        # 关闭所有子窗口
        if self.snap_to_pivot_tool:
            self.snap_to_pivot_tool.close()
        
        # 继续事件传递
        super().closeEvent(event)

    @with_undo_support
    def create_sub_controller(self, parent_ctrl, name, formatted_side, suffix):
        """
        创建子控制器并设置与父控制器的连接

        Args:
            parent_ctrl: 父控制器名称
            name: 基础名称
            formatted_side: 格式化的侧面字符串（如 "_l"）
            suffix: 后缀（如 "_001"）

        Returns:
            tuple: (子控制器名称, 输出组名称)
        """
        try:
            # 创建子控制器 - 直接使用父控制器名称+Sub
            sub_ctrl_name = f"{parent_ctrl}Sub"
            sub_ctrl = cmds.duplicate(parent_ctrl, name=sub_ctrl_name)[0]
            # 先临时将子控制器放在父控制器下
            cmds.parent(sub_ctrl, parent_ctrl)
            cmds.setAttr(f"{sub_ctrl}.scale", 0.9, 0.9, 0.9)
            cmds.makeIdentity(sub_ctrl, apply=True, scale=True)

            # 创建输出组
            output_name = parent_ctrl.replace(f"ctrl{formatted_side}_", f"output{formatted_side}_")
            
            # 检查输出组是否已存在，如果存在则删除
            if cmds.objExists(output_name):
                print(f"警告: 输出组 '{output_name}' 已存在，将被删除并重新创建")
                cmds.delete(output_name)
                
            # 创建输出组并立即父级到控制器下
            output = cmds.createNode('transform', name=output_name, parent=parent_ctrl)

            # 连接属性
            cmds.connectAttr(f"{sub_ctrl}.translate", f"{output_name}.translate")
            cmds.connectAttr(f"{sub_ctrl}.rotate", f"{output_name}.rotate")
            cmds.connectAttr(f"{sub_ctrl}.rotateOrder", f"{output_name}.rotateOrder")
            cmds.connectAttr(f"{sub_ctrl}.scale", f"{output_name}.scale")  # 添加缩放属性连接

            # 显示旋转顺序
            cmds.setAttr(f"{parent_ctrl}.rotateOrder", channelBox=True, keyable=True)
            cmds.setAttr(f"{sub_ctrl}.rotateOrder", channelBox=True, keyable=True)

            # 添加子控制器可见性属性 - 在锁定visibility之前添加
            if not cmds.attributeQuery("subCtrlVis", node=parent_ctrl, exists=True):
                cmds.addAttr(parent_ctrl, longName='subCtrlVis', attributeType='bool', defaultValue=False)
                cmds.setAttr(f"{parent_ctrl}.subCtrlVis", channelBox=True, keyable=False)
                # 设置为可以在通道框中显示但不可k帧
                print(f"已在 '{parent_ctrl}' 上添加 subCtrlVis 属性，并设置为通道框可见但不可关键帧")
            else:
                # 确保属性是不可关键帧的但在通道框可见
                cmds.setAttr(f"{parent_ctrl}.subCtrlVis", channelBox=True, keyable=False)
                
            # 连接子控制器可见性
            cmds.connectAttr(f"{parent_ctrl}.subCtrlVis", f"{sub_ctrl}.visibility")

            # 调整子控制器颜色 - 使用稍浅的颜色
            # 首先获取父控制器的形状节点颜色设置
            parent_shapes = cmds.listRelatives(parent_ctrl, shapes=True) or []
            parent_rgb_colors = None
            parent_index = None
            use_rgb = False

            # 获取父控制器的颜色设置
            if parent_shapes:
                parent_shape = parent_shapes[0]
                if cmds.getAttr(f"{parent_shape}.overrideEnabled"):
                    if cmds.getAttr(f"{parent_shape}.overrideRGBColors"):
                        # 父控制器使用RGB颜色
                        use_rgb = True
                        parent_rgb_colors = cmds.getAttr(f"{parent_shape}.overrideColorRGB")[0]
                    else:
                        # 父控制器使用索引颜色
                        parent_index = cmds.getAttr(f"{parent_shape}.overrideColor")

            # 应用颜色到子控制器
            shapes = cmds.listRelatives(sub_ctrl, shapes=True) or []
            for shape in shapes:
                cmds.setAttr(f"{shape}.overrideEnabled", 1)

                if use_rgb and parent_rgb_colors:
                    # 如果父控制器使用RGB颜色，则子控制器也使用RGB但颜色更淡
                    cmds.setAttr(f"{shape}.overrideRGBColors", 1)
                    # 将RGB颜色调亮一些，但保持原始色调
                    lighter_rgb = [min(c * 1.3, 1.0) for c in parent_rgb_colors]
                    cmds.setAttr(f"{shape}.overrideColorRGB", *lighter_rgb)
                    print(f"子控制器 '{sub_ctrl_name}' 颜色设为淡化的RGB: {lighter_rgb}")
                elif parent_index is not None:
                    # 如果父控制器使用索引颜色，则子控制器使用更淡的索引颜色
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)

                    # Maya颜色索引映射表 - 从深色到浅色
                    color_map = {
                        # 红色系
                        4: 31,  # 暗红 -> 粉红
                        12: 31,  # 红棕 -> 粉红
                        13: 20,  # 红色 -> 浅红
                        24: 20,  # 红色 -> 浅红
                        31: 9,  # 粉红 -> 淡粉

                        # 蓝色系
                        5: 18,  # 深蓝 -> 浅蓝
                        6: 18,  # 蓝色 -> 浅蓝
                        15: 18,  # 海军蓝 -> 浅蓝
                        18: 29,  # 浅蓝 -> 淡蓝

                        # 绿色系
                        7: 19,  # 绿色 -> 浅绿
                        19: 29,  # 浅绿 -> 淡绿
                        23: 19,  # 深绿 -> 浅绿

                        # 黄色系
                        17: 22,  # 黄色 -> 浅黄
                        21: 22,  # 黄褐色 -> 浅黄
                        11: 21,  # 棕色 -> 黄褐色
                        10: 11,  # 深棕 -> 棕色

                        # 紫色系
                        8: 30,  # 紫色 -> 淡紫
                        9: 30,  # 淡紫红 -> 淡紫

                        # 青色系
                        14: 29,  # 亮蓝 -> 淡蓝
                        16: 29,  # 青色 -> 淡蓝绿

                        # 灰色系
                        0: 3,  # 黑色 -> 深灰
                        1: 3,  # 黑色 -> 深灰
                        2: 3,  # 深灰2 -> 深灰
                        3: 2,  # 深灰 -> 灰色
                        25: 22,  # 棕黄 -> 浅黄
                        26: 19,  # 草绿 -> 浅绿
                        27: 30,  # 深紫 -> 淡紫
                        28: 16,  # 褐色 -> 青色
                    }

                    # 使用映射表或简单加亮规则
                    if parent_index in color_map:
                        new_index = color_map[parent_index]
                    else:
                        # 默认规则：如果没有特定映射，使用索引+2 (限制在有效范围内)
                        new_index = min(parent_index + 2, 31)

                    cmds.setAttr(f"{shape}.overrideColor", new_index)
                    print(f"子控制器 '{sub_ctrl_name}' 颜色索引从 {parent_index} 改为 {new_index}")
                else:
                    # 如果父控制器没有设置颜色，使用默认淡蓝色
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                    cmds.setAttr(f"{shape}.overrideColor", 18)  # 浅蓝色
                    print(f"子控制器 '{sub_ctrl_name}' 设置默认颜色索引 18 (浅蓝色)")

            return sub_ctrl_name, output_name
        except Exception as e:
            print(f"创建子控制器时出错: {str(e)}")
            return None, None

    def center_icon_vertically(self):
        """将图标垂直居中显示在其容器中"""
        if hasattr(self, 'gif_label') and hasattr(self, 'gif_container'):
            # 计算居中位置
            container_height = self.gif_container.height()
            icon_height = self.gif_label.height()
            
            # 设置图标的垂直位置（水平位置保持不变）
            if container_height > icon_height:
                y_pos = (container_height - icon_height) // 2
                self.gif_label.move(self.gif_label.x(), y_pos)
                
                # 保存初始位置信息到图标对象
                self.gif_label.start_position = self.gif_label.pos()
                
            # 确保gif_label可以自由定位
            self.gif_label.setProperty("centered", True)

    def showMainContextMenu(self, pos):
        """显示主窗口右键菜单，用于控制图标显示"""
        context_menu = QMenu(self)
        
        # 根据图标当前状态添加显示/隐藏选项
        icon_visible = self.gif_label.is_visible if hasattr(self.gif_label, 'is_visible') else True
        toggle_action = QAction("隐藏图标" if icon_visible else "显示图标", self)
        toggle_action.triggered.connect(self.toggleIconVisibility)
        context_menu.addAction(toggle_action)
        
        # 添加图标设置选项
        settings_action = QAction("图标设置", self)
        settings_action.triggered.connect(lambda: self.gif_label.showSettingsDialog() if hasattr(self.gif_label, 'showSettingsDialog') else None)
        # 当图标隐藏时禁用设置选项
        settings_action.setEnabled(icon_visible)
        context_menu.addAction(settings_action)
        
        # 添加重置图标位置选项
        reset_pos_action = QAction("重置图标位置", self)
        reset_pos_action.triggered.connect(lambda: self.gif_label.resetPosition() if hasattr(self.gif_label, 'resetPosition') else None)
        # 当图标隐藏时禁用重置位置选项
        reset_pos_action.setEnabled(icon_visible)
        context_menu.addAction(reset_pos_action)
        
        # 显示菜单
        context_menu.exec_(self.mapToGlobal(pos))

    def adjustSize(self):
        """重写adjustSize方法，防止窗口自动调整大小"""
        # 获取滚动区域
        scroll_area = None
        for child in self.findChildren(QScrollArea):
            scroll_area = child
            break
        
        # 如果没有滚动区域，调用默认实现
        if not scroll_area or not scroll_area.widget():
            return super().adjustSize()
        
        # 仅更新内部布局，不调整窗口大小
        central_widget = self.centralWidget()
        if central_widget:
            central_widget.updateGeometry()
        
        # 更新内容布局
        content = scroll_area.widget()
        if content:
            content.updateGeometry()
            if content.layout():
                content.layout().invalidate()
                content.layout().activate()
        
        # 更新UI但不改变窗口大小
        self.update()

    def _apply_icon_visibility(self, visible):
        """应用图标可见性状态而不保存设置"""
        if not hasattr(self, 'gif_label'):
            return
            
        # 直接设置内部状态，避免循环调用toggleVisibility
        self.gif_label.is_visible = visible
        
        # 执行与toggleVisibility相同的显示/隐藏逻辑，但不保存设置
        if hasattr(self.gif_label, 'movie') and self.gif_label.movie:
            if visible:
                self.gif_container.setMinimumHeight(70)
                self.gif_label.movie.start()
                self.gif_label.setFixedSize(self.gif_label.current_size)
                self.gif_label.show()
            else:
                self.gif_label.movie.stop()
                self.gif_label.setFixedSize(0, 0)
                self.gif_container.setMinimumHeight(10)
        else:
            if visible:
                self.gif_container.setMinimumHeight(70)
                self.gif_label.setFixedSize(self.gif_label.current_size)
                self.gif_label.show()
            else:
                self.gif_label.setFixedSize(0, 0)
                self.gif_container.setMinimumHeight(10)
                
        # 更新布局
        self.gif_label.updateLayout()
        QTimer.singleShot(0, self.adjustSize)
        
        print(f"已应用可见性状态: {visible}")
    
    def toggleIconVisibility(self):
        """切换图标显示状态并调整UI"""
        if hasattr(self.gif_label, 'toggleVisibility'):
            # 调用toggleVisibility会自动保存状态
            self.gif_label.toggleVisibility()
            # 延迟调整主窗口大小和布局，以确保图标状态已更新
            QTimer.singleShot(100, self.adjustSize)
            # 打印当前状态以便调试
            print(f"图标状态已切换，当前可见性: {self.gif_label.is_visible}")

    def parse_object_name(self, object_name, ignore_suffix=True):
        """解析物体名称，提取控制器名称
        
        参数:
            object_name (str): 物体名称（支持骨骼、网格、组等任意Maya物体）
            ignore_suffix (bool): 是否忽略后缀，默认为True
            
        返回:
            str: 解析后的控制器基础名称
        """
        # 移除路径前缀，只保留节点名称
        clean_name = object_name.split("|")[-1]
        
        # 根据选项决定是否移除后缀
        if ignore_suffix:
            # 移除任何以下划线开头的后缀，使其更通用
            # 例如：_001, _abc, _L, _R, _ctrl等任意后缀
            name_without_suffix = re.sub(r'_[^_]*$', '', clean_name)
        else:
            # 不忽略后缀，使用原始名称
            name_without_suffix = clean_name
        
        # 检查是否符合标准命名格式（支持多种前缀）
        # 支持的格式：jnt_m_aaa, mesh_l_bbb, grp_r_ccc, ctrl_m_ddd等
        if ignore_suffix:
            pattern = r'^([a-zA-Z]+)_([lrcm])_([^_]+)$'
        else:
            pattern = r'^([a-zA-Z]+)_([lrcm])_([^_]+)(_.*)?$'
        
        match = re.match(pattern, name_without_suffix, re.IGNORECASE)
        
        if match:
            # 符合标准格式，提取前缀、侧面和名称部分
            prefix = match.group(1).lower()
            side = match.group(2).lower()
            name_part = match.group(3)
            if ignore_suffix:
                return f"{side}_{name_part}"
            else:
                # 保留后缀（如果有的话）
                suffix_part = match.group(4) if len(match.groups()) > 3 and match.group(4) else ""
                return f"{side}_{name_part}{suffix_part}"
        else:
            # 不符合标准格式，尝试识别常见前缀并移除
            result_name = name_without_suffix
            # 移除常见的Maya物体前缀
            common_prefixes = ['jnt_', 'joint_', 'mesh_', 'geo_', 'grp_', 'group_', 'ctrl_', 'control_', 'loc_', 'locator_']
            for prefix in common_prefixes:
                if result_name.lower().startswith(prefix):
                    result_name = result_name[len(prefix):]
                    break
            return result_name
    
    @with_undo_support
    def create_fk_hierarchy(self):
        """为选中的骨骼链创建FK控制器层级"""
        selected = cmds.ls(selection=True, type="joint")
        
        if not selected:
            cmds.warning("请先选择一个骨骼作为FK链的起始点")
            return
        
        root_joint = selected[0]
        
        # 获取骨骼链
        joint_chain = self.get_joint_chain(root_joint)
        
        if not joint_chain:
            cmds.warning(f"无法从 {root_joint} 获取有效的骨骼链")
            return
        
        # 如果需要排除最后一个骨骼，则移除
        exclude_last = self.exclude_last_joint_check.isChecked()
        if exclude_last and len(joint_chain) > 1:
            joint_chain.pop()
        
        # 检查是否启用物体名称识别
        use_auto_naming = self.auto_name_from_joint_check.isChecked()
        
        # 检查是否忽略后缀
        ignore_suffix = self.ignore_suffix_check.isChecked()
        
        # 从创建关节控制器组件获取设置
        custom_name = self.name_text.text()
        custom_sides = self.side_text.text().strip()
        # 解析用户输入的侧面，支持逗号分隔，例如 "l,r,m"
        sides_list = [s.strip() for s in custom_sides.split(',')] if custom_sides else []
        use_custom_side = len(sides_list) == 1  # 如果只有一个侧面，使用它替代从关节名提取的侧面
        
        create_joint_flag = self.create_joint_flag
        create_controller_flag = self.create_controller_flag
        create_sub_controller_flag = self.create_sub_controller_flag
        use_hierarchy_logic = self.use_hierarchy_logic
        controller_type = self.controller_type
        ctrl_size = self.size_spin.value()
        
        # 确定约束设置
        parent_constraint = self.parent_constraint_check.isChecked()
        parent_offset = self.parent_offset_check.isChecked()
        point_constraint = self.point_constraint_check.isChecked()
        point_offset = self.point_offset_check.isChecked()
        orient_constraint = self.orient_constraint_check.isChecked()
        orient_offset = self.orient_offset_check.isChecked()
        scale_constraint = self.scale_constraint_check.isChecked()
        scale_offset = self.scale_offset_check.isChecked()
        
        # ==== 修改逻辑：先创建所有控制器及组结构 ====
        
        # 存储创建的控制器和组的信息，以便后续处理
        controller_info = []
        controllers = []
        prev_ctrl = None
        
        # 第一步：创建所有控制器和组
        for i, joint in enumerate(joint_chain):
            # 获取关节名称信息
            joint_name = joint.split("|")[-1]  # 移除全路径
            
            # 根据是否启用物体名称识别来确定命名方式
            if use_auto_naming:
                # 使用物体名称识别功能
                parsed_name = self.parse_object_name(joint_name, ignore_suffix)
                
                # 检查解析结果是否包含侧面信息
                if "_" in parsed_name and parsed_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息，直接使用
                    side_and_name = parsed_name
                    formatted_side = ""
                    base_name = parsed_name
                else:
                    # 不包含侧面信息，使用原有逻辑确定侧面
                    side = ""
                    if use_custom_side and sides_list[0]:  # 使用用户指定的侧面
                        side = sides_list[0].lower()
                    elif "_" in joint_name:  # 从关节名称中提取侧面
                        parts = joint_name.split("_")
                        possible_side = parts[0].lower()
                        if possible_side in ["l", "r", "c", "m"]:
                            side = possible_side
                    
                    formatted_side = f"_{side}" if side else ""
                    base_name = parsed_name
                
                # 使用解析的名称，添加序号后缀
                suffix = f"_{i+1:03d}"  # 使用_001格式的后缀
                
                # 创建零组和控制器名称
                if "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    zero_group_name = f"zero_{base_name}{suffix}"
                    ctrl_name = f"ctrl_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    zero_group_name = f"zero{formatted_side}_{base_name}{suffix}"
                    ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
            else:
                # 使用原有的命名逻辑
                # 确定侧面信息
                side = ""
                if use_custom_side and sides_list[0]:  # 使用用户指定的侧面
                    side = sides_list[0].lower()
                elif "_" in joint_name:  # 从关节名称中提取侧面
                    parts = joint_name.split("_")
                    possible_side = parts[0].lower()
                    if possible_side in ["l", "r", "c", "m"]:
                        side = possible_side
                
                # 确定使用的控制器基础名称和后缀
                suffix = f"_{i+1:03d}"  # 使用_001格式的后缀
                
                if custom_name:
                    base_name = custom_name  # 使用用户指定的名称
                else:
                    # 使用关节名称的最后一部分作为基础名称
                    base_name = joint_name.split("_")[-1] if "_" in joint_name else joint_name
                
                formatted_side = f"_{side}" if side else ""
                
                # 创建零组和控制器，采用基础名称+后缀的命名方式
                zero_group_name = f"zero{formatted_side}_{base_name}{suffix}"
                ctrl_name = f"ctrl{formatted_side}_{base_name}{suffix}"
            
            # 创建组层级结构
            if use_hierarchy_logic:
                zero_group = cmds.group(name=zero_group_name, empty=True)
                
                # 根据命名方式确定其他组的名称
                if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    driven_group_name = f"driven_{base_name}{suffix}"
                    connect_group_name = f"connect_{base_name}{suffix}"
                    offset_group_name = f"offset_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    driven_group_name = f"driven{formatted_side}_{base_name}{suffix}"
                    connect_group_name = f"connect{formatted_side}_{base_name}{suffix}"
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"
                
                driven_group = cmds.group(name=driven_group_name, empty=True, parent=zero_group)
                connect_group = cmds.group(name=connect_group_name, empty=True, parent=driven_group)
                offset_group = cmds.group(name=offset_group_name, empty=True, parent=connect_group)
                last_group = offset_group
            else:
                zero_group = cmds.group(name=zero_group_name, empty=True)
                
                # 根据命名方式确定offset组的名称
                if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                    # 已包含侧面信息的情况
                    offset_group_name = f"offset_{base_name}{suffix}"
                else:
                    # 不包含侧面信息的情况
                    offset_group_name = f"offset{formatted_side}_{base_name}{suffix}"
                    
                offset_group = cmds.group(name=offset_group_name, empty=True, parent=zero_group)
                last_group = offset_group
            
            # 创建控制器
            if create_controller_flag:
                ctrl = controller_shapes.create_custom_controller(
                    ctrl_name=ctrl_name, 
                    controller_type=controller_type, 
                    size=ctrl_size
                )
                
                # 设置控制器颜色
                controller_shapes.apply_color_to_controller(ctrl, self.color_rgb)
                
                # 为控制器形状节点重命名为"曲线名称_Shape"格式
                controller_shapes.rename_controller_shape(ctrl)
                
                # 父级控制器到最后一个组
                cmds.parent(ctrl, last_group)
                
                # 确保旋转顺序是可见的和可关键帧的
                cmds.setAttr(f"{ctrl}.rotateOrder", channelBox=True, keyable=True)
                
                # 如果启用了子控制器选项，创建子控制器
                sub_ctrl = None
                output_group = None
                if create_sub_controller_flag:
                    # 创建子控制器
                    sub_ctrl_name = f"{ctrl_name}_sub"
                    sub_ctrl = controller_shapes.create_custom_controller(
                        ctrl_name=sub_ctrl_name,
                        controller_type=controller_type,
                        size=ctrl_size * 0.8
                    )
                    
                    # 为子控制器形状节点重命名为"曲线名称_Shape"格式
                    controller_shapes.rename_controller_shape(sub_ctrl)
                    
                    # 设置子控制器颜色 (稍微暗一点)
                    sub_color = tuple(c * 0.8 for c in self.color_rgb)
                    controller_shapes.apply_color_to_controller(sub_ctrl, sub_color)
                    
                    # 创建输出组 - 这将用于连接FK链和约束
                    if use_auto_naming and "_" in base_name and base_name.split("_")[0].lower() in ["l", "r", "c", "m"]:
                        # 已包含侧面信息的情况
                        output_name = f"output_{base_name}{suffix}"
                    else:
                        # 不包含侧面信息的情况
                        output_name = f"output{formatted_side}_{base_name}{suffix}"
                    output_group = cmds.group(name=output_name, empty=True)
                    
                    # 重要：将子控制器和输出组都放在控制器下面
                    cmds.parent(sub_ctrl, ctrl)
                    cmds.parent(output_group, ctrl)
                    
                    # 添加调试输出
                    print(f"层级结构: 已创建子控制器 '{sub_ctrl}' 和输出组 '{output_group}'，并放置在控制器 '{ctrl}' 下")
                    
                    # 添加子控制器可见性属性，默认设置为不可见
                    cmds.addAttr(ctrl, longName="subCtrlVis", attributeType="bool", defaultValue=0)
                    cmds.setAttr(f"{ctrl}.subCtrlVis", channelBox=True, keyable=False)
                    cmds.connectAttr(f"{ctrl}.subCtrlVis", f"{sub_ctrl}.visibility")
                    print(f"可见性: 子控制器 '{sub_ctrl}' 默认设置为隐藏，可在通道框中显示但不可关键帧")
                    
                    # 确保子控制器的旋转顺序是可见的和可关键帧的
                    cmds.setAttr(f"{sub_ctrl}.rotateOrder", channelBox=True, keyable=True)
                    
                    # 连接子控制器到输出组 - 确保子控制器驱动输出组
                    cmds.connectAttr(f"{sub_ctrl}.translate", f"{output_group}.translate")
                    cmds.connectAttr(f"{sub_ctrl}.rotate", f"{output_group}.rotate")
                    cmds.connectAttr(f"{sub_ctrl}.rotateOrder", f"{output_group}.rotateOrder")
                    cmds.connectAttr(f"{sub_ctrl}.scale", f"{output_group}.scale")
                    print(f"连接: 已将子控制器 '{sub_ctrl}' 变换连接到输出组 '{output_group}'")
            else:
                # 如果不创建控制器，创建一个空组作为控制器
                ctrl = cmds.group(name=ctrl_name, empty=True, parent=last_group)
                sub_ctrl = None
                output_group = None
            
            # 存储控制器信息
            controller_info.append({
                'joint': joint,
                'zero_group': zero_group,
                'ctrl': ctrl,
                'sub_ctrl': sub_ctrl,
                'output_group': output_group,
                'last_group': last_group
            })
            
            controllers.append(ctrl)
        
        # 第二步：建立FK层级关系（使第一个控制器保持在世界空间，其余控制器成为链）
        for i in range(1, len(controller_info)):
            prev_info = controller_info[i-1]
            curr_info = controller_info[i]
            
            # 重要：当启用子控制器时，确保零组连接到前一个控制器的output组
            if prev_info['output_group']:
                # 有output组，连接到output组
                prev_output = prev_info['output_group']
                parent_type = "output组"
            else:
                # 没有output组，连接到控制器本身
                prev_output = prev_info['ctrl']
                parent_type = "控制器"
            
            # 将当前zero组父级到确定的节点（output组或控制器）
            cmds.parent(curr_info['zero_group'], prev_output)
            
            # 添加调试输出
            print(f"FK链接: 将 '{curr_info['zero_group']}' 父级到前一个{parent_type} '{prev_output}'")
        
        # 第三步：匹配位置和旋转，应用约束
        for info in controller_info:
            joint = info['joint']
            zero_group = info['zero_group']
            ctrl = info['ctrl']
            sub_ctrl = info['sub_ctrl']
            output_group = info['output_group']
            
            # 匹配zero组到关节位置
            cmds.matchTransform(zero_group, joint, position=True, rotation=True)
            
            # 如果有子控制器和输出组，匹配它们到控制器
            if sub_ctrl and output_group:
                cmds.matchTransform(sub_ctrl, ctrl, position=True, rotation=True)
                cmds.matchTransform(output_group, ctrl, position=True, rotation=True)
                
                # 应用约束到骨骼
                constraint_target = output_group
                print(f"将使用输出组 '{output_group}' 约束骨骼 '{joint}'")
            else:
                constraint_target = ctrl
                print(f"将使用控制器 '{ctrl}' 约束骨骼 '{joint}'")
            
            # 应用约束
            if parent_constraint:
                constraint = cmds.parentConstraint(constraint_target, joint, maintainOffset=parent_offset)
                print(f"已创建父子约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
            else:
                if point_constraint:
                    constraint = cmds.pointConstraint(constraint_target, joint, maintainOffset=point_offset)
                    print(f"已创建点约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
                if orient_constraint:
                    constraint = cmds.orientConstraint(constraint_target, joint, maintainOffset=orient_offset)
                    print(f"已创建方向约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
            
            if scale_constraint:
                constraint = cmds.scaleConstraint(constraint_target, joint, maintainOffset=scale_offset)
                print(f"已创建缩放约束 '{constraint}' 从 '{constraint_target}' 到 '{joint}'")
        
        # 如果成功创建控制器，选择第一个控制器
        if controllers:
            # 确保所有控制器的subCtrlVis属性是不可关键帧的
            for ctrl in controllers:
                if cmds.attributeQuery("subCtrlVis", node=ctrl, exists=True):
                    try:
                        cmds.setAttr(f"{ctrl}.subCtrlVis", channelBox=True, keyable=False)
                        print(f"确保FK控制器 '{ctrl}.subCtrlVis' 属性在通道框中可见但不可关键帧")
                    except Exception as e:
                        print(f"无法设置 '{ctrl}.subCtrlVis' 属性: {str(e)}")
                        
            cmds.select(controllers[0])
            print(f"✅ 成功创建FK层级链，共 {len(controllers)} 个控制器")
        else:
            cmds.warning("创建FK层级链失败")

    def get_joint_chain(self, root_joint):
        """获取从指定根骨骼开始的骨骼链
        
        参数:
            root_joint (str): 根骨骼名称
            
        返回:
            list: 骨骼链列表
        """
        joint_chain = [root_joint]
        current = root_joint
        
        # 循环查找子骨骼，直到没有子骨骼为止
        while True:
            children = cmds.listRelatives(current, children=True, type="joint") or []
            
            # 如果没有子骨骼或有多个子骨骼，停止
            if not children or len(children) > 1:
                break
            
            # 添加到链中并更新当前骨骼
            joint_chain.append(children[0])
            current = children[0]
        
        return joint_chain

    def update_font_size(self, font_size):
        """更新整个UI的字体大小"""
        # 保存当前字体大小设置
        self.font_size = font_size
        
        # 更新样式表
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QWidget {{
                background-color: #2D2D30;
                color: #E0E0E0;
            }}
            QPushButton {{
                background-color: #3E3E42;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 22px;
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: #505054;
                border-color: #6A6A6A;
            }}
            QPushButton:pressed {{
                background-color: #2A2A2A;
                border-color: #777777;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                selection-background-color: #264F78;
                font-size: {font_size}px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox {{
                background-color: #333337;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px 5px;
                min-height: 20px;
                font-size: {font_size}px;
            }}
            QComboBox:hover {{
                border-color: #6A6A6A;
            }}
            QComboBox:focus {{
                border-color: #0078D7;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QCheckBox {{
                color: #E0E0E0;
                spacing: 6px;
                font-size: {font_size}px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid #555555;
                border-radius: 2px;
                background-color: #333337;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0078D7;
                border-color: #0078D7;
            }}
            QCheckBox::indicator:hover {{
                border-color: #6A6A6A;
            }}
            QLabel {{
                color: #E0E0E0;
                font-size: {font_size}px;
            }}
            QScrollArea {{
                background-color: #2D2D30;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: #2D2D30;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #555555;
                min-height: 20px;
                border-radius: 3px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #6A6A6A;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: #2D2D30;
            }}
            QToolTip {{
                background-color: #2D2D30;
                color: #E0E0E0;
                border: 1px solid #555555;
                padding: 4px;
                opacity: 220;
                font-size: {font_size}px;
            }}
            QFrame[frameShape="4"] {{ /* 分隔线 */
                background-color: #555555;
                height: 1px;
                max-height: 1px;
            }}
        """)
        
        # 更新所有CollapsibleGroupBox的字体大小
        for group_box in self.findChildren(CollapsibleGroupBox):
            # 更新按钮样式
            group_box.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3A3A3A;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 12px;
                    text-align: left;
                    font-weight: bold;
                    font-size: {font_size}px;
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: #4A4A4A;
                }}
                QPushButton:pressed {{
                    background-color: #353535;
                }}
            """)
            
        # 保存设置到Maya optionVar
        cmds.optionVar(intValue=("CKTool_FontSize", font_size))
        
        # 调整窗口大小以适应新的字体大小
        QTimer.singleShot(100, self.adjustSize)

    @with_undo_support
    def match_selected_transforms(self):
        """匹配选中物体的变换到最后一个选中的物体"""
        selected_objects = cmds.ls(selection=True)
        if len(selected_objects) < 2:
            cmds.warning("请选择至少两个物体，最后一个选中的物体将作为目标")
            return

        target_obj = selected_objects[-1]
        source_objects = selected_objects[:-1]

        for obj in source_objects:
            cmds.matchTransform(obj, target_obj,
                              pos=self.match_position,
                              rot=self.match_rotation,
                              scl=self.match_scale)
        print(f"已将 {len(source_objects)} 个物体匹配到 '{target_obj}' 的变换")


# 运行工具
def run_tool():
    try:
        # 使用get_instance方法获取窗口实例，不需要在这里额外检查窗口是否存在
        # get_instance已经包含了完整的窗口唯一性处理逻辑
        window = CombinedTool.get_instance()
        window.show()
        window.raise_()  # 将窗口置于前台
        window.activateWindow()  # 激活窗口
        return window
    except Exception as e:
        print(f"运行工具时出错: {str(e)}")
        print("请确保在Maya环境中运行此工具")
        return None


if __name__ == "__main__":
    try:
        # 尝试导入maya.cmds
        from maya import cmds
        run_tool()
    except ImportError:
        print("=" * 50)
        print("错误: 此工具需要在Maya环境中运行")
        print("请使用Maya的script editor或通过Maya的Python解释器运行此脚本")
        print("=" * 50)
    except Exception as e:
        print(f"工具启动失败: {str(e)}")
        print("请确保在Maya环境中运行此工具")