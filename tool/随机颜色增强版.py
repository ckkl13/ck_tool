# -*- coding: utf-8 -*-
import maya.cmds as cmds
import random
import colorsys

def generate_golden_ratio_color():
    """
    使用黄金比例生成均匀随机颜色
    原理：每次在色相环上偏移黄金比例 (≈0.618)，能让颜色分布均匀。
    """
    golden_ratio = 0.61803398875
    # hue 的随机起点 + 黄金比例偏移
    h = (random.random() + golden_ratio) % 1.0
    s = random.uniform(0.4, 0.9)
    v = random.uniform(0.5, 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (round(r, 3), round(g, 3), round(b, 3))


def get_object_type(obj):
    """返回物体类型"""
    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
    if not shapes:
        return cmds.nodeType(obj)
    shape_type = cmds.nodeType(shapes[0])
    if shape_type in ['mesh', 'nurbsSurface', 'nurbsCurve', 'locator']:
        return shape_type
    return 'other'


def assign_random_colors_golden():
    """
    为选中的物体分配基于黄金比例的随机颜色
    支持：mesh、nurbsSurface、curve、locator
    """
    selected_objects = cmds.ls(selection=True, long=True)
    if not selected_objects:
        cmds.warning("请先选择物体")
        return

    cmds.undoInfo(openChunk=True)
    processed_count = 0
    shader_cache = {}

    try:
        for obj in selected_objects:
            obj_type = get_object_type(obj)
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            if not shapes:
                continue

            # 生成颜色
            rgb = generate_golden_ratio_color()

            if obj_type in ['mesh', 'nurbsSurface']:
                # 缓存相同颜色的材质
                if rgb in shader_cache:
                    shading_group = shader_cache[rgb]
                else:
                    shader_name = cmds.shadingNode('lambert', asShader=True, name="goldenColor_mat#")
                    cmds.setAttr(shader_name + ".color", *rgb, type="double3")

                    shading_group = cmds.sets(renderable=True, noSurfaceShader=True,
                                              empty=True, name=shader_name + "SG")
                    cmds.connectAttr(shader_name + ".outColor", shading_group + ".surfaceShader", f=True)
                    shader_cache[rgb] = shading_group

                for shape in shapes:
                    if cmds.nodeType(shape) in ['mesh', 'nurbsSurface']:
                        cmds.sets(shape, e=True, forceElement=shading_group)
                        processed_count += 1

            else:
                # 对曲线和定位器使用 override
                for shape in shapes:
                    try:
                        cmds.setAttr(shape + ".overrideEnabled", 1)
                        cmds.setAttr(shape + ".overrideRGBColors", 1)
                        cmds.setAttr(shape + ".overrideColorRGB", *rgb, type='double3')
                        processed_count += 1
                    except:
                        cmds.warning("无法设置颜色: {}".format(shape))
    finally:
        cmds.undoInfo(closeChunk=True)

    cmds.select(clear=True)
    print("已为 {} 个 shape 赋予 Golden Ratio 随机颜色".format(processed_count))


# 执行
if __name__ == "__main__":
    assign_random_colors_golden()
