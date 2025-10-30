#coding=utf-8
import os

try:
    from PySide.QtGui import *
    from PySide.QtCore import *
except ImportError:
    from PySide2.QtGui import *
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *


def get_app():
    top = QApplication.activeWindow()
    if top is None:
        return None
    while True:
        parent = top.parent()
        if parent is None:
            return top
        top = parent


def q_add(layout, *elements):
    for elem in elements:
        if isinstance(elem, QLayout):
            layout.addLayout(elem)
        elif isinstance(elem, QWidget):
            layout.addWidget(elem)
    return layout


def q_button(text, action):
    but = QPushButton(text)
    but.clicked.connect(action)
    return but


class ShapeList(QListWidget):
    """控制器列表：展示 Lib 下脚本的图标并双击创建"""
    def __init__(self, tool):
        QListWidget.__init__(self)
        self.tool = tool
        self.setViewMode(self.IconMode)
        self.setMovement(self.Static)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setIconSize(QSize(64, 64))
        self.setResizeMode(self.Adjust)
        self.setSelectionMode(self.ExtendedSelection)
        self.itemDoubleClicked.connect(lambda x: self.tool.MakeController(x.script_file))
        self.update_shapes()

    def update_shapes(self):
        self.clear()
        listMel = self.tool.findAllSuffix(self.tool.current_dir, '.mel')
        listPy = self.tool.findAllSuffix(self.tool.current_dir, '.py')
        listScripts = listMel + listPy
        for script_file in listScripts:
            base_name, _ = os.path.splitext(script_file)
            icon_file = base_name + '.png'
            icon_path = icon_file if os.path.isfile(icon_file) else self.tool.icon_file
            item = QListWidgetItem(QIcon(icon_path), "", self)
            item.script_file = script_file
            item.setSizeHint(QSize(67, 67))


class ColorList(QListWidget):
    """颜色列表：双击设置选中对象颜色"""
    def __init__(self, tool):
        QListWidget.__init__(self)
        self.tool = tool
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewMode(self.IconMode)
        self.setMovement(self.Static)
        self.setIconSize(QSize(32, 32))
        self.setResizeMode(self.Adjust)
        self.setFixedHeight(35*4)
        for i, rgb in enumerate(self.tool.BackGroundColor):
            pix = QPixmap(32, 32)
            try:
                color = QColor.fromRgbF(*rgb)
            except Exception:
                color = QColor(128, 128, 128)
            pix.fill(color)
            item = QListWidgetItem(QIcon(pix), "", self)
            item.setSizeHint(QSize(35, 34))
        self.itemDoubleClicked.connect(lambda x: self.tool.SetShapeColor(self.indexFromItem(x).row()))


class ControlsWindow(QDialog):
    def __init__(self, tool):
        QDialog.__init__(self, get_app())
        self.tool = tool
        self.setWindowTitle("Maya Controller Tool 1.2")
        self.resize(QSize(340, 600))
        self.setLayout(q_add(
            QVBoxLayout(),
            ShapeList(self.tool),
            ColorList(self.tool),
            q_add(
                QHBoxLayout(),
                q_button(u"缩放", self.tool.scale_control),
                q_button(u"镜像", self.tool.mirror_control),
                q_button(u"替换", self.tool.replace_control),
                q_button(u"冻结", self.tool.freeze_control),
            ),
            q_add(
                QHBoxLayout(),
                q_button(u"关联控制器到面板形状", self.tool.curve_picker),
                q_button(u"删除面板", self.tool.clearPanel),
            ),
            q_add(
                QHBoxLayout(),
                q_button(u"刷新控制器库", self.tool.refreshControllers),
                q_button(u"截屏控制器", self.tool.screenshotController),
            ),
        ))
        for but in self.findChildren(QPushButton):
            but.setMinimumWidth(20)
