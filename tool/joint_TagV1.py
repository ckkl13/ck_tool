import maya.cmds as cmds

def toggle_joint_labels():
    """切换骨骼 drawLabel 开关 (优先对选中的骨骼操作，没有选择时对所有骨骼操作)"""
    
    # 获取选择
    selection = cmds.ls(selection=True, type="joint")
    
    # 如果没有选择，获取场景内所有骨骼
    if selection:
        joints = selection
    else:
        joints = cmds.ls(type="joint")
    
    if not joints:
        cmds.warning("没有找到任何骨骼")
        return
    
    # 检查第一个骨骼当前状态
    current_state = cmds.getAttr(joints[0] + ".drawLabel")
    new_state = 0 if current_state == 1 else 1
    
    # 设置所有骨骼的 drawLabel
    for jnt in joints:
        if cmds.objExists(jnt + ".drawLabel"):
            try:
                cmds.setAttr(jnt + ".drawLabel", new_state)
            except:
                cmds.warning("无法设置属性: {}".format(jnt))
    
    state_text = "启用" if new_state == 1 else "关闭"
    print("已{} {} 个骨骼的标签".format(state_text, len(joints)))

# 运行
toggle_joint_labels()
