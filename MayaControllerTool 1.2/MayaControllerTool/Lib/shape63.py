import maya.cmds as cmds

# 创建曲线: icon_cursor
points_icon_cursor = [
    (-4.412, -0.0, -1.537),
    (-2.145, 0.0, 0.73),
    (-5.0, 0.0, 3.562),
    (-3.562, 0.0, 5.0),
    (-0.73, 0.0, 2.145),
    (1.537, 0.0, 4.412),
    (5.0, -0.0, -5.0),
    (-4.412, -0.0, -1.537),
    (-2.145, 0.0, 0.73),
    (-5.0, 0.0, 3.562),
]

icon_cursor = cmds.curve(name='', degree=1, point=points_icon_cursor)

