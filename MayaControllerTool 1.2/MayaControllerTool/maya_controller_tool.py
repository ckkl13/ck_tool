#coding=utf-8
import maya.cmds as cmds
import maya.mel as mel

import os
import io
import shutil
from functools import partial
import datetime
import logging
import sys

# Qt imports (PySide2 preferred)
try:
    from PySide2.QtWidgets import (QDialog, QApplication, QListWidget, QListWidgetItem, QVBoxLayout,
                                   QHBoxLayout, QPushButton, QWidget, QLabel, QCheckBox, QSizePolicy, QMenu)
    from PySide2.QtGui import QIcon, QPixmap, QColor
    from PySide2.QtCore import QSize, Qt, QFileSystemWatcher, QTimer
except ImportError:
    try:
        from PySide.QtGui import QDialog, QApplication, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLabel, QIcon, QPixmap, QColor, QMenu
        from PySide.QtCore import QSize, Qt, QFileSystemWatcher, QTimer
        from PySide.QtGui import QSizePolicy
    except Exception:
        QDialog = None
        QApplication = None
        QListWidget = None
        QListWidgetItem = None
        QVBoxLayout = None
        HBoxLayout = None
        QPushButton = None
        QWidget = None
        QLabel = None
        QCheckBox = None
        QIcon = None
        QPixmap = None
        QColor = None
        QSize = None
        Qt = None
        QFileSystemWatcher = None
        QTimer = None

def get_app():
    try:
        top = QApplication.activeWindow()
        if top is None:
            return None
        while True:
            parent = top.parent()
            if parent is None:
                return top
            top = parent
    except Exception:
        return None

# Logging Setup
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Python 2/3 统一的安全 Unicode 转换
def _to_unicode_safe(obj):
    """将任意对象安全转换为 unicode（Py2）或 str（Py3）。
    在 Py2 中避免默认 ascii 解码导致的异常。
    """
    try:
        # Py2: 存在 unicode 类型
        unicode  # noqa: F821
        fsenc = sys.getfilesystemencoding() or 'utf-8'
        try:
            if isinstance(obj, unicode):  # noqa: F821
                return obj
            # 先尝试直接以文件系统编码解码
            return unicode(obj, fsenc, 'ignore')  # noqa: F821
        except Exception:
            try:
                # 退化为将 str(obj) 再解码
                return unicode(str(obj), fsenc, 'ignore')  # noqa: F821
            except Exception:
                return u''
    except NameError:
        # Py3: 直接转换为字符串
        try:
            return str(obj)
        except Exception:
            return ''

# Windows 下获取短路径（8.3 格式），用以避免非 ASCII 路径导致的内部解码问题
def _win_short_path(path):
    try:
        if os.name != 'nt':
            return path
        import ctypes
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        buf_len = 260
        buf = ctypes.create_unicode_buffer(buf_len)
        res = GetShortPathNameW(path, buf, buf_len)
        if res > 0:
            return buf.value or path
        return path
    except Exception:
        return path

# Constants
CURVE_TYPE_NURBS = "nurbsCurve"
CURVE_TYPE_BEZIER = "bezierCurve"
CURVE_TYPES = [CURVE_TYPE_NURBS, CURVE_TYPE_BEZIER]

class MayaControllerTool():
    Icon_PNG = 'background.png'
    BackGroundColor=[
        (0.47,0.47,0.47),
        (0,0,0), 
        (0.5,0.5,0.5),
        (0.75,0.75,0.75),
        (0.8,0,0.2),
        (0,0,0.4),
        (0,0,1),
        (0,0.3,0),
        (0.2,0,0.3),
        (0.8,0,0.8),
        (0.6,0.3,0.2),                                                                     
        (0.25,0.13,0.13),
        (0.7,0.2,0),
        (1,0,0),
        (0,1,0),
        (0,0.3,0.6),
        (1,1,1),
        (1,1,0),
        (0,1,1),
        (0,1,0.8),
        (1,0.7,0.7),
        (0.9,0.7,0.5),
        (1,1,0.4),
        (0,0.7,0.4),
        (0.6,0.4,0.2),
        (0.63,0.63,0.17),
        (0.4,0.6,0.2),
        (0.2,0.63,0.35),
        (0.18,0.63,0.63),
        (0.18,0.4,0.63),
        (0.43,0.18,0.63),
        (0.63,0.18,0.4)
        ] 

    def __init__(self):
        # 统一为 unicode 路径，避免 Py2 下中文路径触发 ascii 解码错误
        try:
            unicode  # noqa: F821
            fsenc = sys.getfilesystemencoding() or 'utf-8'
            _file_u = __file__ if isinstance(__file__, unicode) else unicode(__file__, fsenc, 'ignore')  # noqa: F821
            self.script_dir = os.path.split(os.path.abspath(_file_u))[0]
        except NameError:
            # Py3
            self.script_dir = os.path.split(os.path.abspath(__file__))[0]
        self.current_dir = os.path.join(self.script_dir,'Lib') 
        self.icon_file = os.path.join(self.current_dir,'icon-bg.png') 
        self.qt_window = None
        self.ifFlip_checkBox_widget = None
        # 优先使用 Qt 界面
        try:
            self.show_qt_ui()
        except Exception as e:
            try:
                logger.warning("Qt UI 启动失败，将回退到 cmds UI。Issue: {}".format(str(e)))
            except Exception:
                pass
            self.mainUI()

    def get_next_shape_name(self):
        """根据 Lib 目录现有 shape 序号，返回下一个可用的形状基础名，如 'shape60'。"""
        import re
        max_num = 0
        try:
            for fn in os.listdir(self.current_dir):
                m = re.match(r'^shape(\d+)\.(png|py|mel)$', fn, re.IGNORECASE)
                if m:
                    try:
                        num = int(m.group(1))
                        if num > max_num:
                            max_num = num
                    except Exception:
                        pass
        except Exception as e:
            try:
                logger.warning("读取目录以确定下一个形状序号失败: {}".format(e))
            except Exception:
                pass
        return "shape{}".format(max_num + 1)

    def show_qt_ui(self):
        if QDialog is None:
            raise RuntimeError('Qt 不可用')
        if self.qt_window is None:
            self.qt_window = ControllerToolWindow(self)
        self.qt_window.show()

    def mainUI(self):
        Window='Control_Window'
        try:
            cmds.deleteUI(Window) 
        except:
            pass
        
        # 创建主窗口，设置合理的初始大小
        cmds.window(Window, title='Maya Controller Tool 1.2', menuBar=True, sizeable=True, 
                   widthHeight=(400, 350), minimizeButton=True, maximizeButton=True) 

        # 定义菜单（仅保留打开脚本文件夹）
        cmds.menu(label="工具", tearOff=False) 
        cmds.menuItem(label=u'打开脚本文件夹', command='os.startfile("%s")'%self.current_dir) 

        # 创建主布局
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=2, parent=Window)
        
        # 创建可滚动的控制器图标区域
        NOC = 8  # 每行图标数量
        scrollLayout = cmds.scrollLayout(childResizable=True, height=520, 
                                        backgroundColor=(0.3, 0.3, 0.3), parent=main_layout)
        GridLayout = cmds.gridLayout(cellWidthHeight=(48, 48), numberOfColumns=NOC, 
                                   parent=scrollLayout) 
        
        # 加载控制器脚本
        listMel = self.findAllSuffix(self.current_dir, '.mel') 
        listPy = self.findAllSuffix(self.current_dir, '.py') 
        listScripts = listMel + listPy
        size = len(listScripts) 
        
        # 创建图标按钮
        for i in range(size): 
            cmds.iconTextButton(style="iconAndTextCentered", image1=self.icon_file, label='') 

        # 编辑控制器图标
        listButton = cmds.gridLayout(GridLayout, q=True, childArray=True) 
        f = 0
        b = -1
        for i in range(size): 
            script_file = listScripts[i] 
            base_name, file_extension = os.path.splitext(script_file) 
            icon_file = '%s.png' % base_name 

            if os.path.isfile(script_file):
                if os.path.isfile(icon_file):
                    cmds.iconTextButton(listButton[f], e=True, style="iconAndTextCentered",
                                      image=icon_file, command=partial(self.MakeController, script_file)) 
                    f = f + 1
                elif not os.path.isfile(icon_file):
                    script_file_name = os.path.basename(script_file) 
                    icon_label = os.path.splitext(script_file_name)[0] 
                    icon_file = self.current_dir + '\\' + self.Icon_PNG
                    cmds.iconTextButton(listButton[b], e=True, style="iconAndTextCentered",
                                      image=icon_file, label=icon_label, 
                                      command=partial(self.MakeController, script_file)) 
                    b = b - 1
        
        # 补全控制器图标满一行 
        size = (NOC - size % NOC) % NOC 
        if size: 
            for i in range(size): 
                cmds.iconTextButton(style="textOnly", enable=False) 
        
        cmds.setParent(main_layout)
        
        # 颜色选择器区域
        cmds.separator(height=3, style='in')
        
        # 创建颜色网格
        color_columns = 10
        color_grid = cmds.gridLayout(cellWidthHeight=(24, 20), numberOfColumns=color_columns, 
                                   parent=main_layout)
        
        # 创建颜色按钮
        for i, RGB in enumerate(self.BackGroundColor): 
            cmds.iconTextButton(style="textOnly", backgroundColor=RGB, width=24, height=20,
                              command=partial(self.SetShapeColor, i)) 
        
        cmds.setParent(main_layout)
        
        # 工具按钮区域
        cmds.separator(height=3, style='in')
        curve_layout = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 180), (2, 180)], 
                                          columnSpacing=[(1, 10), (2, 10)], parent=main_layout)
        cmds.button(label="替换曲线", height=22, backgroundColor=(0.5, 0.6, 0.7),
                   command=lambda *args: self.TransCurveShape()) 
        cmds.button(label="镜像曲线", height=22, backgroundColor=(0.5, 0.6, 0.7),
                   command=lambda *args: self.MirrorCurveShape()) 
        
        cmds.setParent(main_layout)
        cmds.separator(height=1, style='none')
        
        # 面板控制器区域
        panel_layout = cmds.rowColumnLayout(numberOfColumns=1, columnWidth=[(1, 380)], 
                                          columnSpacing=[(1, 10)], parent=main_layout)
        cmds.button(label="关联控制器到面板形状", height=22, backgroundColor=(0.7, 0.5, 0.6),
                   command=lambda *args: self.curve_picker()) 
        
        cmds.setParent(main_layout)
        cmds.separator(height=1, style='none')
        ctrl_layout = cmds.rowColumnLayout(numberOfColumns=1, columnWidth=[(1, 380)], 
                                         parent=main_layout)
        cmds.button(label="截屏控制器", height=22, backgroundColor=(0.6, 0.7, 0.5),
                   command=lambda *args: self.screenshotController()) 
        
        # 显示窗口
        cmds.showWindow(Window) 

    def is_flip_enabled(self):
        """统一读取 Flip 状态（优先 Qt 复选框，其次 cmds 菜单/复选框）"""
        try:
            if self.ifFlip_checkBox_widget is not None:
                return bool(self.ifFlip_checkBox_widget.isChecked())
        except Exception:
            pass
        try:
            if hasattr(self, 'ifFlip_checkBox'):
                return bool(cmds.menuItem(self.ifFlip_checkBox, q=True, checkBox=True))
        except Exception:
            pass
        return False

    def aboutWin(self):
        try:
            cmds.deleteUI('win_abt')
        except:
            pass
        title = "About"
        aboutText = (
                     "- Script By Pan He" +"\n"
                    +"\n"
                    +"- E-Mail:649564644@qq.com" +"\n"
                    ) 

        cmds.window('win_abt', t=title, rtf=0) 
        cmds.columnLayout(adj=True) 
        cmds.scrollField('aboutScroll', ed=0, text=aboutText, bgc=(0.7,0.7,0.7), ww=0) 
        cmds.showWindow('win_abt') 
        # 允许窗口自由缩放，不固定大小
        cmds.window('win_abt', e=True, sizeable=1) 

    def aboutWinQt(self):
        if QDialog is None:
            return self.aboutWin()
        try:
            dlg = QDialog(get_app())
            dlg.setWindowTitle("About")
            layout = QVBoxLayout(dlg)
            label = QLabel("- Script By Pan He\n\n- E-Mail:649564644@qq.com")
            layout.addWidget(label)
            btn = QPushButton("OK")
            btn.clicked.connect(dlg.accept)
            layout.addWidget(btn)
            dlg.setLayout(layout)
            # 允许自由缩放
            dlg.setSizeGripEnabled(True)
            dlg.exec_()
        except Exception as e:
            try:
                logger.warning("Qt About 弹窗失败: {}".format(str(e)))
            except Exception:
                pass


    def freeze_channels(self, obj_list):
        """
        Freezes transforms on a list of objects
        """
        if not obj_list:
            return
        try:
            for obj in obj_list:
                if cmds.objExists(obj):
                    cmds.makeIdentity(obj, apply=True, rotate=True, scale=True, translate=True)
        except Exception as e:
            try:
                logger.warning("Failed to freeze transforms. Issue: {}".format(str(e)))
            except Exception:
                pass

    def combine_curves_list(self, curve_list, convert_bezier_to_nurbs=True):
        """
        Moves the shape objects of all elements in the provided input (curve_list) to a single group
        (essentially combining them under one transform)

        Args:
            curve_list (list): A list of strings with the name of the curves to be combined.
            convert_bezier_to_nurbs (bool, optional): If active, "bezier" curves will automatically be converted to "nurbs".
        Returns:
            str: Name of the generated curve when combining or name of the first curve in the list when only one found.
        """
        function_name = "Combine Curves List"
        try:
            cmds.undoInfo(openChunk=True, chunkName=function_name)
            nurbs_shapes = []
            bezier_shapes = []
            valid_curve_transforms = set()

            for crv in curve_list:
                shapes = cmds.listRelatives(crv, shapes=True, fullPath=True) or []
                for shape in shapes:
                    if cmds.objectType(shape) == CURVE_TYPE_BEZIER:
                        bezier_shapes.append(shape)
                        valid_curve_transforms.add(crv)
                    if cmds.objectType(shape) == CURVE_TYPE_NURBS:
                        nurbs_shapes.append(shape)
                        valid_curve_transforms.add(crv)

            if not nurbs_shapes and not bezier_shapes:  # No valid shapes
                logger.warning("Unable to combine curves. No valid shapes were found under the provided objects.")
                return

            if len(curve_list) == 1:  # Only one curve in provided list
                return curve_list[0]

            if len(bezier_shapes) > 0 and convert_bezier_to_nurbs:
                for bezier in bezier_shapes:
                    logger.debug(str(bezier))
                    cmds.select(bezier)
                    cmds.bezierCurveToNurbs()

            self.freeze_channels(list(valid_curve_transforms))
            # Re-parent Shapes
            shapes = nurbs_shapes + bezier_shapes
            group = cmds.group(empty=True, world=True, name=curve_list[0])
            cmds.refresh()  # Without a refresh, Maya ignores the freeze operation
            for shape in shapes:
                cmds.select(clear=True)
                cmds.parent(shape, group, relative=True, shape=True)
            # Delete empty transforms
            for transform in valid_curve_transforms:
                children = cmds.listRelatives(transform, children=True) or []
                if not children and cmds.objExists(transform):
                    cmds.delete(transform)
            # Clean-up
            combined_curve = cmds.rename(group, curve_list[0])
            if cmds.objExists(combined_curve):
                cmds.select(combined_curve)
            return combined_curve
        except Exception as exception:
            try:
                logger.warning("An error occurred when combining the curves. Issue: {}".format(str(exception)))
            except Exception:
                pass
        finally:
            cmds.undoInfo(closeChunk=True, chunkName=function_name)

    def check_and_combine_controller_shapes(self, ctrl_name):
        """
        检查控制器是否有多个形状，如果有则合并它们
        """
        if not ctrl_name or not cmds.objExists(ctrl_name):
            return ctrl_name
            
        # 获取控制器的所有形状节点
        shapes = cmds.listRelatives(ctrl_name, shapes=True, fullPath=True) or []
        curve_shapes = []
        
        # 筛选出曲线形状
        for shape in shapes:
            if cmds.objectType(shape) in [CURVE_TYPE_NURBS, CURVE_TYPE_BEZIER]:
                curve_shapes.append(shape)
        
        # 如果有多个曲线形状，则需要合并
        if len(curve_shapes) > 1:
            # 获取所有包含曲线形状的变换节点
            transform_nodes = []
            for shape in curve_shapes:
                transform = cmds.listRelatives(shape, parent=True, fullPath=True)
                if transform and transform[0] not in transform_nodes:
                    transform_nodes.append(transform[0])
            
            if len(transform_nodes) > 1:
                # 如果有多个变换节点，使用合并函数
                combined_ctrl = self.combine_curves_list(transform_nodes)
                print(u"控制器形状已合并: {}".format(combined_ctrl))
                return combined_ctrl
            else:
                # 如果只有一个变换节点但有多个形状，说明形状已经在同一个变换下
                print(u"控制器 {} 的多个形状已在同一变换节点下".format(ctrl_name))
                return ctrl_name
        
        return ctrl_name

    def MakeController(self,*ScriptFile):
        Selected = cmds.ls(sl=True,allPaths=True) 
        script_file = ScriptFile[0] 
        base_name, file_extension = os.path.splitext(script_file)
        
        # 记录执行前的所有曲线对象
        existing_curves = cmds.ls(type=['nurbsCurve', 'bezierCurve'], long=True) or []
        existing_transforms = set()
        for curve in existing_curves:
            transform = cmds.listRelatives(curve, parent=True, fullPath=True)
            if transform:
                existing_transforms.add(transform[0])
        
        Ctrl = None
        
        if file_extension.lower() == '.mel':
            # 执行MEL脚本
            with open(script_file,'r') as f:
                STR = f.read() 
            Ctrl = mel.eval(STR) 
        elif file_extension.lower() == '.py':
            # 执行Python脚本
            try:
                # 读取Python文件内容（兼容 Py2/3）
                is_py2 = False
                try:
                    unicode  # noqa: F821
                    is_py2 = True
                except NameError:
                    is_py2 = False

                if is_py2:
                    # 在 Py2 中以二进制方式读取字节串，避免“Unicode 字符串中的编码声明”错误
                    with open(script_file, 'rb') as f:
                        script_content = f.read()
                else:
                    # 在 Py3 中以 UTF-8 文本方式读取
                    with io.open(script_file, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                
                # 创建一个局部命名空间来执行脚本
                local_namespace = {'cmds': cmds, 'mel': mel, 'os': os}
                
                # 执行Python脚本
                exec(script_content, globals(), local_namespace)
                
                # 尝试获取返回的控制器对象
                # 假设Python脚本返回控制器名称或者选中了创建的控制器
                current_selection = cmds.ls(sl=True)
                if current_selection:
                    Ctrl = current_selection[0]
                    
            except Exception as e:
                cmds.warning(u'执行Python脚本时出错: %s' % str(e))
                return
        else:
            cmds.warning(u'不支持的文件类型: %s' % file_extension)
            return
        
        # 检查脚本执行后新生成的曲线对象
        new_curves = cmds.ls(type=['nurbsCurve', 'bezierCurve'], long=True) or []
        new_transforms = set()
        for curve in new_curves:
            transform = cmds.listRelatives(curve, parent=True, fullPath=True)
            if transform and transform[0] not in existing_transforms:
                new_transforms.add(transform[0])
        
        # 如果生成了多个新的曲线变换节点，合并它们
        if len(new_transforms) > 1:
            new_transform_list = list(new_transforms)
            print(u"检测到 {} 个新生成的曲线对象，正在合并...".format(len(new_transform_list)))
            Ctrl = self.combine_curves_list(new_transform_list)
            print(u"曲线对象已合并为: {}".format(Ctrl))
        elif len(new_transforms) == 1:
            # 如果只有一个新的变换节点，使用它作为控制器
            Ctrl = list(new_transforms)[0]
        
        # 如果没有检测到新的曲线但有返回值，使用返回值
        if not Ctrl and len(new_transforms) == 0:
            current_selection = cmds.ls(sl=True)
            if current_selection:
                Ctrl = current_selection[0]
            
        if Selected and Ctrl: 
            cmds.matchTransform(Ctrl,Selected[0]) 
        if Ctrl:
            cmds.select(Ctrl,r=True) 


    def findAllSuffix(self, path, suffix): 
        result = [] 
        if not suffix.startswith("."): 
            suffix = "." + suffix
        for root, dirs, files in os.walk(path, topdown=False): 
            #print(root, dirs, files) 
            for file in files: 
                if suffix in file: 
                    file_path = os.path.join(root, file) 
                    result.append(file_path) 

        return result 


    def SetShapeColor(self,*Index): 
        sel = cmds.ls(sl=True) 
        size = len(sel) 
        if size == 0: 
            cmds.warning("No object is selected!") 
            return 
            
        for obj in sel: 
            shapes = cmds.listRelatives(obj,s=True) 
            if shapes == None: 
                shapes = [obj] 
            for s in shapes: 
                cmds.setAttr(s+".overrideEnabled",1) 
                cmds.setAttr(s+".overrideColor",Index[0]) 


    def TransCurveShape(self): 
        try:
            SourceCurve,TargetCurve= cmds.ls(sl=True,allPaths=True) 
        except:
            cmds.warning(u'请选择拷贝形状的两个控制器.') 
            return

        TargetCurve_SN = cmds.ls(TargetCurve,shortNames=True)[0] 

        CopyCurve = cmds.duplicate(SourceCurve)[0] 
        CurveShape = cmds.listRelatives(CopyCurve,s=True) 
        cmds.delete(cmds.listRelatives(TargetCurve,s=True)) 

        for shp in CurveShape:
            shp = cmds.rename(shp, '%sShape#'%TargetCurve_SN) 
            cmds.parent(shp,TargetCurve,r=True,s=True) 

        cmds.delete(CopyCurve) 
        cmds.select(TargetCurve,r=True) 


    def MirrorCurveShape(self):
        try:
            con,con_dist = cmds.ls(sl=True)
        except:
            cmds.warning(u'请选择两根需要镜像的曲线.')
            return
        if not cmds.getAttr( con +'.controlPoints',size=True) == cmds.getAttr( con_dist +'.controlPoints',size=True):
            cmds.warning(u'所选控制器CV点的数量不相同.')
            return
        for i in range(cmds.getAttr( con +'.controlPoints',size=True)):
            P = cmds.pointPosition( con +'.controlPoints[%s]'%i)
            cmds.xform( con_dist +'.controlPoints[%s]'%i,t=(-1*P[0],P[1],P[2]),ws=True)


    # 如果效果不对请检查控制器Pivot与层级状态
    def curve_picker(self, control=None, picker=None):
        sel = cmds.ls(sl=True)
        if control==None and picker==None:
            control,picker = sel

        picker = cmds.rename(picker, 'panel_{}'.format(control)) 
        shape_picker = cmds.listRelatives (picker,shapes=True, fullPath=True)[0] 

        picker_trans = cmds.duplicate(picker)[0] 
        shape_orig = cmds.listRelatives (picker_trans,shapes=True, fullPath=True)[0]
        cmds.setAttr('{}.v'.format(shape_orig),False) 
        
        #
        temp_trans = cmds.duplicate (shape_picker)[0] 
        shape_temp = cmds.listRelatives (temp_trans,shapes=True, fullPath=True)[0] 
        cmds.setAttr("{}.template".format(shape_temp),1) 
        
        cvLen = cmds.getAttr(shape_temp +'.controlPoints',size=True) 
        cvs = cmds.getAttr(shape_temp +".cv[*]") 

        pos = list()
        for i in range(0,cvLen,1):
            pos = cmds.pointPosition("%s.cv[%d]"%(shape_temp,i))
            cmds.xform("%s.cv[%d]"%(shape_temp,i),t=(pos[0],pos[1],pos[2]-0.001),ws=True)

        #revNode = cmds.createNode('reverse')
        #cmds.connectAttr('{}.visibility'.format(shape_picker),'{}.inputX'.format(revNode),f=True) 
        #cmds.connectAttr('{}.outputX'.format(revNode),'{}.visibility'.format(shape_temp),f=True)

        #
        shape_picker = cmds.rename(shape_picker, '%s_picker'%shape_picker) 
        shape_orig = cmds.rename(shape_orig, '%s_picker'%shape_orig) 
        shape_picker,shape_orig = cmds.parent (shape_picker,shape_orig,control,r=True,s=True)
        cmds.parent(picker,picker_trans) 

        Flip = self.is_flip_enabled() 
        if Flip:
            cmds.setAttr('%s.sx'%picker_trans, cmds.getAttr('%s.sx'%picker_trans)*-1) 
            #cmds.setAttr('%s.ry'%picker_trans, cmds.getAttr('%s.ry'%picker_trans)*+180) 
            #cmds.setAttr('%s.sz'%picker_trans, cmds.getAttr('%s.sz'%picker_trans)*-1) 

        #
        transNode = cmds.createNode ('transformGeometry') 
        cmds.setAttr ("{}.invertTransform".format(transNode),1) 
        cmds.connectAttr ('{}.worldSpace[0]'.format(shape_orig),'{}.inputGeometry'.format(transNode),f=True) 
        cmds.connectAttr ('{}.matrix'.format(picker),'{}.transform'.format(transNode),f=True) 
        cmds.connectAttr ('{}.outputGeometry'.format(transNode),'{}.create'.format(shape_picker),f=True) 

        cmds.parentConstraint(control,picker,mo=0,w=1) 
        cmds.scaleConstraint (control,picker,offset=[1,1,1],w=1) 

    def get_python_curve_code(self, crv_list):
        """
        从曲线生成Python代码
        
        Args:
            crv_list (list): 曲线对象列表
            
        Returns:
            str: 创建曲线的Python代码
        """
        result = u""
        
        for crv in crv_list:
            if not cmds.objectType(crv, isType='transform') and not cmds.objectType(crv, isType='shape'):
                continue
                
            shapes = []
            if cmds.objectType(crv, isType='transform'):
                shapes = cmds.listRelatives(crv, shapes=True, fullPath=True) or []
            else:
                shapes = [crv]
                
            if not shapes:
                continue
                
            # 获取曲线信息
            for shape in shapes:
                if cmds.objectType(shape, isType='nurbsCurve'):
                    curve_name = cmds.ls(shape, long=False)[0].split('|')[-1]
                    parent = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
                    parent_name = parent.split('|')[-1]
                    
                    # 获取曲线度数和表单
                    curve_degree = cmds.getAttr(shape + '.degree')
                    curve_form = cmds.getAttr(shape + '.form')
                    
                    # 获取控制顶点
                    curve_spans = cmds.getAttr(shape + '.spans')
                    curve_cvs = []
                    for i in range(curve_spans + curve_degree):
                        cv_pos = cmds.getAttr(shape + '.cv[' + str(i) + ']')[0]
                        curve_cvs.extend(cv_pos)
                    
                    points = []
                    # 格式化点坐标
                    for i in range(0, len(curve_cvs), 3):
                        points.append((curve_cvs[i], curve_cvs[i+1], curve_cvs[i+2]))
                    
                    # 添加变量名和曲线创建代码
                    import re
                    var_name = parent_name.replace(':', '_').replace('|', '_')
                    var_name = re.sub(r'[^0-9A-Za-z_]', '_', var_name)
                    if re.match(r'^\d', var_name):
                        var_name = '_' + var_name
                    result += u"# 创建曲线: %s\n" % _to_unicode_safe(parent_name)
                    result += u"points_%s = [\n" % _to_unicode_safe(var_name)
                    
                    for point in points:
                        result += u"    %s,\n" % _to_unicode_safe(str(point))
                    
                    result += u"]\n\n"
                    
                    # 创建曲线
                    if curve_form == 0:  # 开放曲线
                        result += u"%s = cmds.curve(name='', degree=%d, point=points_%s)\n\n" % (_to_unicode_safe(var_name), curve_degree, _to_unicode_safe(var_name))
                    else:  # 闭合曲线
                        result += u"# 创建曲线然后闭合\n"
                        result += u"temp_curve = cmds.curve(degree=%d, point=points_%s)\n" % (curve_degree, _to_unicode_safe(var_name))
                        name_literal = _to_unicode_safe(parent_name).replace("'", "\\'")
                        result += u"%s = cmds.rename(temp_curve, '%s')\n" % (_to_unicode_safe(var_name), name_literal)
                        result += u"# 闭合曲线\n"
                        result += u"cmds.closeCurve(%s, ch=False, ps=True, rpo=True)\n\n" % _to_unicode_safe(var_name)
        
        if not result:
            result = u"# 未找到选中的曲线或选中的对象不包含曲线\n"
        
        return result

    def screenshotController(self):
        """截屏选中的控制器并保存为图片，同时提取曲线代码"""
        sel = cmds.ls(sl=True)
        if not sel:
            cmds.warning(u'请选择一个控制器进行截屏.')
            return
        
        # 获取选中的第一个对象
        controller = sel[0]
        
        # 计算按序递增的默认文件名（基于 Lib 目录现状）
        default_basename = self.get_next_shape_name()
        # 弹出对话框让用户输入文件名（用于图片和曲线代码文件），默认给出按序名称
        result = cmds.promptDialog(
            title=u'保存截图和曲线代码',
            message=u'请输入文件名（将用于图片和曲线代码文件）:',
            button=['OK', 'Cancel'],
            defaultButton='OK',
            cancelButton='Cancel',
            dismissString='Cancel',
            text=default_basename
        )

        if result == 'OK':
            filename = cmds.promptDialog(query=True, text=True)
            if not filename:
                # 若未输入，使用按序递增的默认名
                filename = default_basename
            
            # 确保文件名不包含非法字符
            import re
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            # 构建完整的文件路径
            image_path = os.path.join(self.current_dir, filename + '.png')
            curve_code_path = os.path.join(self.current_dir, filename + '.py')
            # 在 Py2 下确保路径为 unicode，避免后续字符串拼接/打印出现 ascii 解码错误
            try:
                unicode  # noqa: F821
                fsenc = sys.getfilesystemencoding() or 'utf-8'
                if not isinstance(image_path, unicode):  # noqa: F821
                    image_path = unicode(image_path, fsenc, 'ignore')  # noqa: F821
                if not isinstance(curve_code_path, unicode):  # noqa: F821
                    curve_code_path = unicode(curve_code_path, fsenc, 'ignore')  # noqa: F821
            except NameError:
                pass
            
            # 选中控制器并聚焦
            cmds.select(controller, r=True)
            cmds.viewFit()
            
            # 获取当前视图面板
            current_panel = cmds.getPanel(withFocus=True)
            if not cmds.getPanel(typeOf=current_panel) == 'modelPanel':
                # 如果当前面板不是模型面板，获取第一个模型面板
                model_panels = cmds.getPanel(type='modelPanel')
                if model_panels:
                    current_panel = model_panels[0]
                else:
                    cmds.warning(u'找不到可用的3D视图面板.')
                    return
            
            # 启用独显模式
            cmds.isolateSelect(current_panel, state=True)
            cmds.isolateSelect(current_panel, addSelected=True)
            
            # 记录并设置曲线为白色，然后清空选择
            curve_shapes = []
            try:
                shapes = cmds.listRelatives(controller, shapes=True, fullPath=True) or []
                for s in shapes:
                    if cmds.objectType(s) in [CURVE_TYPE_NURBS, CURVE_TYPE_BEZIER]:
                        curve_shapes.append(s)
            except Exception:
                curve_shapes = []

            prev_states = {}
            for shp in curve_shapes:
                try:
                    st = {
                        'overrideEnabled': cmds.getAttr(shp + '.overrideEnabled'),
                        'overrideRGBColors': cmds.getAttr(shp + '.overrideRGBColors')
                    }
                    # 记录原始颜色
                    if st['overrideRGBColors']:
                        try:
                            st['colorRGB'] = cmds.getAttr(shp + '.overrideColorRGB')[0]
                        except Exception:
                            st['colorRGB'] = (0.0, 0.0, 0.0)
                    else:
                        try:
                            st['colorIndex'] = cmds.getAttr(shp + '.overrideColor')
                        except Exception:
                            st['colorIndex'] = 0
                    prev_states[shp] = st
                    # 设置为白色
                    cmds.setAttr(shp + '.overrideEnabled', True)
                    try:
                        cmds.setAttr(shp + '.overrideRGBColors', True)
                        cmds.setAttr(shp + '.overrideColorRGB', 1.0, 1.0, 1.0, type='double3')
                    except Exception:
                        # 旧版兼容：使用索引颜色（16通常为白色）
                        cmds.setAttr(shp + '.overrideRGBColors', False)
                        cmds.setAttr(shp + '.overrideColor', 16)
                except Exception:
                    pass

            # 取消选择，避免截图叠加高亮
            try:
                cmds.select(clear=True)
            except Exception:
                pass

            # 截屏并保存
            try:
                # 对于 Maya Py2，优先传入 Unicode 路径，避免内部尝试用 ascii 解码字节串
                pb_path = _win_short_path(image_path)
                try:
                    cmds.playblast(
                         frame=1,
                         format='image',
                         compression='png',
                         quality=100,
                         widthHeight=[40, 40],
                         percent=100,
                         viewer=False,
                         showOrnaments=False,
                         offScreen=True,
                         completeFilename=pb_path
                     )
                except Exception as pb_err:
                    # 回退到纯 ASCII 的临时目录进行截图，再复制回目标目录
                    try:
                        fallback_dir = u"C:\\MCTemp"
                        if not os.path.isdir(fallback_dir):
                            try:
                                os.makedirs(fallback_dir)
                            except Exception:
                                pass
                        fb_path = os.path.join(fallback_dir, filename + '.png')
                        fb_path_short = _win_short_path(fb_path)
                        cmds.playblast(
                             frame=1,
                             format='image',
                             compression='png',
                             quality=100,
                             widthHeight=[40, 40],
                             percent=100,
                             viewer=False,
                             showOrnaments=False,
                             offScreen=True,
                             completeFilename=fb_path_short
                         )
                        # 尝试把文件移回目标路径
                        try:
                            shutil.copy(fb_path_short, image_path)
                        except Exception:
                            try:
                                # 如果短路径复制失败，尝试用原始路径
                                shutil.copy(fb_path, image_path)
                            except Exception:
                                pass
                    except Exception:
                        # 如果回退也失败，抛出原始错误
                        raise pb_err
                
                # 恢复颜色到原始状态
                for shp, st in prev_states.items():
                    try:
                        cmds.setAttr(shp + '.overrideEnabled', bool(st.get('overrideEnabled', False)))
                        use_rgb = bool(st.get('overrideRGBColors', False))
                        cmds.setAttr(shp + '.overrideRGBColors', use_rgb)
                        if use_rgb:
                            col = st.get('colorRGB')
                            if col is not None:
                                try:
                                    cmds.setAttr(shp + '.overrideColorRGB', col[0], col[1], col[2], type='double3')
                                except Exception:
                                    pass
                        else:
                            if 'colorIndex' in st:
                                try:
                                    cmds.setAttr(shp + '.overrideColor', int(st['colorIndex']))
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # 退出独显模式
                cmds.isolateSelect(current_panel, state=False)
                
                # 提取曲线代码
                curve_code = u"# -*- coding: utf-8 -*-\nfrom __future__ import unicode_literals\n\nimport maya.cmds as cmds\n\n"
                curve_code += self.get_python_curve_code([controller])
                
                # 保存曲线代码到文件
                try:
                    # 写入文件（兼容 Py2/3）
                    try:
                        with io.open(curve_code_path, 'w', encoding='utf-8') as f:
                            f.write(curve_code)
                    except TypeError:
                        with open(curve_code_path, 'w') as f:
                            f.write(curve_code)
                    
                    print(u'截图已保存: %s' % _to_unicode_safe(image_path))
                    print(u'曲线代码已保存: %s' % _to_unicode_safe(curve_code_path))
                    # 自动刷新 Qt 列表
                    try:
                        if self.qt_window is not None:
                            self.qt_window.refresh_shapes()
                    except Exception:
                        pass
                except Exception as e:
                    cmds.warning(u'保存曲线代码失败: %s' % _to_unicode_safe(e))
                    # 即使代码保存失败，图片已保存，尝试自动刷新 Qt 列表
                    try:
                        if self.qt_window is not None:
                            self.qt_window.refresh_shapes()
                    except Exception:
                        pass
                    
            except Exception as e:
                # 确保在异常情况下也退出独显模式
                # 异常同样恢复颜色
                for shp, st in prev_states.items():
                    try:
                        cmds.setAttr(shp + '.overrideEnabled', bool(st.get('overrideEnabled', False)))
                        use_rgb = bool(st.get('overrideRGBColors', False))
                        cmds.setAttr(shp + '.overrideRGBColors', use_rgb)
                        if use_rgb:
                            col = st.get('colorRGB')
                            if col is not None:
                                try:
                                    cmds.setAttr(shp + '.overrideColorRGB', col[0], col[1], col[2], type='double3')
                                except Exception:
                                    pass
                        else:
                            if 'colorIndex' in st:
                                try:
                                    cmds.setAttr(shp + '.overrideColor', int(st['colorIndex']))
                                except Exception:
                                    pass
                    except Exception:
                        pass
                cmds.isolateSelect(current_panel, state=False)
                cmds.warning(u'截图失败: %s' % _to_unicode_safe(e))

    def refreshControllers(self):
        """刷新控制器列表"""
        # 优先刷新 Qt 界面
        if self.qt_window is not None:
            try:
                self.qt_window.refresh_shapes()
                print(u'控制器已刷新')
                return
            except Exception as e:
                try:
                    logger.warning("刷新 Qt 界面失败，回退到 cmds UI。Issue: {}".format(str(e)))
                except Exception:
                    pass
        # 回退刷新 cmds UI
        try:
            cmds.deleteUI('Control_Window')
        except:
            pass
        self.mainUI()
        print(u'控制器已刷新')
    
    def curve_picker(self, control=None, picker=None):
        """关联控制器到面板形状功能"""
        sel = cmds.ls(sl=True)
        if control==None and picker==None:
            if len(sel) < 2:
                cmds.warning(u'请选择两个对象：控制器和面板形状')
                return
            control,picker = sel

        picker = cmds.rename(picker, 'panel_{}'.format(control)) 
        shape_picker = cmds.listRelatives (picker,shapes=True, fullPath=True)[0] 

        picker_trans = cmds.duplicate(picker)[0] 
        shape_orig = cmds.listRelatives (picker_trans,shapes=True, fullPath=True)[0]
        cmds.setAttr('{}.v'.format(shape_orig),False) 
        
        # 创建模板形状
        temp_trans = cmds.duplicate (shape_picker)[0] 
        shape_temp = cmds.listRelatives (temp_trans,shapes=True, fullPath=True)[0] 
        cmds.setAttr("{}.template".format(shape_temp),1) 
        
        cvLen = cmds.getAttr(shape_temp +'.controlPoints',size=True) 
        cvs = cmds.getAttr(shape_temp +".cv[*]") 

        pos = list()
        for i in range(0,cvLen,1):
            pos = cmds.pointPosition("%s.cv[%d]"%(shape_temp,i))
            cmds.xform("%s.cv[%d]"%(shape_temp,i),t=(pos[0],pos[1],pos[2]-0.001),ws=True)

        # 重命名和父子关系设置
        shape_picker = cmds.rename(shape_picker, '%s_picker'%shape_picker) 
        shape_orig = cmds.rename(shape_orig, '%s_picker'%shape_orig) 
        shape_picker,shape_orig = cmds.parent (shape_picker,shape_orig,control,r=True,s=True)
        cmds.parent(picker,picker_trans) 

        # 检查翻转模式
        Flip = self.is_flip_enabled() 
        if Flip:
            cmds.setAttr('%s.sx'%picker_trans, cmds.getAttr('%s.sx'%picker_trans)*-1) 

        # 创建变换几何节点
        transNode = cmds.createNode ('transformGeometry') 
        cmds.setAttr ("{}.invertTransform".format(transNode),1) 
        cmds.connectAttr ('{}.worldSpace[0]'.format(shape_orig),'{}.inputGeometry'.format(transNode),f=True) 
        cmds.connectAttr ('{}.matrix'.format(picker),'{}.transform'.format(transNode),f=True) 
        cmds.connectAttr ('{}.outputGeometry'.format(transNode),'{}.create'.format(shape_picker),f=True) 

        cmds.parentConstraint(control,picker,mo=0,w=1) 
        cmds.scaleConstraint (control,picker,offset=[1,1,1],w=1) 
        
        print(u'控制器 %s 已关联到面板形状' % control)

    def clearPanel(self):
        """删除所有面板形状"""
        listNode = cmds.ls(long=True) 
        sorted_list = sorted(listNode, key=lambda x: len(x), reverse=True)
        
        deleted_count = 0
        for long in sorted_list:
            short_name = long.split("|")[-1] 
            if short_name.startswith('panel_'):
                print (long)
                cmds.delete(long)
                deleted_count += 1
        
        if deleted_count > 0:
            print(u'已删除 %d 个面板形状' % deleted_count)
        else:
            print(u'没有找到面板形状')


class ControllerToolWindow(QDialog):
    def __init__(self, tool):
        super(ControllerToolWindow, self).__init__(get_app())
        self.tool = tool
        self.setWindowTitle('Maya Controller Tool 1.2')
        # 参考 controls.2024.05.17/ui.py 的初始窗口大小
        self.resize(QSize(307, 472))
        # 允许自由缩放
        self.setSizeGripEnabled(True)

        main_layout = QVBoxLayout()

        # 顶部操作区（按钮 + Flip 复选框）
        top_bar = QHBoxLayout()
        btn_open = QPushButton(u'打开脚本文件夹')
        btn_open.clicked.connect(lambda: os.startfile(self.tool.current_dir))
        # 仅保留“打开脚本文件夹”
        for w in (btn_open,):
            top_bar.addWidget(w)
        main_layout.addLayout(top_bar)

        # 控制器图标列表（来自 Lib 下的 .mel/.py 及配套 .png）
        self.shape_list = QListWidget()
        self.shape_list.setViewMode(QListWidget.IconMode)
        self.shape_list.setMovement(QListWidget.Static)
        # 滚动条策略对齐参考实现
        self.shape_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.shape_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 图标尺寸对齐参考实现
        self.shape_list.setIconSize(QSize(64, 64))
        self.shape_list.setResizeMode(QListWidget.Adjust)
        self.shape_list.setSelectionMode(QListWidget.ExtendedSelection)
        # 单击即可运行控制器脚本
        self.shape_list.itemClicked.connect(self._on_item_clicked)
        # 右键菜单：删除对应曲线代码和截图
        try:
            self.shape_list.setContextMenuPolicy(Qt.CustomContextMenu)
            self.shape_list.customContextMenuRequested.connect(self._on_list_context_menu)
        except Exception:
            pass
        main_layout.addWidget(self.shape_list)
        self.refresh_shapes()

        # 颜色列表（缩小图标与高度占用）
        color_list = QListWidget()
        color_list.setViewMode(QListWidget.IconMode)
        color_list.setMovement(QListWidget.Static)
        color_list.setIconSize(QSize(20, 20))
        color_list.setResizeMode(QListWidget.Adjust)
        color_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        color_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        if QSizePolicy is not None:
            color_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # 限制颜色列表最大高度，使曲线图标区域更大
        try:
            color_list.setMaximumHeight(120)
        except Exception:
            pass
        for i, rgb in enumerate(self.tool.BackGroundColor):
            pix = QPixmap(20, 20)
            pix.fill(QColor.fromRgbF(*rgb))
            item = QListWidgetItem(QIcon(pix), "", color_list)
            item.setSizeHint(QSize(22, 22))
        color_list.itemDoubleClicked.connect(lambda x: self.tool.SetShapeColor(self._index_from_item(color_list, x)))
        main_layout.addWidget(color_list)

        # 工具按钮区
        tools_bar1 = QHBoxLayout()
        btn_replace = QPushButton(u"替换曲线")
        btn_replace.clicked.connect(self.tool.TransCurveShape)
        btn_mirror = QPushButton(u"镜像曲线")
        btn_mirror.clicked.connect(self.tool.MirrorCurveShape)
        tools_bar1.addWidget(btn_replace)
        tools_bar1.addWidget(btn_mirror)
        main_layout.addLayout(tools_bar1)

        tools_bar2 = QHBoxLayout()
        btn_link_panel = QPushButton(u"关联控制器到面板形状")
        btn_link_panel.clicked.connect(self.tool.curve_picker)
        tools_bar2.addWidget(btn_link_panel)
        main_layout.addLayout(tools_bar2)

        btn_shot = QPushButton(u"截屏控制器")
        btn_shot.clicked.connect(self.tool.screenshotController)
        main_layout.addWidget(btn_shot)

        # 调整布局伸缩比例：增大曲线图标区域、缩小颜色区域
        try:
            # 0: 顶部工具条, 1: 曲线图标列表, 2: 颜色列表, 3: 工具条1, 4: 工具条2, 5: 截屏按钮
            main_layout.setStretch(0, 0)
            main_layout.setStretch(1, 5)
            main_layout.setStretch(2, 1)
            main_layout.setStretch(3, 0)
            main_layout.setStretch(4, 0)
            main_layout.setStretch(5, 0)
        except Exception:
            pass
        self.setLayout(main_layout)
        # 对齐参考实现：统一按钮最小宽度
        for but in self.findChildren(QPushButton):
            but.setMinimumWidth(20)

        # 自动刷新：目录监控 + 防抖定时器
        try:
            if QTimer is not None:
                self._refresh_timer = QTimer(self)
                self._refresh_timer.setSingleShot(True)
                self._refresh_timer.setInterval(300)
                self._refresh_timer.timeout.connect(self.refresh_shapes)
            else:
                self._refresh_timer = None

            if QFileSystemWatcher is not None:
                self._fs_watcher = QFileSystemWatcher([self.tool.current_dir])
                self._fs_watcher.directoryChanged.connect(self._on_dir_changed)
            else:
                self._fs_watcher = None
        except Exception as e:
            try:
                logger.warning("初始化自动刷新失败: {}".format(e))
            except Exception:
                pass

    def _index_from_item(self, lw, item):
        return lw.indexFromItem(item).row()

    def _on_item_double_clicked(self, item):
        script_file = getattr(item, 'script_file', None)
        if script_file and os.path.isfile(script_file):
            self.tool.MakeController(script_file)

    def _on_item_clicked(self, item):
        # 单击触发运行控制器脚本
        script_file = getattr(item, 'script_file', None)
        if script_file and os.path.isfile(script_file):
            self.tool.MakeController(script_file)

    def _on_dir_changed(self, path):
        # 目录内容变化时触发刷新（定时防抖，避免重复刷新）
        try:
            if getattr(self, '_refresh_timer', None) is not None:
                self._refresh_timer.start()
            else:
                self.refresh_shapes()
        except Exception as e:
            try:
                logger.warning("目录变更刷新失败: {}".format(e))
            except Exception:
                pass

    def _on_list_context_menu(self, pos):
        # 右键菜单触发，定位项
        try:
            item_under_cursor = self.shape_list.itemAt(pos)
            selected_items = list(self.shape_list.selectedItems() or [])
            menu = QMenu(self)
            act_del_selected = None
            act_del_single = None

            if len(selected_items) > 1:
                act_del_selected = menu.addAction(u"删除所选项对应的代码和截图")
            # 如果有光标下的项或只选了一个项，提供单项删除
            if item_under_cursor is not None or len(selected_items) == 1:
                act_del_single = menu.addAction(u"删除对应曲线代码和截图")

            action = menu.exec_(self.shape_list.mapToGlobal(pos))
            if action == act_del_selected and len(selected_items) > 1:
                self._delete_items_files(selected_items)
            elif action == act_del_single:
                target_item = item_under_cursor if item_under_cursor is not None else (selected_items[0] if selected_items else None)
                if target_item is not None:
                    self._delete_item_files(target_item)
        except Exception as e:
            try:
                logger.warning("右键菜单处理失败: {}".format(e))
            except Exception:
                pass

    def _delete_item_files(self, item):
        # 删除选中项的脚本文件和配套截图
        script_file = getattr(item, 'script_file', None)
        if not script_file:
            return
        deleted_any = self._delete_files_for_script(script_file)
        # 刷新列表显示
        try:
            if deleted_any:
                self.refresh_shapes()
            else:
                cmds.warning(u"未找到可删除的文件")
        except Exception:
            pass

    def _delete_items_files(self, items):
        # 批量删除多个选中项的脚本和截图
        total_deleted = 0
        for it in items:
            script_file = getattr(it, 'script_file', None)
            if not script_file:
                continue
            if self._delete_files_for_script(script_file):
                total_deleted += 1
        # 批量完成后统一刷新一次
        try:
            if total_deleted > 0:
                self.refresh_shapes()
                print(u"已删除 {} 项".format(total_deleted))
            else:
                cmds.warning(u"未找到可删除的文件")
        except Exception:
            pass

    def _delete_files_for_script(self, script_file):
        # 删除一个脚本文件及其同名截图，不触发刷新，返回是否有删除
        deleted_any = False
        try:
            if os.path.isfile(script_file):
                os.remove(script_file)
                deleted_any = True
                print(u"已删除代码文件: {}".format(script_file))
        except Exception as e:
            try:
                logger.warning("删除代码文件失败: {}".format(e))
            except Exception:
                pass
        try:
            base_name, _ = os.path.splitext(script_file)
            png_file = u"%s.png" % base_name
            if os.path.isfile(png_file):
                os.remove(png_file)
                deleted_any = True
                print(u"已删除截图文件: {}".format(png_file))
        except Exception as e:
            try:
                logger.warning("删除截图文件失败: {}".format(e))
            except Exception:
                pass
        return deleted_any

    def refresh_shapes(self):
        self.shape_list.clear()
        listMel = self.tool.findAllSuffix(self.tool.current_dir, '.mel')
        listPy = self.tool.findAllSuffix(self.tool.current_dir, '.py')
        listScripts = listMel + listPy
        for script_file in listScripts:
            base_name, file_extension = os.path.splitext(script_file)
            icon_file = '%s.png' % base_name
            icon = QIcon(icon_file) if os.path.isfile(icon_file) else QIcon(self.tool.icon_file)
            # 与参考实现一致：列表不显示文本，仅显示图标
            item = QListWidgetItem(icon, "", self.shape_list)
            item.script_file = script_file
            # 对齐参考实现的尺寸
            item.setSizeHint(QSize(67, 67))












