# -*- coding: utf-8 -*-
"""
曲线大小调整工具
独立的Maya曲线控制器缩放工具

功能:
- 调整选中控制器的控制顶点大小
- 支持自定义缩放倍率
- 提供变大/变小按钮快速操作
- 支持撤销操作
"""

import sys
import math
from functools import wraps

try:
    from PySide2.QtWidgets import *
    from PySide2.QtCore import *
    from PySide2.QtGui import *
except ImportError:
    from PySide.QtGui import *
    from PySide.QtCore import *

try:
    import maya.cmds as cmds
    import maya.OpenMayaUI as omui
except ImportError:
    print(u"错误: 此工具需要在Maya环境中运行")
    sys.exit(1)

try:
    from shiboken2 import wrapInstance
except ImportError:
    from shiboken import wrapInstance


def get_maya_main_window():
    """获取Maya主窗口"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if main_window_ptr is not None:
        return wrapInstance(int(main_window_ptr), QWidget)
    return None


# 全局撤销装饰器
def with_undo_support(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            cmds.undoInfo(openChunk=True)
            result = func(self, *args, **kwargs)
            if func.__name__ not in ["show", "closeEvent"]:
                print(u"'{}' 操作完成。按 Ctrl+Z 可撤销此操作。".format(func.__name__))
            return result
        except Exception as e:
            print(u"'{}' 操作出错: {}".format(func.__name__, e))
            raise
        finally:
            cmds.undoInfo(closeChunk=True)
    return wrapper


class CurveScaleTool(QMainWindow):
    """曲线大小调整工具主窗口"""
    
    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = CurveScaleTool()
        return cls._instance

    def __init__(self):
        super(CurveScaleTool, self).__init__(parent=get_maya_main_window())
        self.setWindowTitle(u"曲线大小调整工具")
        self.setObjectName("CurveScaleToolWindow")
        self.resize(300, 150)
        
        # 设置窗口标志
        self.setWindowFlags(Qt.Window)
        
        # 初始化UI
        self.init_ui()
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 11px;
            }
            QPushButton {
                background-color: #5a5a5a;
                color: #ffffff;
                border: 1px solid #7a7a7a;
                border-radius: 3px;
                padding: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #6a6a6a;
            }
            QPushButton:pressed {
                background-color: #4a4a4a;
            }
            QDoubleSpinBox {
                background-color: #5a5a5a;
                color: #ffffff;
                border: 1px solid #7a7a7a;
                border-radius: 3px;
                padding: 3px;
                font-size: 11px;
            }
        """)

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel(u"曲线大小调整")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # 缩放倍率设置
        scale_layout = QHBoxLayout()
        scale_label = QLabel(u"缩放倍率:")
        scale_layout.addWidget(scale_label)
        
        self.scale_factor_input = QDoubleSpinBox()
        self.scale_factor_input.setRange(0.01, 100.0)
        self.scale_factor_input.setValue(1.1)
        self.scale_factor_input.setSingleStep(0.1)
        self.scale_factor_input.setDecimals(2)
        self.scale_factor_input.setToolTip(u"设置每次缩放的倍率")
        scale_layout.addWidget(self.scale_factor_input)
        
        main_layout.addLayout(scale_layout)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        # 变大按钮
        scale_up_btn = QPushButton(u"变大")
        scale_up_btn.setToolTip(u"按设定倍率放大选中控制器的控制顶点")
        scale_up_btn.clicked.connect(self.scale_cv_handles_up)
        button_layout.addWidget(scale_up_btn)
        
        # 变小按钮
        scale_down_btn = QPushButton(u"变小")
        scale_down_btn.setToolTip(u"按设定倍率缩小选中控制器的控制顶点")
        scale_down_btn.clicked.connect(self.scale_cv_handles_down)
        button_layout.addWidget(scale_down_btn)
        
        main_layout.addLayout(button_layout)
        
        # 缩放模式选项
        mode_layout = QHBoxLayout()
        self.local_scale_checkbox = QCheckBox(u"使用形状局部中心缩放")
        self.local_scale_checkbox.setToolTip(u"勾选时以每个形状的局部中心点为基准缩放，\n不勾选时以控制器的轴心点为基准缩放")
        self.local_scale_checkbox.setChecked(False)  # 默认不勾选，使用控制器轴心点
        mode_layout.addWidget(self.local_scale_checkbox)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # 说明文字
        info_label = QLabel(u"请选择NURBS曲线控制器后使用此工具")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 10px; color: #cccccc; margin-top: 10px;")
        main_layout.addWidget(info_label)
        
        # 添加弹性空间
        main_layout.addStretch()

    def get_shape_local_center(self, shape):
        """计算形状的局部中心点（所有CV的平均位置）"""
        cvs = cmds.ls("{}.cv[*]".format(shape), flatten=True)
        if not cvs:
            return [0, 0, 0]
        
        total_pos = [0, 0, 0]
        for cv in cvs:
            pos = cmds.pointPosition(cv, world=True)
            for i in range(3):
                total_pos[i] += pos[i]
        
        # 计算平均位置
        center = [total_pos[i] / len(cvs) for i in range(3)]
        return center

    @with_undo_support
    def scale_cv_handles_up(self):
        """放大控制器的控制顶点"""
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning(u"请至少选择一个控制器！")
            return

        scale_factor = self.scale_factor_input.value()
        use_local_center = self.local_scale_checkbox.isChecked()
        
        for ctrl in selected_controllers:
            # 获取所有的nurbsCurve形状节点
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                # 遍历每个形状节点
                for shape in shapes:
                    # 获取该形状的所有控制顶点
                    cvs = cmds.ls("{}.cv[*]".format(shape), flatten=True)
                    if cvs:
                        # 根据选项选择缩放中心点
                        if use_local_center:
                            pivot = self.get_shape_local_center(shape)
                        else:
                            pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                        
                        for cv in cvs:
                            pos = cmds.pointPosition(cv, world=True)
                            vector = [pos[i] - pivot[i] for i in range(3)]
                            scaled_vector = [v * scale_factor for v in vector]
                            new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                            cmds.xform(cv, worldSpace=True, translation=new_pos)
                
                mode_text = u"局部中心" if use_local_center else u"控制器轴心"
                print(u"已将控制器 '{}' 的 {} 个形状节点的控制顶点按倍率 {} 放大（基于{}）".format(ctrl, len(shapes), scale_factor, mode_text))
            else:
                print(u"警告: '{}' 不是NURBS曲线控制器，跳过处理".format(ctrl))

    @with_undo_support
    def scale_cv_handles_down(self):
        """缩小控制器的控制顶点"""
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning(u"请至少选择一个控制器！")
            return

        scale_factor = 1.0 / self.scale_factor_input.value()
        use_local_center = self.local_scale_checkbox.isChecked()
        
        for ctrl in selected_controllers:
            # 获取所有的nurbsCurve形状节点
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                # 遍历每个形状节点
                for shape in shapes:
                    # 获取该形状的所有控制顶点
                    cvs = cmds.ls("{}.cv[*]".format(shape), flatten=True)
                    if cvs:
                        # 根据选项选择缩放中心点
                        if use_local_center:
                            pivot = self.get_shape_local_center(shape)
                        else:
                            pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                        
                        for cv in cvs:
                            pos = cmds.pointPosition(cv, world=True)
                            vector = [pos[i] - pivot[i] for i in range(3)]
                            scaled_vector = [v * scale_factor for v in vector]
                            new_pos = [pivot[i] + scaled_vector[i] for i in range(3)]
                            cmds.xform(cv, worldSpace=True, translation=new_pos)
                
                mode_text = u"局部中心" if use_local_center else u"控制器轴心"
                print(u"已将控制器 '{}' 的 {} 个形状节点的控制顶点按倍率 {} 缩小（基于{}）".format(ctrl, len(shapes), 1.0 / scale_factor, mode_text))
            else:
                print(u"警告: '{}' 不是NURBS曲线控制器，跳过处理".format(ctrl))

    def get_cv_handle_scale(self):
        """获取控制器控制顶点的平均缩放值"""
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            print(u"未选择任何控制器，返回默认值 50")
            return 50.0

        total_scale = 0.0
        count = 0
        for ctrl in selected_controllers:
            shapes = cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            if shapes:
                cvs = cmds.ls("{}.cv[*]".format(ctrl), flatten=True)
                if cvs:
                    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
                    for cv in cvs:
                        pos = cmds.pointPosition(cv, world=True)
                        vector = [pos[i] - pivot[i] for i in range(3)]
                        magnitude = math.sqrt(sum(v * v for v in vector))
                        total_scale += magnitude * 50.0
                        count += 1

        if count > 0:
            average_scale = total_scale / count
            print(u"平均缩放值: {}".format(average_scale))
            return average_scale
        else:
            print(u"未找到有效的控制顶点，返回默认值 50")
            return 50.0

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 清除实例引用
        CurveScaleTool._instance = None
        event.accept()


def run_curve_scale_tool():
    """运行曲线大小调整工具"""
    try:
        # 获取窗口实例
        window = CurveScaleTool.get_instance()
        window.show()
        window.raise_()
        window.activateWindow()
        return window
    except Exception as e:
        print(u"运行曲线大小调整工具时出错: {}".format(str(e)))
        print(u"请确保在Maya环境中运行此工具")
        return None


if __name__ == "__main__":
    try:
        run_curve_scale_tool()
    except ImportError:
        print("=" * 50)
        print(u"错误: 此工具需要在Maya环境中运行")
        print(u"请使用Maya的script editor或通过Maya的Python解释器运行此脚本")
        print("=" * 50)
    except Exception as e:
        print(u"工具启动失败: {}".format(str(e)))
        print(u"请确保在Maya环境中运行此工具")