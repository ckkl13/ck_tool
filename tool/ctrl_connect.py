import maya.cmds as cmds

CTRL_COLORS = {'m': 17,
               'l': 6,
               'r': 13}

SUB_COLORS = {'m': 25,
              'l': 15,
              'r': 4}

# get selected nurbs curve as controller
ctrls = cmds.ls(selection=True)

# loop in each ctrl and create hierarchy
for ctrl in ctrls:
    # get name parts
    name_parts = ctrl.split('_')

    # create zero group
    zero = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'zero_'))
    # create driven group
    driven = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'driven_'), parent=zero)
    # create connect group
    connect = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'connect_'), parent=driven)
    # create offset group
    offset = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'offset_'), parent=connect)

    # snap to control position
    cmds.matchTransform(zero, ctrl, position=True, rotation=True)

    # parent control to offset group
    cmds.parent(ctrl, offset)

    # freeze transformation for controller
    cmds.makeIdentity(ctrl, apply=True, scale=True)
    # delete history
    cmds.select(ctrl)
    cmds.DeleteHistory()

    # duplicate ctrl as sub control
    sub = cmds.duplicate(ctrl, name=ctrl.replace(name_parts[2], name_parts[2] + 'Sub'))[0]
    cmds.parent(sub, ctrl)
    cmds.setAttr(sub + '.scale', 0.9, 0.9, 0.9)
    cmds.makeIdentity(sub, apply=True, scale=True)

    # create output group
    output = cmds.createNode('transform', name=ctrl.replace('ctrl_', 'output_'), parent=ctrl)

    # connect attrs
    cmds.connectAttr(sub + '.translate', output + '.translate')
    cmds.connectAttr(sub + '.rotate', output + '.rotate')
    cmds.connectAttr(sub + '.rotateOrder', output + '.rotateOrder')

    # show rotate order
    cmds.setAttr(ctrl + '.rotateOrder', channelBox=True)
    cmds.setAttr(sub + '.rotateOrder', channelBox=True)

    # add sub vis attr
    cmds.addAttr(ctrl, longName='subCtrlVis', attributeType='bool')
    cmds.setAttr(ctrl + '.subCtrlVis', channelBox=True)

    # connect sub vis
    cmds.connectAttr(ctrl + '.subCtrlVis', sub + '.visibility')

    # lock hide unused attrs
    for attr in ['scaleX', 'scaleY', 'scaleZ', 'visibility']:
        for ctrl_node in [ctrl, sub]:
            cmds.setAttr('{}.{}'.format(ctrl_node, attr), keyable=False, channelBox=False, lock=True)

    # set color
    for ctrl_node, col_idx in zip([ctrl, sub], [CTRL_COLORS[name_parts[1]], SUB_COLORS[name_parts[1]]]):
        # get shape node
        shape_node = cmds.listRelatives(ctrl_node, shapes=True)[0]
        # set color
        cmds.setAttr(shape_node + '.overrideEnabled', 1)
        cmds.setAttr(shape_node + '.overrideColor', col_idx)
