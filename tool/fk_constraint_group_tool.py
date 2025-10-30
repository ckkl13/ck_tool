# -*- coding: utf-8 -*-
import maya.cmds as cmds

# -------------------------
# 基础工具函数
# -------------------------

def match_transform(target, source):
    """对齐 target 到 source（位置、旋转、缩放）"""
    matrix = cmds.xform(source, q=True, ws=True, matrix=True)
    cmds.xform(target, ws=True, matrix=matrix)

def create_constraint(source, target, constraint_types):
    """根据选择的约束类型创建约束"""
    constraints = []
    
    if constraint_types.get("parent"):
        constraints.append(cmds.parentConstraint(source, target, mo=True)[0])
    if constraint_types.get("point"):
        constraints.append(cmds.pointConstraint(source, target, mo=True)[0])
    if constraint_types.get("orient"):
        constraints.append(cmds.orientConstraint(source, target, mo=True)[0])
    if constraint_types.get("scale"):
        constraints.append(cmds.scaleConstraint(source, target, mo=True)[0])
    
    return constraints

# -------------------------
# 次级控制器功能
# -------------------------

def create_sub_controller(ctrl):
    """为控制器创建次级控制器，并建立输出与可见性控制"""
    # 复制控制器
    sub = cmds.duplicate(ctrl, rr=True)[0]
    # 命名为原控制器名 + 'Sur'
    sub = cmds.rename(sub, unique_name(ctrl + 'Sur'))
    # 放入层级：父到主控制器
    cmds.parent(sub, ctrl)
    # 缩放并冻结缩放
    cmds.setAttr(sub + '.scale', 0.9, 0.9, 0.9)
    cmds.makeIdentity(sub, apply=True, scale=True)

    # 创建 output 组，命名基于控制器名
    out_base = ctrl.replace('ctrl_', 'output_')
    if out_base == ctrl:
        if ctrl.endswith('_Ctrl'):
            out_base = ctrl.replace('_Ctrl', '_Output')
        else:
            out_base = 'output_' + ctrl
    output = cmds.createNode('transform', name=unique_name(out_base), parent=ctrl)

    # 连接属性
    cmds.connectAttr(sub + '.translate', output + '.translate', force=True)
    cmds.connectAttr(sub + '.rotate', output + '.rotate', force=True)
    cmds.connectAttr(sub + '.rotateOrder', output + '.rotateOrder', force=True)
    cmds.connectAttr(sub + '.scale', output + '.scale', force=True)

    # 在通道盒显示旋转顺序
    cmds.setAttr(ctrl + '.rotateOrder', channelBox=True)
    cmds.setAttr(sub + '.rotateOrder', channelBox=True)

    # 添加次级控制器可见性开关
    if not cmds.attributeQuery('subCtrlVis', node=ctrl, exists=True):
        cmds.addAttr(ctrl, longName='subCtrlVis', attributeType='bool')
    cmds.setAttr(ctrl + '.subCtrlVis', channelBox=True)
    cmds.connectAttr(ctrl + '.subCtrlVis', sub + '.visibility', force=True)

    # 锁定隐藏无用属性（不处理缩放）
    for attr in ['visibility']:
        for node in [ctrl, sub]:
            try:
                cmds.setAttr('{}.{}'.format(node, attr), keyable=False, channelBox=False, lock=True)
            except Exception:
                pass

    return sub, output

def strip_prefix(name, exclude_prefixes=None):
    """去掉名称开头的指定前缀"""
    if exclude_prefixes:
        for p in exclude_prefixes:
            if name.startswith(p):
                return name[len(p):]
    return name

def unique_name(base_name):
    """确保命名唯一"""
    if cmds.objExists(base_name):
        i = 1
        while cmds.objExists("{}_{}".format(base_name, i)):
            i += 1
        return "{}_{}".format(base_name, i)
    return base_name

def create_ctrl_hierarchy_recursive(obj, parent_ctrl=None, mode="full", all_ctrl_info=None, exclude_prefixes=None, create_sub=False, recurse_children=True):
    """
    为单个物体及其子物体递归生成控制器层级
    如果选择的物体是曲线，则直接使用该控制器
    """
    base = obj
    short_name = strip_prefix(base, exclude_prefixes)

    # 创建组层级
    if mode == "full":
        zero_name    = unique_name("zero_{}".format(short_name))
        driven_name  = unique_name("driven_{}".format(short_name))
        connect_name = unique_name("connect_{}".format(short_name))
        offset_name  = unique_name("offset_{}".format(short_name))
        ctrl_name    = unique_name("ctrl_{}".format(short_name))

        zero_grp    = cmds.group(empty=True, name=zero_name)
        driven_grp  = cmds.group(empty=True, name=driven_name)
        connect_grp = cmds.group(empty=True, name=connect_name)
        offset_grp  = cmds.group(empty=True, name=offset_name)

        for g in [zero_grp, driven_grp, connect_grp, offset_grp]:
            match_transform(g, base)

        cmds.parent(driven_grp, zero_grp)
        cmds.parent(connect_grp, driven_grp)
        cmds.parent(offset_grp, connect_grp)
        parent_grp = offset_grp

    elif mode == "simple":
        zero_name    = unique_name("zero_{}".format(short_name))
        offset_name  = unique_name("grpOffset_{}".format(short_name))
        ctrl_name    = unique_name("ctrl_{}".format(short_name))

        zero_grp   = cmds.group(empty=True, name=zero_name)
        offset_grp = cmds.group(empty=True, name=offset_name)

        for g in [zero_grp, offset_grp]:
            match_transform(g, base)

        cmds.parent(offset_grp, zero_grp)
        parent_grp = offset_grp

    elif mode == "group":
        gp_name   = unique_name("{}_Gp".format(short_name))
        gro_name  = unique_name("{}_Gro".format(short_name))
        g_name    = unique_name("{}_G".format(short_name))
        ctrl_name = unique_name("{}_Ctrl".format(short_name))

        gp_grp  = cmds.group(empty=True, name=gp_name)
        gro_grp = cmds.group(empty=True, name=gro_name)
        g_grp   = cmds.group(empty=True, name=g_name)

        for g in [gp_grp, gro_grp, g_grp]:
            match_transform(g, base)

        cmds.parent(gro_grp, gp_grp)
        cmds.parent(g_grp, gro_grp)
        parent_grp = g_grp

    # 检测是否为曲线控制器
    shapes = cmds.listRelatives(base, s=True, ni=True) or []
    is_curve_ctrl = any([cmds.nodeType(s) == "nurbsCurve" for s in shapes])

    if is_curve_ctrl:
        ctrl = base
    else:
        # 创建正方体控制器
        cube_points = [(-1,-1,-1), (-1,-1,1), (-1,1,1), (-1,1,-1),
                       (-1,-1,-1), (1,-1,-1), (1,-1,1), (-1,-1,1),
                       (1,-1,1), (1,1,1), (-1,1,1), (-1,1,-1),
                       (-1,1,-1), (1,1,-1), (1,-1,-1),
                       (1,1,-1), (1,1,1), (1,-1,1), (1,-1,-1)]
        ctrl = cmds.curve(name=ctrl_name, d=1, p=cube_points)
        match_transform(ctrl, base)


    # 父子关系
    cmds.parent(ctrl, parent_grp)

    # 已有曲线控制器命名规则：full/simple 用 'ctrl_' 前缀，group 用 '_Ctrl' 后缀
    if is_curve_ctrl:
        if mode == "group":
            if not ctrl.endswith('_Ctrl'):
                new_name = unique_name(ctrl + '_Ctrl')
                ctrl = cmds.rename(ctrl, new_name)
        else:
            if not ctrl.startswith('ctrl_'):
                new_name = unique_name("ctrl_{}".format(strip_prefix(ctrl, exclude_prefixes)))
                ctrl = cmds.rename(ctrl, new_name)
        base = ctrl

    # 非骨骼且不是已有曲线才 parent
    if cmds.nodeType(base) != "joint" and not is_curve_ctrl:
        cmds.parent(base, ctrl)

    # 如果有父控制器
    if parent_ctrl:
        if mode == "group":
            cmds.parent(gp_grp, parent_ctrl)
        else:
            cmds.parent(zero_grp, parent_ctrl)

    # 次级控制器（可选）
    sub_node = None
    output = None
    if create_sub:
        try:
            sub_node, output = create_sub_controller(ctrl)
        except Exception as e:
            cmds.warning("Failed to create sub controller for {}: {}".format(ctrl, e))

    ctrl_info = {"base": base, "ctrl": ctrl, "parent_grp": parent_grp}
    if sub_node:
        ctrl_info["sub"] = sub_node
    if output:
        ctrl_info["output"] = output
    if all_ctrl_info is not None:
        all_ctrl_info.append(ctrl_info)

    # 递归子物体（可关闭）
    if recurse_children:
        children = cmds.listRelatives(base, children=True, type='transform') or []
        # 过滤掉已创建的控制器相关节点（包括 Sur 和 output）
        skip_set = set([n for n in [sub_node, output] if n])
        children = [c for c in children if not (c in skip_set or c.startswith(("ctrl_", "zero_", "offset_", "connect_", "driven_")))]
        # 下一级层级根放到当前 output 下（若启用次级控制器）
        next_parent = output if (create_sub and output) else ctrl
        for child in children:
            create_ctrl_hierarchy_recursive(child, next_parent, mode, all_ctrl_info, exclude_prefixes, create_sub, recurse_children)

    return ctrl_info

def run_with_constraints(parent_cb, point_cb, orient_cb, scale_cb, mode_radio, exclude_txt, sub_cb, fk_cb):
    # 获取约束类型
    constraint_types = {
        "parent": cmds.checkBox(parent_cb, q=True, value=True),
        "point": cmds.checkBox(point_cb, q=True, value=True),
        "orient": cmds.checkBox(orient_cb, q=True, value=True),
        "scale": cmds.checkBox(scale_cb, q=True, value=True)
    }

    # 获取层级模式
    mode_sel = cmds.radioButtonGrp(mode_radio, q=True, select=True)
    mode = {1: "full", 2: "simple", 3: "group"}.get(mode_sel, "full")

    # 获取排除前缀
    exclude_prefixes = [x.strip() for x in cmds.textField(exclude_txt, q=True, text=True).split(",") if x.strip()]

    # 获取选择
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("No objects selected.")
        return

    # 勾选次级控制器与 FK 层级模式
    created_sub = cmds.checkBox(sub_cb, q=True, value=True)
    fk_mode = cmds.checkBox(fk_cb, q=True, value=True)
    all_ctrl_info = []
    chain_parent = None

    for obj in sel:
        if fk_mode:
            # 将本次生成的层级根（zero）放到上一个的 output 下（启用 FK 链式父级）
            root_info = create_ctrl_hierarchy_recursive(obj, parent_ctrl=chain_parent, mode=mode, all_ctrl_info=all_ctrl_info, exclude_prefixes=exclude_prefixes, create_sub=created_sub, recurse_children=True)
            if created_sub and root_info.get("output"):
                chain_parent = root_info["output"]
            else:
                chain_parent = root_info["ctrl"]
        else:
            # 关闭 FK 链式父级：每个选择对象独立生成层级
            root_info = create_ctrl_hierarchy_recursive(obj, parent_ctrl=None, mode=mode, all_ctrl_info=all_ctrl_info, exclude_prefixes=exclude_prefixes, create_sub=created_sub, recurse_children=False)
            chain_parent = None

    # 应用约束（优先使用 output 作为驱动）
    if any(constraint_types.values()):
        for info in all_ctrl_info:
            source = info.get("output") or (info.get("sub") if created_sub else info["ctrl"])  # 优先 output
            target = info["base"]
            if source != target:
                create_constraint(source, target, constraint_types)
                print("Applied constraints from {} to {}".format(source, target))

    # 自动选中生成的控制器（操作手保持为 Sur 或主 ctrl）
    cmds.select([info.get("sub", info["ctrl"]) if created_sub else info["ctrl"] for info in all_ctrl_info], replace=True)

def create_constraint_ui():
    window_name = "constraintUI"
    
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    cmds.window(window_name, title="控制器约束工具", width=400)
    cmds.columnLayout(adjustableColumn=True, columnAlign="left")

    cmds.text(label="层级模式选择:", height=30, align="left", font="boldLabelFont")
    mode_radio = cmds.radioButtonGrp(labelArray3=["完整层级", "简化层级", "打组模式"], numberOfRadioButtons=3, select=1)

    cmds.separator(height=10, style="in")

    cmds.text(label="选择约束类型:", height=30, align="left", font="boldLabelFont")
    parent_cb = cmds.checkBox(label="父子约束 (Parent Constraint)", value=True)
    point_cb = cmds.checkBox(label="点约束 (Point Constraint)", value=False)
    orient_cb = cmds.checkBox(label="旋转约束 (Orient Constraint)", value=False)
    scale_cb = cmds.checkBox(label="缩放约束 (Scale Constraint)", value=False)
    
    # 次级控制器勾选
    sub_cb = cmds.checkBox(label="次级控制器 (Sub Controller)", value=False)
    # FK 层级模式开关（启用链式父级，默认关闭）
    fk_cb = cmds.checkBox(label="FK层级模式 (启用/关闭链式父级)", value=False)

    cmds.separator(height=10, style="in")

    cmds.text(label="生成控制器名称时排除前缀 (逗号分隔):", align="left")
    exclude_txt = cmds.textField(text="jnt_")

    cmds.separator(height=10, style="in")

    cmds.button(label="创建控制器并约束", height=35,
                command=lambda x: run_with_constraints(parent_cb, point_cb, orient_cb, scale_cb, mode_radio, exclude_txt, sub_cb, fk_cb))

    cmds.separator(height=15, style="in")

    # 使用说明默认折叠
    cmds.frameLayout(label="使用说明", collapsable=True, collapse=True, marginWidth=5)
    cmds.columnLayout(adjustableColumn=True)
    cmds.text(label="1. 先选择要创建控制器的物体或已有控制器曲线", align="left")
    cmds.text(label="2. 选择层级模式（完整 / 简化 / 打组模式）", align="left")
    cmds.text(label="3. 勾选需要的约束类型", align="left")
    cmds.text(label="4. 输入排除的前缀（可选，逗号分隔）", align="left")
    cmds.text(label="5. 可启用/关闭 FK 层级模式（链式父级）", align="left")
    cmds.text(label="6. 点击按钮生成控制器或套用约束", align="left")
    cmds.text(label="控制器命名规则: 根据模式生成对应层级 (去掉前缀)", align="left", font="boldLabelFont")
    cmds.setParent('..')
    cmds.setParent('..')

    cmds.showWindow(window_name)

# 启动 UI
create_constraint_ui()

