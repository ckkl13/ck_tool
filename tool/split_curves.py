import maya.cmds as cmds
import logging
import sys

# Logging Setup
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
CURVE_TYPE_NURBS = "nurbsCurve"
CURVE_TYPE_BEZIER = "bezierCurve"
CURVE_TYPES = [CURVE_TYPE_NURBS, CURVE_TYPE_BEZIER]


def get_short_name(obj_name):
    """
    Get the short name of an object from its full DAG path
    
    Args:
        obj_name (str): The full path of the object
        
    Returns:
        str: The short name of the object
    """
    if not obj_name or not isinstance(obj_name, str):
        return obj_name
    return obj_name.split('|')[-1]


def separate_curve_shapes_into_transforms(curve_name):
    """
    Moves the shapes instead of a curve to individual transforms (separating curves)
    Args:
        curve_name (str): Name of the transform holding multiple shapes.
    Returns:
        list or None: List of transforms generated out of the operation or None if the operation failed.
    """
    function_name = "Separate Curves"
    try:
        cmds.undoInfo(openChunk=True, chunkName=function_name)
        nurbs_shapes = []
        bezier_shapes = []
        parent_transforms = []

        if not curve_name or not isinstance(curve_name, str) or not cmds.objExists(curve_name):
            logger.warning(f'Unable to separate curve shapes. Missing provided curve: "{curve_name}".')
            return

        new_transforms = []

        shapes = cmds.listRelatives(curve_name, shapes=True, fullPath=True) or []
        for shape in shapes:
            if cmds.objectType(shape) == CURVE_TYPE_BEZIER:
                bezier_shapes.append(shape)
            if cmds.objectType(shape) == CURVE_TYPE_NURBS:
                nurbs_shapes.append(shape)

        if not nurbs_shapes and not bezier_shapes:  # No valid shapes
            logger.warning(f"Unable to separate curves. No valid shapes were found under the provided object.")
            return

        if len(shapes) == 1:  # Only one curve in provided object
            logger.debug("Provided curve contains only one shape. Nothing to separate.")
            return curve_name

        for obj in nurbs_shapes + bezier_shapes:
            parent = cmds.listRelatives(obj, parent=True) or []
            for par in parent:
                if par not in parent_transforms:
                    parent_transforms.append(par)
                cmds.makeIdentity(par, apply=True, rotate=True, scale=True, translate=True)
            group = cmds.group(empty=True, world=True, name=get_short_name(obj).replace("Shape", ""))
            cmds.parent(obj, group, relative=True, shape=True)
            new_transforms.append(group)

        for obj in parent_transforms:
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            if cmds.objExists(obj) and cmds.objectType(obj) == "transform" and len(shapes) == 0:
                cmds.delete(obj)
        return new_transforms
    except Exception as e:
        logger.warning(f"An error occurred when separating the curve. Issue: {e}")
    finally:
        cmds.undoInfo(closeChunk=True, chunkName=function_name)


def selected_curves_separate():
    """
    Moves the shapes instead of a curve to individual transforms (separating curves)
    Returns:
        list: List of transforms generated out of the operation (each separated shape goes under a new transform)
    """
    function_name = "Separate Selected Curves"
    try:
        cmds.undoInfo(openChunk=True, chunkName=function_name)
        selection = cmds.ls(sl=True, long=True) or []

        if len(selection) < 1:
            logger.warning("You need to select at least one curve.")
            return

        parent_transforms = []
        for obj in selection:
            nurbs_shapes = []
            bezier_shapes = []
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.objectType(shape) == CURVE_TYPE_BEZIER:
                    bezier_shapes.append(shape)
                if cmds.objectType(shape) == CURVE_TYPE_NURBS:
                    nurbs_shapes.append(shape)

            curve_shapes = nurbs_shapes + bezier_shapes
            if len(curve_shapes) == 0:
                logger.warning(f'Unable to separate "{obj}". No valid shapes were found under this object.')
            elif len(curve_shapes) > 1:
                parent_transforms.extend(separate_curve_shapes_into_transforms(obj))
            else:
                cmds.warning("The selected curve contains only one shape.")

        cmds.select(parent_transforms)
        sys.stdout.write("\n" + str(len(parent_transforms)) + " shapes extracted.")
        return parent_transforms
    except Exception as e:
        logger.warning(f"An error occurred when separating the curves. Issue: {e}")
    finally:
        cmds.undoInfo(closeChunk=True, chunkName=function_name)


def main():
    """
    Main function to execute when script is run directly
    """
    selected_curves_separate()


if __name__ == "__main__":
    main()