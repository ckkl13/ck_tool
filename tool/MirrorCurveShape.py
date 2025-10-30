# coding=utf-8
import maya.cmds as cmds


def MirrorCurveShape():
    """
    镜像两曲线形状：
    - 选择两个曲线，将第一个曲线的形状沿 X 轴镜像到第二个。
    - 如果控制点数量不一致或未选择两个对象，会弹出警告。
    - 支持全局撤销。
    """
    # 打开撤销块
    cmds.undoInfo(openChunk=True)
    try:
        # 获取选择的两个曲线对象
        con, con_dist = cmds.ls(sl=True)
    except ValueError:
        cmds.warning(u'请选择两根需要镜像的曲线.')
        return
    finally:
        # 如果发生异常，确保关闭撤销块
        cmds.undoInfo(closeChunk=True)

    # 打开新的撤销块以包含后续操作
    cmds.undoInfo(openChunk=True)
    try:
        # 检查两曲线的控制点数量是否一致
        if not cmds.getAttr(con + '.controlPoints', size=True) == cmds.getAttr(con_dist + '.controlPoints', size=True):
            cmds.warning(u'所选控制器CV点的数量不相同.')
            return

        # 遍历控制点并进行镜像
        for i in range(cmds.getAttr(con + '.controlPoints', size=True)):
            # 获取源曲线控制点的位置
            P = cmds.pointPosition(con + '.controlPoints[%s]' % i)
            # 将目标曲线的控制点沿 X 轴镜像（X 取反，Y 和 Z 不变）
            cmds.xform(con_dist + '.controlPoints[%s]' % i, t=(-1 * P[0], P[1], P[2]), ws=True)

        print(u"曲线形状已成功沿 X 轴镜像.")
    except Exception as e:
        cmds.warning(u"镜像曲线形状失败: %s" % str(e))
        raise  # 抛出异常以便调试
    finally:
        # 关闭撤销块
        cmds.undoInfo(closeChunk=True)


# 可选：直接运行函数
if __name__ == "__main__":
    MirrorCurveShape()