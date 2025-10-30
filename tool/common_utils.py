# -*- coding: utf-8 -*-
import os
import sys
import importlib
import importlib.util
from maya import cmds

def reload_module(module_name, module_path=None):
    """
    通用模块重载函数，用于导入或重载指定的模块
    
    参数:
        module_name (str): 要导入或重载的模块名称
        module_path (str, 可选): 模块文件的完整路径，如果提供则使用spec_from_file_location方式导入
        
    返回:
        module: 导入或重载后的模块对象
        
    异常:
        Exception: 导入或重载过程中发生的任何异常
    """
    try:
        if module_path and os.path.exists(module_path):
            # 如果提供了文件路径，使用spec_from_file_location方式导入
            if module_name in sys.modules:
                # 如果模块已存在，重载它
                importlib.reload(sys.modules[module_name])
            else:
                # 如果模块不存在，使用spec导入
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
        else:
            # 使用常规方式导入/重载
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        
        # 返回导入或重载后的模块
        return sys.modules[module_name]
    except Exception as e:
        cmds.warning(f"加载模块 {module_name} 失败: {str(e)}")
        print(f"错误详情: {str(e)}")
        raise