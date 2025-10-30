import maya.cmds as cmds

def tag_joint(jnt):
    """
    Tag joint based on its name.

    Args:
        jnt (str): Joint name.
    """
    # Split the joint name into parts
    name_parts = jnt.split('_')

    # Determine the side index based on naming convention
    side_index = 0  # Default: center
    if len(name_parts) > 1:
        if name_parts[1] == 'l':
            side_index = 1  # Left
        elif name_parts[1] == 'r':
            side_index = 2  # Right

    # Construct the otherType attribute value safely
    other_type = ''
    if len(name_parts) > 2:
        other_type = '_'.join(name_parts[2:])

    # Set attributes on the joint
    cmds.setAttr(jnt + '.side', side_index)
    cmds.setAttr(jnt + '.type', 18)  # 18 corresponds to "other"
    cmds.setAttr(jnt + '.otherType', other_type, type='string')

# List all joints in the scene matching a flexible pattern
jnts = cmds.ls(type='joint')

# Tag each joint
for j in jnts:
    try:
        tag_joint(j)
    except Exception as e:
        print(f"Failed to tag joint {j}: {e}")

# Confirm completion
cmds.confirmDialog(title="Success", message="Joints tagged successfully!", button=["OK"])
