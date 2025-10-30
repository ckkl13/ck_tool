import maya.cmds as cmds

def reparent_shape_nodes():
    # 获取当前选择
    selection = cmds.ls(selection=True, type="transform")
    if len(selection) < 2:
        cmds.warning("请至少选择两个物体：源物体和目标物体（最后选择的目标）")
        return

    # 最后一个物体作为目标父节点
    target_parent = selection[-1]
    # 除最后一个外的所有物体作为源节点
    source_objects = selection[:-1]

    # 记录成功添加的形状节点数量
    total_shapes_count = 0
    success_count = 0

    # 遍历源物体，复制它们的形状节点并添加到目标物体
    for obj in source_objects:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
        if shapes:
            try:
                # 复制整个物体（包含形状节点）
                duplicated_obj = cmds.duplicate(obj, returnRootsOnly=True)[0]
                # 获取复制出来的形状节点
                dup_shapes = cmds.listRelatives(duplicated_obj, shapes=True, fullPath=True)
                if dup_shapes:
                    # 将复制的形状节点添加到目标物体下
                    cmds.parent(dup_shapes, target_parent, shape=True, add=True)
                    total_shapes_count += len(dup_shapes)
                    success_count += 1
                    print(f"已从 {obj} 复制 {len(dup_shapes)} 个形状节点到 {target_parent}")
                # 删除复制出来的变换节点
                cmds.delete(duplicated_obj)
            except Exception as e:
                cmds.warning(f"复制物体 {obj} 的形状节点失败: {str(e)}")
                print(f"错误详情: {str(e)}")
        else:
            cmds.warning(f"物体 {obj} 下没有找到形状节点")

    # 最终结果
    if success_count > 0:
        cmds.select(target_parent)
        print(f"操作完成：成功从 {success_count} 个物体复制了 {total_shapes_count} 个形状节点到 {target_parent}")
    else:
        cmds.warning("未能成功添加任何形状节点")

if __name__ == "__main__":
    reparent_shape_nodes()