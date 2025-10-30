# external_reference.py - 外部工具引用模块
# 包含各种外部工具的调用函数

from maya import cmds
import maya.mel as mel
import os
import sys
import importlib
from functools import wraps

# with_undo_support 装饰器定义
def with_undo_support(func):
    """为函数添加Maya撤销支持的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        cmds.undoInfo(openChunk=True)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            cmds.warning(f"执行 {func.__name__} 时出错: {str(e)}")
            raise
        finally:
            cmds.undoInfo(closeChunk=True)
    return wrapper



# 创建绑定基础设置
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

#创建次级控制层级
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

# 创建物体控制器
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

# 镜像曲线形状
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

# 替换曲线形状
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


# 加载外部模块
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


# 重新添加形状节点
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


# 自动重命名曲线形状
def auto_rename_curve_shapes(self):
        """调用曲线Shape重命名工具的自动全部命名功能"""
        curve_rename_file = os.path.join(TOOL_DIR, "curve_shape_rename_tool.py")
        if not os.path.exists(curve_rename_file):
            cmds.warning(f"未找到 curve_shape_rename_tool.py 文件: {curve_rename_file}")
            return

        try:
            # 直接执行Python文件
            with open(curve_rename_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 创建一个新的命名空间来执行代码，包含必要的导入
            namespace = {
                'cmds': cmds,
                'mel': mel,
                'os': os,
                'sys': sys,
                '__builtins__': __builtins__
            }
            exec(code, namespace)
            
            # 调用自动全部命名函数
            if "auto_rename_all" in namespace:
                namespace["auto_rename_all"]()
                print("已运行 curve_shape_rename_tool.py 的自动命名功能")
            else:
                cmds.warning("curve_shape_rename_tool.py 中未找到 auto_rename_all 函数")
        except Exception as e:
            cmds.warning(f"运行 curve_shape_rename_tool.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")
#拆分曲线
@with_undo_support
def separate_selected_curves(self):
        """拆分选中的曲线"""
        separate_file = os.path.join(TOOL_DIR, "split_curves.py")
        if not os.path.exists(separate_file):
            cmds.warning(f"未找到 split_curves.py 文件: {separate_file}")
            return

        try:
            import importlib.util
            module_name = "split_curves"

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
                print("已运行 split_curves.py 中的 selected_curves_separate 函数，拆分选中的曲线")
            else:
                cmds.warning("split_curves.py 中未找到 selected_curves_separate 函数")
        except Exception as e:
            cmds.warning(f"运行 split_curves.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")

@with_undo_support
def open_fk_constraint_group_tool(self):
        """打开FK约束打组工具"""
        try:
            # 使用load_module函数加载并运行FK约束打组工具
            module_name = "fk_constraint_group_tool"
            file_path = os.path.join(TOOL_DIR, f"{module_name}.py")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                cmds.warning(f"找不到文件: {file_path}")
                return
                
            # 加载模块并运行create_constraint_ui函数
            load_module(module_name, file_path, "create_constraint_ui")
            print(f"已成功打开FK约束打组工具")
        except Exception as e:
            cmds.warning(f"打开FK约束打组工具失败: {str(e)}")
            print(f"错误详情: {str(e)}")

@with_undo_support
def apply_random_colors(self):
        """调用随机颜色功能"""
        try:
            # 使用load_module函数加载并执行随机颜色模块
            load_module("random_colors", os.path.join(TOOL_DIR, "random_colors.py"), "assign_random_colors")
        except Exception as e:
            cmds.warning(f"执行 random_colors.py 中的 assign_random_colors 函数时出错: {str(e)}")
            print(f"错误详情: {str(e)}")
    
def open_gradient_color_tool(self):
        """打开渐变颜色工具"""
        try:
            # 使用load_module函数加载并执行渐变颜色模块
            load_module("gradient_colors", os.path.join(TOOL_DIR, "gradient_colors.py"), "show_gradient_color_tool")
        except Exception as e:
            cmds.warning(f"打开渐变颜色工具时出错: {str(e)}")
            print(f"错误详情: {str(e)}")

@with_undo_support
def combine_selected_curves(self):
        """结合选中的曲线"""
        combine_file = os.path.join(TOOL_DIR, "combine_curves.py")
        if not os.path.exists(combine_file):
            cmds.warning(f"未找到 combine_curves.py 文件: {combine_file}")
            return

        try:
            import importlib.util
            module_name = "combine_curves" 

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
                print("已运行 combine_curves.py 中的 selected_curves_combine 函数，结合选中的曲线")  
            else:
                cmds.warning("combine_curves.py 中未找到 selected_curves_combine 函数")
        except Exception as e:
            cmds.warning(f"运行 combine_curves.py 失败: {str(e)}")
            print(f"错误详情: {str(e)}")