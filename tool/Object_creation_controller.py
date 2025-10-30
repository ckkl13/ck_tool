import maya.cmds as cmds

def create_controller(obj, ctrl_type, base_name):
    # 创建控制器类型
    if ctrl_type == 'Circle':
        controller = cmds.circle(name='ctrl_m_{}_001'.format(base_name),
                                 center=(0, 0, 0), normal=(0, 1, 0), sweep=360,
                                 radius=1, degree=3, useTolerance=0, tolerance=0.01,
                                 sections=8, constructionHistory=1)[0]
    elif ctrl_type == 'Cube':
        controller = cmds.curve(name='ctrl_m_{}_001'.format(base_name), degree=1,
                                point=[(-1, 1, 1), (-1, 1, -1), (1, 1, -1),
                                       (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
                                       (-1, -1, -1), (-1, 1, -1), (-1, 1, 1),
                                       (-1, -1, 1), (1, -1, 1), (1, 1, 1),
                                       (1, 1, -1), (1, -1, -1), (1, -1, 1),
                                       (1, -1, -1), (-1, -1, -1)])
    elif ctrl_type == 'Square':
        controller = cmds.curve(name='ctrl_m_{}_001'.format(base_name), degree=1,
                                point=[(-1, 0, 1), (1, 0, 1), (1, 0, -1),
                                       (-1, 0, -1), (-1, 0, 1)])
    else:
        controller = cmds.circle(name='ctrl_m_{}_001'.format(base_name), normal=(1, 0, 0))[0]
    return controller

def create_controller_for_selected_objects(ctrl_type):
    # 获取当前选择的物体
    selected_objects = cmds.ls(selection=True)

    for obj in selected_objects:
        # 获取物体名称的基本部分
        base_name = obj.split('|')[-1]

        # 冻结物体的缩放（如果需要）
        scale_values = cmds.getAttr(f'{obj}.scale')[0]
        if scale_values != (1.0, 1.0, 1.0):
            cmds.makeIdentity(obj, apply=True, scale=True)

        # 创建物体的零组和偏移组
        zero_group = cmds.group(empty=True, name='zero_m_{}_001'.format(base_name))
        offset_group = cmds.group(empty=True, name='offset_m_{}_001'.format(base_name))
        cmds.parent(offset_group, zero_group)
        cmds.matchTransform(zero_group, obj)
        cmds.parent(obj, offset_group)

        # 创建控制器
        controller = create_controller(obj, ctrl_type, base_name)

        # 创建控制器的零组
        zero_ctrl_group = cmds.group(empty=True, name='zero_ctrl_m_{}_001'.format(base_name))
        cmds.parent(controller, zero_ctrl_group)
        cmds.matchTransform(zero_ctrl_group, obj)

        # 缩放控制器匹配物体大小
        bbox = cmds.exactWorldBoundingBox(obj)
        size_x = bbox[3] - bbox[0]
        size_y = bbox[4] - bbox[1]
        size_z = bbox[5] - bbox[2]
        cmds.scale(size_x, size_y, size_z, controller, absolute=True)
        cmds.makeIdentity(controller, apply=True, scale=True)

        # 约束物体偏移组
        cmds.parentConstraint(controller, offset_group, maintainOffset=True)
        cmds.scaleConstraint(controller, offset_group, maintainOffset=True)

        # 创建rig组
        rig_group = cmds.group(empty=True, name='grp_rig_{}_001'.format(base_name))
        cmds.parent(zero_group, rig_group)
        cmds.parent(zero_ctrl_group, rig_group)

def create_ui():
    if cmds.window("controllerUI", exists=True):
        cmds.deleteUI("controllerUI")

    window = cmds.window("controllerUI", title="Controller Creator", widthHeight=(300, 150))
    cmds.columnLayout(adjustableColumn=True)

    cmds.text(label='Select Controller Type:')
    controller_types = ['Circle', 'Cube', 'Square']
    ctrl_type_menu = cmds.optionMenu()
    for ctrl_type in controller_types:
        cmds.menuItem(label=ctrl_type)

    def on_create_pressed(*args):
        selected_ctrl_type = cmds.optionMenu(ctrl_type_menu, query=True, value=True)
        create_controller_for_selected_objects(selected_ctrl_type)

    cmds.button(label='Create Controller', command=on_create_pressed)
    cmds.button(label='Close', command=('cmds.deleteUI(\"' + window + '\", window=True)'))
    cmds.showWindow(window)

# 调用UI函数
create_ui()