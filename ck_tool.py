from maya import cmds
import maya.mel as mel
import re
import math
import os
import sys  # 用于动态添加路径
import importlib
import json
import time
from datetime import datetime
from functools import wraps  # 用于装饰器



# 导入控制器形状模块
from controllers import controller_shapes

# 新增：导入分离后的 UI 与外部引用模块
from ui import CombinedTool
import external_reference as external_reference

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

# 绑定与注入：将当前文件与 external_reference 的方法挂到 CombinedTool
def attach_external_methods_to_combined_tool():
    # 将依赖注入到 external_reference 的命名空间，确保其函数可用
    external_reference.os = os
    external_reference.sys = sys
    external_reference.cmds = cmds
    external_reference.mel = mel
    external_reference.TOOL_DIR = TOOL_DIR
    external_reference.load_module = load_module
    external_reference.with_undo_support = with_undo_support

    # 辅助：从模块中挑选第一个参数为 self 的可调用对象并绑定到 CombinedTool
    import inspect
    def attach_from(module):
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj):
                # 支持带有 @with_undo_support 装饰器的函数，通过 __wrapped__ 还原原始函数签名
                target = getattr(obj, "__wrapped__", obj)
                code = getattr(target, "__code__", None)
                if code and code.co_varnames and len(code.co_varnames) > 0 and code.co_varnames[0] == "self":
                    setattr(CombinedTool, name, obj)

    # 绑定当前文件中定义的工具方法（如曲线相关等）
    attach_from(sys.modules[__name__])
    # 绑定 external_reference 中的 open_* 等外部工具方法
    attach_from(external_reference)



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
        """放大控制器的控制顶点，支持按形状局部中心或控制器轴心"""
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = self.scale_factor_input.value()
        use_local_center = getattr(self, 'local_scale_checkbox', None) and self.local_scale_checkbox.isChecked()

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

                mode_text = "局部中心" if use_local_center else "控制器轴心"
                print(f"已将控制器 '{ctrl}' 的 {len(shapes)} 个形状节点的控制顶点按倍率 {scale_factor} 放大（基于{mode_text}）")
            else:
                print(f"警告: '{ctrl}' 不是NURBS曲线控制器，跳过处理")

    @with_undo_support
    def scale_cv_handles_down(self):
        """缩小控制器的控制顶点，支持按形状局部中心或控制器轴心"""
        selected_controllers = cmds.ls(selection=True, type="transform")
        if not selected_controllers:
            cmds.warning("请至少选择一个控制器！")
            return

        scale_factor = 1.0 / self.scale_factor_input.value()
        use_local_center = getattr(self, 'local_scale_checkbox', None) and self.local_scale_checkbox.isChecked()

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

                mode_text = "局部中心" if use_local_center else "控制器轴心"
                print(f"已将控制器 '{ctrl}' 的 {len(shapes)} 个形状节点的控制顶点按倍率 {1.0 / scale_factor} 缩小（基于{mode_text}）")
            else:
                print(f"警告: '{ctrl}' 不是NURBS曲线控制器，跳过处理")

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

    # 显式绑定这些方法到 CombinedTool
    setattr(CombinedTool, 'scale_cv_handles_up', scale_cv_handles_up)
    setattr(CombinedTool, 'scale_cv_handles_down', scale_cv_handles_down)
    setattr(CombinedTool, 'get_cv_handle_scale', get_cv_handle_scale)
    setattr(CombinedTool, 'apply_curve_width', apply_curve_width)
    setattr(CombinedTool, 'get_shape_local_center', get_shape_local_center)
    # 自动绑定逻辑已移至函数末尾，确保覆盖所有内嵌方法



    def rgb_to_hex(self, rgb):
        r, g, b = [int(c * 255) for c in rgb]
        return "#{:02X}{:02X}{:02X}".format(r, g, b)

    def compute_text_color(self, r, g, b):
        brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if brightness > 0.5 else "#FFFFFF"

    def apply_preview_style(self, hex_color, text_color, border_css):
        self.color_preview.setStyleSheet(f"""
            background-color: {hex_color};
            border: {border_css};
            border-radius: 5px;
            color: {text_color};
            font-size: 10px;
            text-align: center;
            padding: 2px;
        """)

    def apply_preset_color(self, rgb):
        self.set_preset_color(rgb)
        self.apply_color_to_controller()

    def update_color_preview(self):
        hex_color = self.rgb_to_hex(self.color_rgb)
        r, g, b = [int(c * 255) for c in self.color_rgb]
        text_color = self.compute_text_color(r, g, b)
        self.apply_preview_style(hex_color, text_color, "1px solid #666666")
        self.color_preview.setText(f"{hex_color}")
        self.color_preview.setToolTip(f"RGB: {r}, {g}, {b}\n点击修改颜色")

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
        
        # 启用自定义颜色并显示颜色代码编辑框（移除淡入动画）
        color_dialog.setOptions(QColorDialog.ShowAlphaChannel | QColorDialog.DontUseNativeDialog)

        # 使用集中定义的预设颜色填充自定义颜色槽（最多前10个）
        for i in range(min(10, len(self.preset_colors))):
            r, g, b = self.preset_colors[i]
            qcolor = QColor(int(r * 255), int(g * 255), int(b * 255))
            color_dialog.setCustomColor(i, qcolor.rgb())

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
        """重置颜色功能：识别选中物体及其所有子层级中的形状节点并重置颜色"""
        selected_nodes = cmds.ls(selection=True, long=True)
        if not selected_nodes:
            cmds.warning("请至少选择一个控制器！")
            return

        # 收集所有需要重置的形状节点（包含直接选中的形状与所有后代形状）
        shapes_to_reset = set()
        for node in selected_nodes:
            if cmds.objectType(node, isAType="shape"):
                shapes_to_reset.add(node)
            else:
                # 后代形状
                descendant_shapes = cmds.listRelatives(node, shapes=True, allDescendents=True, fullPath=True) or []
                # 直接子形状（以防 allDescendents 不包含本节点的直接形状）
                direct_shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
                for s in descendant_shapes + direct_shapes:
                    shapes_to_reset.add(s)

        reset_count = 0
        for shape in shapes_to_reset:
            try:
                # 先将RGB颜色模式切回索引颜色模式
                if cmds.attributeQuery("overrideRGBColors", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                # 然后关闭绘制覆盖
                if cmds.attributeQuery("overrideEnabled", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.overrideEnabled", 0)
                reset_count += 1
            except Exception as e:
                print(f"重置形状 '{shape}' 颜色覆盖失败: {e}")

        if reset_count:
            print(f"已重置 {reset_count} 个形状的颜色覆盖。")
        else:
            cmds.warning("未找到可重置颜色的形状节点。")



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


    # 显式绑定复位方法到 CombinedTool
    setattr(CombinedTool, 'reset_position', reset_position)
    setattr(CombinedTool, 'reset_rotation', reset_rotation)
    setattr(CombinedTool, 'reset_scale', reset_scale)

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
            print(f"成功创建FK层级链，共 {len(controllers)} 个控制器")
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

    # 自动绑定本函数内定义的以 self 为首参数的方法（支持装饰器）
    for _name, _obj in list(locals().items()):
        if _name.startswith("_"):
            continue
        if callable(_obj):
            _target = getattr(_obj, "__wrapped__", _obj)
            _code = getattr(_target, "__code__", None)
            if _code and _code.co_varnames and len(_code.co_varnames) > 0 and _code.co_varnames[0] == "self":
                setattr(CombinedTool, _name, _obj)

# 运行工具
def run_tool():
    try:
        # 先绑定方法与注入依赖，再显示窗口
        attach_external_methods_to_combined_tool()

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
