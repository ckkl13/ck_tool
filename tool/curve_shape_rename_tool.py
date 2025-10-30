import maya.cmds as cmds

def rename_curve_shapes(target_curves):
    renamed_count = 0

    for curve in target_curves:
        # 检查是否有shape且shape是nurbsCurve
        shapes = cmds.listRelatives(curve, shapes=True, fullPath=True)
        if not shapes:
            continue

        for index, shape in enumerate(shapes):
            if cmds.nodeType(shape) != 'nurbsCurve':
                continue

            # 生成新名称，支持多shape编号
            transform_name = curve.split('|')[-1]
            new_shape_name = f"{transform_name}_Shape" if len(shapes) == 1 else f"{transform_name}_Shape{index+1}"

            # 避免重名
            if cmds.objExists(new_shape_name):
                cmds.warning(f"{new_shape_name} 已存在，跳过重命名。")
                continue

            cmds.rename(shape, new_shape_name)
            renamed_count += 1
            print(f"{shape} 重命名为 {new_shape_name}")

    cmds.inViewMessage(amg=f"<hl>完成！共重命名 {renamed_count} 个曲线shape。</hl>", pos='midCenterTop', fade=True)


def auto_rename_all():
    # 如果有选择，则只对选中的曲线进行重命名
    selected = cmds.ls(selection=True, long=True)
    if selected:
        rename_selected()
        return
    
    # 查找场景内所有带 nurbsCurve 的 transform
    all_curves = []
    transforms = cmds.ls(type='transform', long=True)
    for trans in transforms:
        shapes = cmds.listRelatives(trans, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                if cmds.nodeType(shape) == 'nurbsCurve':
                    all_curves.append(trans)
                    break
    if not all_curves:
        cmds.warning('场景中未找到曲线。')
        return
    rename_curve_shapes(all_curves)


def rename_selected():
    selected = cmds.ls(selection=True, long=True)
    if not selected:
        cmds.warning('请先选择需要重命名的曲线。')
        return

    # 过滤选中的曲线
    target_curves = []
    for obj in selected:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                if cmds.nodeType(shape) == 'nurbsCurve':
                    target_curves.append(obj)
                    break

    if not target_curves:
        cmds.warning('选择的物体中没有有效的曲线。')
        return

    rename_curve_shapes(target_curves)


# 直接运行自动全部命名功能
if __name__ == "__main__":
    # 运行时优先使用选择；无选择则处理全场景
    selected = cmds.ls(selection=True, long=True)
    if selected:
        rename_selected()
    else:
        auto_rename_all()
else:
    # 当作为模块导入时不自动执行，等待外部调用
    pass
