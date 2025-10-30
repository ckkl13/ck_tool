import maya.cmds as cmds
import re


def get_unique_name(base_name):
    """生成一个唯一的名称，如果名称已存在，则递增后缀"""
    suffix = 1
    new_name = f"{base_name}_{str(suffix).zfill(3)}"

    while cmds.objExists(new_name):
        suffix += 1
        new_name = f"{base_name}_{str(suffix).zfill(3)}"

    return new_name


def create_controller(name, parent, radius=70, sections=8):
    """创建控制器并返回控制器和零控制器的名称"""
    zero_ctrl = cmds.group(em=True, name=f"zero_{name}", parent=parent)
    ctrl = cmds.circle(
        name=name,
        c=(0, 0, 0),
        nr=(0, 1, 0),
        sw=360,
        r=radius,
        d=3,
        ut=0,
        tol=0.01,
        s=sections,
        ch=1
    )[0]
    cmds.parent(ctrl, zero_ctrl)
    return zero_ctrl, ctrl


def create_general_control(parent):
    """创建General control控制器，使用自定义曲线形状"""
    # 创建自定义曲线形状
    curve = cmds.curve(
        d=1,
        p=[(-1.044209, 7.931564, 0),
           (1.044209, 7.931564, 0),
           (2.143027, 5.173721, 0),
           (3.409064, 4.44278, 0),
           (6.346827, 4.870087, 0),
           (7.391036, 3.061462, 0),
           (5.552091, 0.730942, 0),
           (5.552091, -0.730942, 0),
           (7.391036, -3.061462, 0),
           (6.346827, -4.870087, 0),
           (3.409064, -4.44278, 0),
           (2.143027, -5.173721, 0),
           (1.044209, -7.931564, 0),
           (-1.044209, -7.931564, 0),
           (-2.143027, -5.173721, 0),
           (-3.409064, -4.44278, 0),
           (-6.346827, -4.870087, 0),
           (-7.391036, -3.061462, 0),
           (-5.552091, -0.730942, 0),
           (-5.552091, 0.730942, 0),
           (-7.391036, 3.061462, 0),
           (-6.346827, 4.870087, 0),
           (-3.409064, 4.44278, 0),
           (-2.143027, 5.173721, 0),
           (-1.044209, 7.931564, 0)],
        name="GeneralControl"
    )
    
    # 创建零组
    zero_general_control = cmds.group(em=True, name="zero_GeneralControl", parent=parent)
    
    # 将控制器放到零组里
    cmds.parent(curve, zero_general_control)
    
    # 移动零组y轴100
    cmds.setAttr(f"{zero_general_control}.translateY", 100)
    
    return zero_general_control, curve


def create_hierarchy(master_name="master", num_count=1):
    """创建层级结构，支持指定数量的控制器
    
    参数:
        master_name (str): 主层级名称，默认为"master"
        num_count (int): 控制器数量，默认为1
    """
    try:

        # 创建主层级
        master = cmds.group(em=True, name=master_name)

        # 创建几何体层级
        geometry = cmds.group(em=True, name="geometry", parent=master)
        grp_low_model = cmds.group(em=True, name=get_unique_name("grp_low_model"), parent=geometry)
        grp_mid_model = cmds.group(em=True, name=get_unique_name("grp_mid_model"), parent=geometry)
        grp_high_model = cmds.group(em=True, name=get_unique_name("grp_high_model"), parent=geometry)
        
        # 创建控制器层级
        controls = cmds.group(em=True, name="controls", parent=master)
        controllers = []
        for i in range(num_count):
            ctrl_name = f"ctrl_m_world_{str(i + 1).zfill(3)}"
            zero_m_world, ctrl_m_world = create_controller(ctrl_name, controls)
            controllers.append(ctrl_m_world)
            cmds.delete(ctrl_m_world, ch=True)  # 清理控制器历史
        
        # 创建General control控制器，放到第一个控制器下面
        if controllers:
            first_ctrl = controllers[0]
            zero_general_control, general_control = create_general_control(first_ctrl)
        else:
            zero_general_control, general_control = create_general_control(master)
        
        # 锁定并隐藏GeneralControl控制器的平移、旋转、缩放，但保持可见性可用
        transform_attrs = ["translateX", "translateY", "translateZ",
                          "rotateX", "rotateY", "rotateZ",
                          "scaleX", "scaleY", "scaleZ"]
        for attr in transform_attrs:
            cmds.setAttr(f"{general_control}.{attr}", lock=True, keyable=False, channelBox=False)
        
        # 保持可见性属性可用
        cmds.setAttr(f"{general_control}.visibility", lock=False, keyable=True, channelBox=True)

        # 创建骨骼层级
        rig_nodes = cmds.group(em=True, name="rigNodes", parent=master)
        rig_nodes_local = cmds.group(em=True, name="rigNodesLocal", parent=rig_nodes)
        rig_nodes_world = cmds.group(em=True, name="rigNodesWorld", parent=rig_nodes)

        # 创建关节层级
        driver_joints = cmds.group(em=True, name="Driver_Joints", parent=master)
        export_skinning_joints = cmds.group(em=True, name="Export_Skin_Joints", parent=master)

        # 使用第一个控制器进行约束
        if controllers:
            ctrl_m_world = controllers[0]  # 使用第一个控制器作为主约束对象
            cmds.parentConstraint(ctrl_m_world, rig_nodes_local, mo=True)
            cmds.scaleConstraint(ctrl_m_world, rig_nodes_local, mo=True)
            cmds.parentConstraint(ctrl_m_world, driver_joints, mo=True)
            cmds.scaleConstraint(ctrl_m_world, driver_joints, mo=True)
            # Export_Skinning_Joints 被 world 控制器约束（不保持偏移）
            cmds.parentConstraint(ctrl_m_world, export_skinning_joints, mo=False)
            cmds.scaleConstraint(ctrl_m_world, export_skinning_joints, mo=False)

        # 添加自定义属性到 general_control
        cmds.addAttr(general_control, longName="geometryVis", attributeType="bool", defaultValue=1)
        cmds.addAttr(general_control, longName="geometryDisplayType", attributeType="enum", enumName="Normal:Template:Reference")
        cmds.addAttr(general_control, longName="resolution", attributeType="enum", enumName="Low:Mid:High", defaultValue=1)
        cmds.addAttr(general_control, longName="controlsVis", attributeType="bool", defaultValue=1, keyable=True)
        cmds.addAttr(general_control, longName="driverJointsVis", attributeType="bool", defaultValue=1)
        cmds.addAttr(general_control, longName="exportSkinningJointsVis", attributeType="bool", defaultValue=1)
        cmds.addAttr(general_control, longName="rignodesVis", attributeType="bool", defaultValue=1)

        # 修改自定义属性的键控状态和显示在 Channel Box 的设置
        cmds.setAttr(f"{general_control}.geometryVis", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.geometryDisplayType", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.resolution", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.controlsVis", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.driverJointsVis", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.exportSkinningJointsVis", edit=True, keyable=False, channelBox=True)
        cmds.setAttr(f"{general_control}.rignodesVis", edit=True, keyable=False, channelBox=True)

        # 创建 condition 节点 - 用于低分辨率可见性控制
        lowvis = cmds.createNode("condition", name=get_unique_name("lowvis"))
        cmds.setAttr(f"{lowvis}.secondTerm", 0)
        cmds.setAttr(f"{lowvis}.operation", 0)  # 相等操作
        cmds.connectAttr(f"{general_control}.resolution", f"{lowvis}.firstTerm")
        cmds.setAttr(f"{lowvis}.colorIfTrue", 1, 0, 0)  # True 时的颜色为红色
        cmds.setAttr(f"{lowvis}.colorIfFalse", 0, 1, 0)  # False 时的颜色为绿色
        cmds.connectAttr(f"{lowvis}.outColorR", f"{grp_low_model}.visibility")

        # 创建 condition 节点 - 用于中分辨率可见性控制
        midvis = cmds.createNode("condition", name=get_unique_name("midvis"))
        cmds.setAttr(f"{midvis}.secondTerm", 1)
        cmds.setAttr(f"{midvis}.operation", 0)  # 相等操作
        cmds.connectAttr(f"{general_control}.resolution", f"{midvis}.firstTerm")
        cmds.setAttr(f"{midvis}.colorIfTrue", 1, 0, 0)  # True 时的颜色为红色
        cmds.setAttr(f"{midvis}.colorIfFalse", 0, 1, 0)  # False 时的颜色为绿色
        cmds.connectAttr(f"{midvis}.outColorR", f"{grp_mid_model}.visibility")

        # 创建 condition 节点 - 用于高分辨率可见性控制
        highvis = cmds.createNode("condition", name=get_unique_name("highvis"))
        cmds.setAttr(f"{highvis}.secondTerm", 2)
        cmds.setAttr(f"{highvis}.operation", 0)  # 相等操作
        cmds.connectAttr(f"{general_control}.resolution", f"{highvis}.firstTerm")
        cmds.setAttr(f"{highvis}.colorIfTrue", 1, 0, 0)  # True 时的颜色为红色
        cmds.setAttr(f"{highvis}.colorIfFalse", 0, 1, 0)  # False 时的颜色为绿色
        cmds.connectAttr(f"{highvis}.outColorR", f"{grp_high_model}.visibility")

        # 检查并连接 general_control 的可见性属性到各个组的可见性
        if cmds.objExists(geometry):
            cmds.connectAttr(f"{general_control}.geometryVis", f"{geometry}.visibility", force=True)
        if cmds.objExists(geometry):
            cmds.connectAttr(f"{general_control}.geometryDisplayType", f"{geometry}.overrideDisplayType", force=True)
        if cmds.objExists(controls):
            cmds.connectAttr(f"{general_control}.controlsVis", f"{controls}.visibility", force=True)
        if cmds.objExists(driver_joints):
            cmds.connectAttr(f"{general_control}.driverJointsVis", f"{driver_joints}.visibility", force=True)
        if cmds.objExists(export_skinning_joints):
            cmds.connectAttr(f"{general_control}.exportSkinningJointsVis", f"{export_skinning_joints}.visibility", force=True)
        if cmds.objExists(rig_nodes):
            cmds.connectAttr(f"{general_control}.rignodesVis", f"{rig_nodes}.visibility", force=True)

        # 启用 geometry 的绘制覆盖
        cmds.setAttr(f"{geometry}.overrideEnabled", 1)  # 启用绘制覆盖

        # 锁定并隐藏 geometry 的位移、旋转、缩放、可见性
        attrs = ["translateX", "translateY", "translateZ",
                 "rotateX", "rotateY", "rotateZ",
                 "scaleX", "scaleY", "scaleZ"]
        
        # 锁定master的变换属性并隐藏
        for attr in attrs:
            cmds.setAttr(f"{master}.{attr}", lock=True, keyable=False, channelBox=False)
        
        # 保持master的visibility属性可用
        cmds.setAttr(f"{master}.visibility", lock=False, keyable=True, channelBox=True)
        
        # 解除锁定其他组的所有属性（包括visibility）
        all_attrs = attrs + ["visibility"]
        for attr in all_attrs:
            cmds.setAttr(f"{geometry}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{controls}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{rig_nodes}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{driver_joints}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{export_skinning_joints}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{rig_nodes_local}.{attr}", lock=False, keyable=True, channelBox=True)
            cmds.setAttr(f"{rig_nodes_world}.{attr}", lock=False, keyable=True, channelBox=True)

        print(f"✅ 层级结构创建完成，包含 {num_count} 个控制器！")

    except Exception as e:
        print(f"创建层级结构时出错: {e}")


# 直接运行创建层级结构
if __name__ == "__main__":
    create_hierarchy()