# coding=utf-8
import maya.cmds as cmds


def trans_curve_shape():
    """
    替换目标曲线形状：
    - 将源曲线的形状复制到一个或多个目标曲线，替换目标曲线的现有形状。
    - 需要选择至少两个有效的曲线对象（第一个为源曲线，其余为目标曲线），否则会弹出警告。
    - 支持全局撤销功能，可以一次性撤销所有操作。

    Returns:
        None
    """
    # 获取选择的对象
    selected = cmds.ls(sl=True, long=True)
    if len(selected) < 2:
        cmds.warning("请至少选择两个曲线对象（第一个为源曲线，其余为目标曲线）！当前选择数量: {}".format(len(selected)))
        return

    source_curve = selected[0]
    target_curves = selected[1:]

    # 验证源曲线是否为有效曲线
    if not cmds.listRelatives(source_curve, shapes=True, type="nurbsCurve"):
        cmds.warning(f"源曲线 '{source_curve}' 不是有效的 NURBS 曲线！")
        return

    # 验证所有目标曲线是否为有效曲线
    invalid_targets = []
    for curve in target_curves:
        if not cmds.listRelatives(curve, shapes=True, type="nurbsCurve"):
            invalid_targets.append(curve)
    
    if invalid_targets:
        cmds.warning(f"以下目标对象不是有效的 NURBS 曲线：{', '.join(cmds.ls(invalid_targets, shortNames=True))}")
        return

    # 开始撤销块，将所有操作组合为一个可撤销的操作
    cmds.undoInfo(openChunk=True, chunkName="替换曲线形状")
    
    try:
        # 处理每个目标曲线
        processed_targets = []
        for target_curve in target_curves:
            # 获取目标曲线的短名称
            target_short_name = cmds.ls(target_curve, shortNames=True)[0]

            # 复制源曲线并获取其形状
            temp_curve = cmds.duplicate(source_curve, name="temp_curve")[0]
            source_shapes = cmds.listRelatives(temp_curve, shapes=True, fullPath=True)
            if not source_shapes:
                cmds.warning(f"源曲线 '{source_curve}' 没有形状节点！")
                cmds.delete(temp_curve)
                continue

            # 删除目标曲线的现有形状
            target_shapes = cmds.listRelatives(target_curve, shapes=True, fullPath=True)
            if target_shapes:
                cmds.delete(target_shapes)

            # 转移并重命名形状到目标曲线
            for shape in source_shapes:
                new_shape = cmds.rename(shape, f"{target_short_name}Shape#")
                cmds.parent(new_shape, target_curve, relative=True, shape=True)

            # 清理临时对象
            cmds.delete(temp_curve)
            processed_targets.append(target_curve)

        # 选中所有处理过的目标曲线
        if processed_targets:
            cmds.select(processed_targets, replace=True)
            cmds.inViewMessage(amg=f"已成功替换 {len(processed_targets)} 个目标曲线的形状", pos='midCenter', fade=True, fst=1000)
    
    finally:
        # 关闭撤销块，确保即使发生错误也会关闭
        cmds.undoInfo(closeChunk=True)


if __name__ == "__main__":
    trans_curve_shape()