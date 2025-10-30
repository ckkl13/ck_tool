import maya.cmds as cmds

# 创建曲线: shape48
points_shape48 = [
    (-0.25, 0.0, -2.75),
    (0.25, 0.0, -2.75),
    (0.25, 0.0, -0.75),
    (0.5, 0.0, -0.75),
    (0.0, 0.0, 0.0),
    (-0.5, 0.0, -0.75),
    (-0.25, 0.0, -0.75),
    (-0.25, 0.0, -2.75),
]

shape48 = cmds.curve(name='', degree=1, point=points_shape48)

