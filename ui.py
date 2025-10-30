
# 创建Qt兼容层，支持PySide2和PySide6
def _import_qt():
    """动态导入Qt模块，优先尝试PySide2（Maya默认），如果不可用则尝试PySide6"""
    qt_binding = ""
    shiboken_module = None
    
    # 尝试导入PySide2（Maya默认）
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
        import shiboken2
        qt_binding = "PySide2"
        shiboken_module = shiboken2
        print("使用PySide2")
    except ImportError:
        try:
            # 尝试导入PySide6
            from PySide6 import QtWidgets, QtGui, QtCore
            import shiboken6
            qt_binding = "PySide6"
            shiboken_module = shiboken6
            print("使用PySide6")
        except ImportError:
            # 如果两者都不可用，抛出错误
            raise ImportError("无法导入PySide2或PySide6，请确保至少安装了其中一个")
    
    return QtWidgets, QtGui, QtCore, qt_binding, shiboken_module

# 导入Qt模块
QtWidgets, QtGui, QtCore, qt_binding, shiboken = _import_qt()

# 导入Maya相关模块
from maya import cmds
import maya.mel as mel
import sys
import os

# 从导入的模块中获取所需的类
QApplication = QtWidgets.QApplication
QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QPushButton = QtWidgets.QPushButton
QLineEdit = QtWidgets.QLineEdit
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QColorDialog = QtWidgets.QColorDialog
QLabel = QtWidgets.QLabel
QGridLayout = QtWidgets.QGridLayout
QScrollArea = QtWidgets.QScrollArea
QToolTip = QtWidgets.QToolTip
QFrame = QtWidgets.QFrame
QGraphicsOpacityEffect = QtWidgets.QGraphicsOpacityEffect
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QGroupBox = QtWidgets.QGroupBox
QRadioButton = QtWidgets.QRadioButton
QFileDialog = QtWidgets.QFileDialog
QTabWidget = QtWidgets.QTabWidget
QMessageBox = QtWidgets.QMessageBox
QSizePolicy = QtWidgets.QSizePolicy
QDialog = QtWidgets.QDialog
QSlider = QtWidgets.QSlider
QMenu = QtWidgets.QMenu

# 从QtGui导入
QColor = QtGui.QColor
QPalette = QtGui.QPalette
QFont = QtGui.QFont
QPixmap = QtGui.QPixmap
QPainter = QtGui.QPainter
QImage = QtGui.QImage
QCursor = QtGui.QCursor
QMovie = QtGui.QMovie

# 处理QAction在PySide2和PySide6中的位置差异
# 在PySide2中，QAction在QtWidgets中
# 在PySide6中，QAction在QtGui中
if qt_binding == "PySide2":
    QAction = QtWidgets.QAction
else:  # PySide6
    QAction = QtGui.QAction

# 从QtCore导入
Qt = QtCore.Qt
QTimer = QtCore.QTimer
QEvent = QtCore.QEvent
QPropertyAnimation = QtCore.QPropertyAnimation
QEasingCurve = QtCore.QEasingCurve
QParallelAnimationGroup = QtCore.QParallelAnimationGroup
QPoint = QtCore.QPoint
QSize = QtCore.QSize
QRect = QtCore.QRect
QSequentialAnimationGroup = QtCore.QSequentialAnimationGroup

# 导入Maya OpenMayaUI
from maya import OpenMayaUI

# 获取 Maya 主窗口作为 Qt 小部件
def get_maya_main_window():
    main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
    if main_window_ptr is not None:
        return shiboken.wrapInstance(int(main_window_ptr), QWidget)
    return None


# 确保 PySide2 应用实例存在
if QApplication.instance() is None:
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

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
        # 集中定义预设颜色（RGB 0-1），用于颜色网格与颜色对话框
        self.preset_colors = [
            (0.5, 0.5, 0.5), (0, 0, 0), (0.247, 0.247, 0.247), (0.498, 0.498, 0.498),
            (0.608, 0, 0.157), (0, 0.16, 0.376), (0, 0, 1), (0, 0.275, 0.094),
            (0.149, 0, 0.263), (0.78, 0, 0.78), (0.537, 0.278, 0.2), (0.243, 0.133, 0.121),
            (0.6, 0.145, 0), (1, 0, 0), (0, 1, 0), (0, 0.2549, 0.6),
            (1, 1, 1), (1, 1, 0), (0.388, 0.863, 1), (0.263, 1, 0.639),
            (1, 0.686, 0.686), (0.89, 0.674, 0.474), (1, 1, 0.388), (0, 0.6, 0.329),
            (0.627, 0.411, 0.188), (0.619, 0.627, 0.188), (0.408, 0.631, 0.188), (0.188, 0.631, 0.365),
            (0.188, 0.627, 0.627), (0.188, 0.403, 0.627), (0.434, 0.188, 0.627), (0.627, 0.188, 0.411)
        ]
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

        # 缩放模式选项：使用形状局部中心缩放
        mode_layout = QHBoxLayout()
        self.local_scale_checkbox = QCheckBox("使用形状局部中心缩放")
        self.local_scale_checkbox.setToolTip("勾选时以每个形状的局部中心点为基准缩放，\n不勾选时以控制器的轴心点为基准缩放")
        self.local_scale_checkbox.setChecked(False)
        mode_layout.addWidget(self.local_scale_checkbox)
        mode_layout.addStretch()
        fixed_controls_layout.addLayout(mode_layout)

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
            hex_color = self.rgb_to_hex(self.color_rgb)
            text_color = self.compute_text_color(r, g, b)
            self.apply_preview_style(hex_color, text_color, "2px solid #0078D7")

        def preview_leave_event(event):
            r, g, b = [int(c * 255) for c in self.color_rgb]
            hex_color = self.rgb_to_hex(self.color_rgb)
            text_color = self.compute_text_color(r, g, b)
            self.apply_preview_style(hex_color, text_color, "1px solid #666666")

        self.color_preview.enterEvent = preview_enter_event
        self.color_preview.leaveEvent = preview_leave_event

        self.update_color_preview()
        color_layout.addWidget(QLabel("颜色:"), 0, 0)
        color_layout.addWidget(self.color_preview, 0, 1)
        color_layout.addWidget(QLabel("预设颜色："), 1, 0)
        
        # 使用集中定义的预设颜色
        preset_colors = self.preset_colors
        
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
            color_button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #666666; padding: 0px;")
            color_button.clicked.connect(lambda checked=False, rgb=color: self.apply_preset_color(rgb))
            
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
        
        # 添加FK约束打组工具按钮
        fk_constraint_group_button = DelayedToolTipButton("FK约束打组工具", "打开高级FK约束打组工具界面")
        fk_constraint_group_button.setMinimumHeight(30)
        fk_constraint_group_button.setStyleSheet("""
            QPushButton {
                background-color: #ff9933; 
                color: white; 
                border-radius: 3px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68a2e;
            }
            QPushButton:pressed {
                background-color: #cc7a29;
            }
        """)
        fk_constraint_group_button.clicked.connect(self.open_fk_constraint_group_tool)
        fk_hierarchy_layout.addWidget(fk_constraint_group_button)

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
        if hasattr(self, 'snap_to_pivot_tool') and self.snap_to_pivot_tool:
            self.snap_to_pivot_tool.close()
        
        # 继续事件传递
        super().closeEvent(event)

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
