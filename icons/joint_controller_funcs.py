# joint_controller_funcs.py
import maya.cmds as cmds
import math

def generate_unique_name(base_name, start_index=1):
    index = start_index
    unique_name = f"{base_name}_{index:03d}"
    while cmds.objExists(unique_name):
        index += 1
        unique_name = f"{base_name}_{index:03d}"
    return unique_name

def create_joint(prefix, name, side, index, translation, rotation, scale, orient="xyz", sec_axis_orient="yup",
                 preferred_angles=(0, 0, 0), joint_set=None):
    formatted_side = f"_{side}" if side and side.lower() != "none" else ""
    base_name = f"{prefix}{formatted_side}_{name}"
    joint_name = generate_unique_name(base_name, start_index=index or 1)

    cmds.select(clear=True)
    joint = cmds.joint(name=joint_name)
    cmds.joint(joint, edit=True, oj=orient, sao=sec_axis_orient, ch=True, zso=True)
    cmds.xform(joint, scale=scale, ws=True, a=True, translation=translation, rotation=rotation)
    cmds.setAttr(f"{joint}.preferredAngle", *preferred_angles)

    if joint_set:
        if not cmds.objExists(joint_set):
            joint_set = cmds.sets(name=joint_set, empty=True)
        elif cmds.nodeType(joint_set) != "objectSet":
            joint_set = cmds.sets(name=joint_set, empty=True)
        cmds.sets(joint, edit=True, forceElement=joint_set)

    return joint_name

def create_custom_controller(name, side, index, size=1, color_rgb=(1.0, 1.0, 1.0),
                             translation=(0, 0, 0), rotation=(0, 0, 0), controller_type="sphere"):
    formatted_side = f"_{side}" if side and side.lower() != "none" else ""
    base_name = f"ctrl{formatted_side}_{name}"
    ctrl_name = generate_unique_name(base_name, start_index=index or 1)

    if controller_type == "sphere":
        points = [(x * size, y * size, z * size) for x, y, z in [
            (0, 1, 0), (0, 0.92388, 0.382683), (0, 0.707107, 0.707107), (0, 0.382683, 0.92388),
            (0, 0, 1), (0, -0.382683, 0.92388), (0, -0.707107, 0.707107), (0, -0.92388, 0.382683),
            (0, -1, 0), (0, -0.92388, -0.382683), (0, -0.707107, -0.707107), (0, -0.382683, -0.92388),
            (0, 0, -1), (0, 0.382683, -0.92388), (0, 0.707107, -0.707107), (0, 0.92388, -0.382683),
            (0, 1, 0), (0.382683, 0.92388, 0), (0.707107, 0.707107, 0), (0.92388, 0.382683, 0),
            (1, 0, 0), (0.92388, -0.382683, 0), (0.707107, -0.707107, 0), (0.382683, -0.92388, 0),
            (0, -1, 0), (-0.382683, -0.92388, 0), (-0.707107, -0.707107, 0), (-0.92388, -0.382683, 0),
            (-1, 0, 0), (-0.92388, 0.382683, 0), (-0.707107, 0.707107, 0), (-0.382683, 0.92388, 0),
            (0, 1, 0), (0, 0.92388, -0.382683), (0, 0.707107, -0.707107), (0, 0.382683, -0.92388),
            (0, 0, -1), (-0.382683, 0, -0.92388), (-0.707107, 0, -0.707107), (-0.92388, 0, -0.382683),
            (-1, 0, 0), (-0.92388, 0, 0.382683), (-0.707107, 0, 0.707107), (-0.382683, 0, 0.92388),
            (0, 0, 1), (0.382683, 0, 0.92388), (0.707107, 0, 0.707107), (0.92388, 0, 0.382683),
            (1, 0, 0), (0.92388, 0, -0.382683), (0.707107, 0, -0.707107), (0.382683, 0, -0.92388),
            (0, 0, -1)
        ]]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "cube":
        points = [(x * size, y * size, z * size) for x, y, z in [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
            (1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1), (-1, 1, -1)
        ]]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "circle":
        ctrl = cmds.circle(name=ctrl_name, radius=size, normal=(0, 1, 0))[0]
    elif controller_type == "arrow":
        points = [(x * size, y * size, z * size) for x, y, z in [
            (0, 0, -1), (1, 0, 0), (0.5, 0, 0), (0.5, 0, 1),
            (-0.5, 0, 1), (-0.5, 0, 0), (-1, 0, 0), (0, 0, -1)
        ]]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "cylinder":
        base_points = [
            (math.cos(2 * math.pi * i / 8) * size, -size / 2 * size, math.sin(2 * math.pi * i / 8) * size) for i in range(8)]
        top_points = [(math.cos(2 * math.pi * i / 8) * size, size / 2 * size, math.sin(2 * math.pi * i / 8) * size)
                      for i in range(8)]
        points = base_points + [top_points[-1]] + list(reversed(top_points[:-1])) + [base_points[0]]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "cone":
        base_points = [
            (math.cos(2 * math.pi * i / 8) * size, -size / 2 * size, math.sin(2 * math.pi * i / 8) * size) for i in range(8)]
        apex = (0 * size, size / 2 * size, 0 * size)
        points = base_points + [apex] + [base_points[0]]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "cross":
        points = [(-size, 0, 0), (size, 0, 0), (0, 0, 0), (0, -size, 0), (0, size, 0)]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "diamond":
        points = [(0, size, 0), (size, 0, 0), (0, -size, 0), (-size, 0, 0), (0, size, 0)]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    elif controller_type == "rectangle":
        points = [(-size, -size / 2, 0), (size, -size / 2, 0), (size, size / 2, 0), (-size, size / 2, 0),
                  (-size, -size / 2, 0)]
        ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)

    cmds.xform(ctrl, translation=translation, rotation=rotation, worldSpace=True)
    shapes = cmds.listRelatives(ctrl, shapes=True) or []
    for shape in shapes:
        cmds.setAttr(f"{shape}.overrideEnabled", 1)
        cmds.setAttr(f"{shape}.overrideRGBColors", 1)
        cmds.setAttr(f"{shape}.overrideColorRGB", *color_rgb)

    return ctrl_name

def create_joint_and_controller(name, side, count, size, color_rgb, controller_type,
                                create_joint_flag, create_controller_flag, use_hierarchy_logic,
                                match_position, match_rotation, match_scale):
    joint_set = "Skin_Joints_Set"

    if not name:
        cmds.warning("请输入名称！")
        return

    if not create_joint_flag and not create_controller_flag:
        cmds.warning("请至少选择创建关节或控制器！")
        return

    selected_objects = cmds.ls(selection=True)
    target_obj = selected_objects[0] if selected_objects else None

    side = side if side and side.lower() in ["l", "r", "m"] else "none"
    created_groups = []
    for i in range(count):
        formatted_side = f"_{side}" if side.lower() != "none" else ""
        base_name = f"{name}{formatted_side}"

        if use_hierarchy_logic:
            zero_group_name = generate_unique_name(f"zero_{base_name}")
            driven_group_name = generate_unique_name(f"driven_{base_name}")
            connect_group_name = generate_unique_name(f"connect_{base_name}")
            offset_group_name = generate_unique_name(f"offset_{base_name}")

            zero_group = cmds.group(name=zero_group_name, empty=True)
            driven_group = cmds.group(name=driven_group_name, empty=True, parent=zero_group)
            connect_group = cmds.group(name=connect_group_name, empty=True, parent=driven_group)
            offset_group = cmds.group(name=offset_group_name, empty=True, parent=connect_group)

            ctrl = None
            joint = None

            if create_controller_flag:
                ctrl = create_custom_controller(
                    name=name, side=side, index=i + 1, size=size, color_rgb=color_rgb,
                    translation=(0, 0, 0), controller_type=controller_type
                )
                cmds.parent(ctrl, offset_group)

            if create_joint_flag:
                joint = create_joint(
                    prefix="jntSkin", name=name, side=side, index=i + 1,
                    translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1),
                    orient="xyz", sec_axis_orient="yup", preferred_angles=(0, 0, 0),
                    joint_set=joint_set
                )
                if ctrl and create_controller_flag:
                    cmds.parent(joint, ctrl)
                else:
                    cmds.parent(joint, offset_group)

            created_groups.append(zero_group)
        else:
            zero_group_name = generate_unique_name(f"zero_{base_name}")
            offset_group_name = generate_unique_name(f"grpOffset_{base_name}")

            zero_group = cmds.group(name=zero_group_name, empty=True)
            offset_group = cmds.group(name=offset_group_name, empty=True)
            cmds.parent(offset_group, zero_group)

            ctrl = None
            joint = None

            if create_controller_flag:
                ctrl = create_custom_controller(
                    name=name, side=side, index=i + 1, size=size, color_rgb=color_rgb,
                    translation=(0, 0, 0), controller_type=controller_type
                )
                cmds.parent(ctrl, offset_group)

            if create_joint_flag:
                joint = create_joint(
                    prefix="jntSkin", name=name, side=side, index=i + 1,
                    translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1),
                    orient="xyz", sec_axis_orient="yup", preferred_angles=(0, 0, 0),
                    joint_set=joint_set
                )
                if ctrl and create_controller_flag:
                    cmds.parent(joint, ctrl)
                else:
                    cmds.parent(joint, offset_group)

            created_groups.append(zero_group)

    if target_obj:
        for group in created_groups:
            cmds.matchTransform(group, target_obj, pos=match_position,
                                rot=match_rotation, scl=match_scale)
        print(f"已将 {len(created_groups)} 个 zero 组匹配到 '{target_obj}' 的变换。")