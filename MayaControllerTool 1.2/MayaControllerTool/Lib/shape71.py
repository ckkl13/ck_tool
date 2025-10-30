import maya.cmds as cmds

# 创建曲线: square
points_square = [
    (-0.5, 0.0, -0.5),
    (-0.5, 0.0, 0.5),
    (0.5, 0.0, 0.5),
    (0.5, 0.0, -0.5),
    (-0.5, 0.0, -0.5),
]

square = cmds.curve(name='', degree=1, point=points_square)

