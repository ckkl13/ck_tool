# -*- coding: utf-8 -*-
"""
Maya控制器层级创建工具
为选中的控制器创建zero、driven、connect、offset层级结构

使用方法:
1. 在Maya中选择一个或多个控制器
2. 运行此脚本或调用add_controller_hierarchy()函数
3. 脚本会自动为每个控制器创建层级结构

作者: CK Tool
"""

import maya.cmds as cmds
from functools import wraps


def with_undo_support(func):
    """
    装饰器：为函数添加撤销支持
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            cmds.undoInfo(openChunk=True)
            result = func(*args, **kwargs)
            print(f"'{func.__name__}' 操作完成。按 Ctrl+Z 可撤销此操作。")
            return result
        except Exception as e:
            print(f"'{func.__name__}' 操作出错: {e}")
            raise
        finally:
            cmds.undoInfo(closeChunk=True)
    return wrapper


@with_undo_support
def add_controller_hierarchy():
    """
    为选中的控制器创建层级结构
    
    层级结构从上到下为：
    zero -> driven -> connect -> offset -> controller
    
    功能说明：
    - zero: 零位节点，用于重置控制器位置
    - driven: 驱动节点，用于被其他控制器驱动
    - connect: 连接节点，用于连接约束
    - offset: 偏移节点，用于局部偏移调整
    """
    controllers = cmds.ls(selection=True)
    if not controllers:
        cmds.warning("请至少选择一个控制器！")
        return

    for ctrl in controllers:
        # 创建层级节点
        zero = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'zero_'))
        driven = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'driven_'), parent=zero)
        connect = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'connect_'), parent=driven)
        offset = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'offset_'), parent=connect)

        # 匹配控制器的变换到zero节点
        cmds.matchTransform(zero, ctrl, position=True, rotation=True)
        
        # 将控制器父级到offset节点下
        cmds.parent(ctrl, offset)
        
        print(f"控制器 '{ctrl}' 的层级已创建。")


if __name__ == "__main__":
    # 检查是否在Maya环境中
    try:
        import maya.cmds as cmds
        # 直接执行函数
        add_controller_hierarchy()
    except ImportError:
        print("请在Maya环境中运行此脚本")