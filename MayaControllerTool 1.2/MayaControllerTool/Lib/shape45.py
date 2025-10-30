import maya.cmds as cmds

# 创建曲线: shape45
points_shape45 = [
    (1.0, 0.0, -1.0),
    (-1.0, 0.0, -1.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (1.0, 0.0, -1.0),
    (-1.0, 0.0, -1.0),
    (0.0, 0.0, 0.0),
]

shape45 = cmds.curve(name='', degree=1, point=points_shape45)

