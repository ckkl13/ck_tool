# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel
import pymel.core as pm
from functools import partial

class GradientColorTool:
    def __init__(self):
        self.window_name = 'gradientColorWindow'
        self.ramp_name = 'TEMPNODE_remapValue'
        
    def create_ui(self):
        """创建UI界面"""
        # 如果窗口已存在，删除它
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)
            
        # 创建窗口
        window = cmds.window(self.window_name, 
                           title='🎨 渐变颜色工具', 
                           widthHeight=(320, 260),
                           resizeToFitChildren=True,
                           backgroundColor=(0.25, 0.25, 0.25))
        
        # 主布局
        main_layout = cmds.columnLayout(adjustableColumn=True, 
                                      columnAttach=('both', 10),
                                      rowSpacing=8,
                                      columnWidth=300)
        
        # 顶部装饰条
        cmds.rowLayout(numberOfColumns=3, 
                      columnWidth3=(100, 100, 100),
                      height=4)
        cmds.text(label='', backgroundColor=(0.9, 0.3, 0.3))
        cmds.text(label='', backgroundColor=(0.3, 0.9, 0.3))
        cmds.text(label='', backgroundColor=(0.3, 0.3, 0.9))
        cmds.setParent('..')
        
        # 标题区域
        title_frame = cmds.frameLayout(label='', 
                                     backgroundColor=(0.3, 0.3, 0.35),
                                     marginWidth=5,
                                     marginHeight=5)
        
        cmds.text(label='🎨 渐变颜色工具', 
                  height=25,
                  backgroundColor=(0.3, 0.3, 0.35),
                  align='center')
        
        cmds.text(label='为选中的物体应用美丽的渐变色彩效果', 
                  align='center',
                  height=15,
                  backgroundColor=(0.3, 0.3, 0.35))
        
        cmds.setParent('..')
        
        # 功能按钮区域
        button_frame = cmds.frameLayout(label='操作面板', 
                                      collapsable=False,
                                      backgroundColor=(0.28, 0.28, 0.32),
                                      marginWidth=8,
                                      marginHeight=8)
        
        # 颜色目标选择
        cmds.rowLayout(numberOfColumns=2, 
                      columnWidth2=(100, 170),
                      columnAttach=[(1, 'both', 5), (2, 'both', 5)],
                      height=25)
        
        cmds.text(label='颜色目标:', align='left')
        self.color_target_menu = cmds.optionMenu(label='', 
                                               backgroundColor=(0.35, 0.35, 0.4))
        cmds.menuItem(label='Shape节点 (形状)')
        cmds.menuItem(label='Transform节点 (变换)')
        
        cmds.setParent('..')
        
        # 第一行按钮
        cmds.rowLayout(numberOfColumns=2, 
                      columnWidth2=(135, 135),
                      columnAttach=[(1, 'both', 5), (2, 'both', 5)],
                      height=32)
        
        # 编辑渐变按钮
        cmds.button(label='🎨 编辑渐变',
                    command=self.open_ramp_editor,
                    backgroundColor=(0.2, 0.5, 0.8),
                    height=30)
         
         # 应用渐变按钮
        cmds.button(label='✨ 应用渐变',
                    command=self.apply_gradient_color,
                    backgroundColor=(0.5, 0.7, 0.2),
                    height=30)
        
        cmds.setParent('..')
        
        # 第二行按钮
        cmds.rowLayout(numberOfColumns=1, 
                      columnWidth1=270,
                      columnAttach=[(1, 'both', 5)],
                      height=32)
        
        # 重置按钮
        cmds.button(label='🔄 重置颜色', 
                    command=self.reset_colors,
                    backgroundColor=(0.7, 0.3, 0.3),
                    height=30)
        
        cmds.setParent('..')
        cmds.setParent('..') 
        
        # 状态显示区域
        status_frame = cmds.frameLayout(label='状态信息', 
                                      collapsable=False,
                                      backgroundColor=(0.26, 0.26, 0.3),
                                      marginWidth=8,
                                      marginHeight=5)
        
        self.status_text = cmds.text(label='🟢 准备就绪 - 请选择物体后开始操作', 
                                    align='center',
                                    height=18,
                                    backgroundColor=(0.15, 0.15, 0.2))
        
        cmds.setParent('..')
        
        # 底部装饰条
        cmds.rowLayout(numberOfColumns=5, 
                      columnWidth5=(60, 60, 60, 60, 60),
                      height=3)
        cmds.text(label='', backgroundColor=(0.9, 0.6, 0.2))
        cmds.text(label='', backgroundColor=(0.9, 0.3, 0.6))
        cmds.text(label='', backgroundColor=(0.3, 0.9, 0.9))
        cmds.text(label='', backgroundColor=(0.6, 0.3, 0.9))
        cmds.text(label='', backgroundColor=(0.9, 0.9, 0.3))
        cmds.setParent('..')
        
        # 显示窗口
        cmds.showWindow(window)
        
    def create_ramp_node(self):
        """创建或获取渐变节点"""
        if not cmds.objExists(self.ramp_name):
            cmds.createNode('remapValue', n=self.ramp_name)
            # 设置默认渐变（从红到蓝）
            cmds.setAttr(f'{self.ramp_name}.color[0].color_Position', 0.0)
            cmds.setAttr(f'{self.ramp_name}.color[0].color_FloatValue', 1.0, 0.0, 0.0, type='double3')
            cmds.setAttr(f'{self.ramp_name}.color[1].color_Position', 1.0)
            cmds.setAttr(f'{self.ramp_name}.color[1].color_FloatValue', 0.0, 0.0, 1.0, type='double3')
        return self.ramp_name
        
    def open_ramp_editor(self, *args):
        """打开渐变编辑器"""
        try:
            self.create_ramp_node()
            pm.mel.editRampAttribute(f'{self.ramp_name}.color')
            self.update_status('渐变编辑器已打开，请设置您喜欢的颜色', 'success')
        except Exception as e:
            self.update_status(f'打开编辑器失败: {str(e)}', 'error')
            
    def apply_gradient_color(self, *args):
        """应用渐变颜色到选中的物体"""
        try:
            # 获取选中的物体
            sel = cmds.ls(sl=True)
            if not sel:
                self.update_status('请先选择物体再进行操作', 'warning')
                return
                
            sel_size = len(sel)
            if sel_size < 2:
                self.update_status('请选择至少2个物体以获得渐变效果', 'warning')
                return
                
            # 确保渐变节点存在
            self.create_ramp_node()
            
            # 为每个物体应用渐变颜色
            for i, obj in enumerate(sel):
                # 计算参数值（0到1之间）
                if sel_size == 1:
                    par_value = 0.5
                else:
                    par_value = i / (sel_size - 1.0)
                
                # 设置输入值并获取输出颜色
                cmds.setAttr(f'{self.ramp_name}.inputValue', par_value)
                rgb_value = cmds.getAttr(f'{self.ramp_name}.outColor')[0]
                
                # 应用颜色到物体
                self.set_object_color(obj, rgb_value)
                
            self.update_status(f'太棒了！成功为 {sel_size} 个物体应用了渐变颜色', 'success')
            
        except Exception as e:
            self.update_status(f'应用颜色失败: {str(e)}', 'error')
            
    def set_object_color(self, obj, rgb_color):
        """设置物体颜色"""
        try:
            # 获取颜色目标类型
            target_type = cmds.optionMenu(self.color_target_menu, query=True, value=True)
            
            if 'Shape' in target_type:
                # 对Shape节点设置颜色
                shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
                if not shapes:
                    return
                    
                for shape in shapes:
                    # 启用颜色覆盖
                    cmds.setAttr(f'{shape}.overrideEnabled', True)
                    cmds.setAttr(f'{shape}.overrideRGBColors', True)
                    
                    # 设置RGB颜色
                    cmds.setAttr(f'{shape}.overrideColorRGB', 
                               rgb_color[0], rgb_color[1], rgb_color[2], 
                               type='double3')
            else:
                # 对Transform节点设置颜色
                # 启用颜色覆盖
                cmds.setAttr(f'{obj}.overrideEnabled', True)
                cmds.setAttr(f'{obj}.overrideRGBColors', True)
                
                # 设置RGB颜色
                cmds.setAttr(f'{obj}.overrideColorRGB', 
                           rgb_color[0], rgb_color[1], rgb_color[2], 
                           type='double3')
                           
        except Exception as e:
            print(f'设置物体 {obj} 颜色失败: {str(e)}')
            
    def reset_colors(self, *args):
        """重置选中物体的颜色"""
        try:
            sel = cmds.ls(sl=True)
            if not sel:
                self.update_status('请先选择要重置的物体', 'warning')
                return
            
            # 获取颜色目标类型
            target_type = cmds.optionMenu(self.color_target_menu, query=True, value=True)
                
            for obj in sel:
                if 'Shape' in target_type:
                    # 重置Shape节点颜色
                    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
                    if shapes:
                        for shape in shapes:
                            cmds.setAttr(f'{shape}.overrideEnabled', False)
                else:
                    # 重置Transform节点颜色
                    cmds.setAttr(f'{obj}.overrideEnabled', False)
                        
            self.update_status(f'已成功重置 {len(sel)} 个物体的颜色', 'success')
            
        except Exception as e:
            self.update_status(f'重置颜色失败: {str(e)}', 'error')
            
    def update_status(self, message, status_type='info'):
        """更新状态文字"""
        # 根据状态类型添加不同的图标和颜色
        status_icons = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': '🔵',
            'ready': '🟢'
        }
        
        status_colors = {
            'success': (0.1, 0.3, 0.1),
            'error': (0.3, 0.1, 0.1),
            'warning': (0.3, 0.25, 0.1),
            'info': (0.1, 0.1, 0.3),
            'ready': (0.15, 0.15, 0.2)
        }
        
        icon = status_icons.get(status_type, '🔵')
        color = status_colors.get(status_type, (0.15, 0.15, 0.2))
        formatted_message = f'{icon} {message}'
        
        if cmds.text(self.status_text, exists=True):
            cmds.text(self.status_text, edit=True, 
                     label=formatted_message,
                     backgroundColor=color)
        print(message)

# 全局函数，用于启动工具
def show_gradient_color_tool():
    """显示渐变颜色工具"""
    tool = GradientColorTool()
    tool.create_ui()
    return tool

# 如果直接运行此脚本
if __name__ == '__main__':
    show_gradient_color_tool()
