import maya.cmds as cmds

# 创建曲线: primitive_pyramid
points_primitive_pyramid = [
    (0.0, 2.0, 0.0),
    (1.0, 0.0, -1.0),
    (-1.0, 0.0, -1.0),
    (0.0, 2.0, 0.0),
    (-1.0, 0.0, 1.0),
    (1.0, 0.0, 1.0),
    (0.0, 2.0, 0.0),
    (1.0, 0.0, -1.0),
    (1.0, 0.0, 1.0),
    (-1.0, 0.0, 1.0),
    (-1.0, 0.0, -1.0),
]

primitive_pyramid = cmds.curve(name='', degree=1, point=points_primitive_pyramid)

