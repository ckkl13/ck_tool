import maya.cmds as cmds

# 创建曲线: locator
points_locator = [
    (-1.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
]

locator = cmds.curve(name='', degree=1, point=points_locator)

