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


def freeze_channels(obj_list):
    """
    Freezes transforms on a list of objects
    """
    if not obj_list:
        return
    try:
        for obj in obj_list:
            if cmds.objExists(obj):
                cmds.makeIdentity(obj, apply=True, rotate=True, scale=True, translate=True)
    except Exception as e:
        logger.warning(f"Failed to freeze transforms. Issue: {str(e)}")


def combine_curves_list(curve_list, convert_bezier_to_nurbs=True):
    """
    Moves the shape objects of all elements in the provided input (curve_list) to a single group
    (essentially combining them under one transform)

    Args:
        curve_list (list): A list of strings with the name of the curves to be combined.
        convert_bezier_to_nurbs (bool, optional): If active, "bezier" curves will automatically be converted to "nurbs".
    Returns:
        str: Name of the generated curve when combining or name of the first curve in the list when only one found.
    """
    function_name = "Combine Curves List"
    try:
        cmds.undoInfo(openChunk=True, chunkName=function_name)
        nurbs_shapes = []
        bezier_shapes = []
        valid_curve_transforms = set()

        for crv in curve_list:
            shapes = cmds.listRelatives(crv, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.objectType(shape) == CURVE_TYPE_BEZIER:
                    bezier_shapes.append(shape)
                    valid_curve_transforms.add(crv)
                if cmds.objectType(shape) == CURVE_TYPE_NURBS:
                    nurbs_shapes.append(shape)
                    valid_curve_transforms.add(crv)

        if not nurbs_shapes and not bezier_shapes:  # No valid shapes
            logger.warning(f"Unable to combine curves. No valid shapes were found under the provided objects.")
            return

        if len(curve_list) == 1:  # Only one curve in provided list
            return curve_list[0]

        if len(bezier_shapes) > 0 and convert_bezier_to_nurbs:
            for bezier in bezier_shapes:
                logger.debug(str(bezier))
                cmds.select(bezier)
                cmds.bezierCurveToNurbs()

        freeze_channels(list(valid_curve_transforms))
        # Re-parent Shapes
        shapes = nurbs_shapes + bezier_shapes
        group = cmds.group(empty=True, world=True, name=curve_list[0])
        cmds.refresh()  # Without a refresh, Maya ignores the freeze operation
        for shape in shapes:
            cmds.select(clear=True)
            cmds.parent(shape, group, relative=True, shape=True)
        # Delete empty transforms
        for transform in valid_curve_transforms:
            children = cmds.listRelatives(transform, children=True) or []
            if not children and cmds.objExists(transform):
                cmds.delete(transform)
        # Clean-up
        combined_curve = cmds.rename(group, curve_list[0])
        if cmds.objExists(combined_curve):
            cmds.select(combined_curve)
        return combined_curve
    except Exception as exception:
        logger.warning(f"An error occurred when combining the curves. Issue: {str(exception)}")
    finally:
        cmds.undoInfo(closeChunk=True, chunkName=function_name)


def selected_curves_combine(convert_bezier_to_nurbs=False, show_bezier_conversion_dialog=True):
    """
    Moves the shape objects of all selected curves under a single group (combining them)

    Args:
        convert_bezier_to_nurbs (bool, optional): If active, the script will not show a dialog when "bezier" curves
                                                  are found and will automatically convert them to nurbs.
        show_bezier_conversion_dialog (bool, optional): If a "bezier" curve is found and this option is active,
                                                        a dialog will ask the user if they want to convert "bezier"
                                                        curves to "nurbs".
    Returns:
        str or None: Name of the generated combined curve. None if it failed to generate it.
    """
    errors = ""
    function_name = "Combine Selected Curves"
    try:
        cmds.undoInfo(openChunk=True, chunkName=function_name)
        selection = cmds.ls(sl=True, absoluteName=True)
        nurbs_shapes = []
        bezier_shapes = []
        valid_curve_transforms = set()

        if len(selection) < 2:
            logger.warning("You need to select at least two curves.")
            return

        for obj in selection:
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            for shape in shapes:
                if cmds.objectType(shape) == CURVE_TYPE_BEZIER:
                    bezier_shapes.append(shape)
                    valid_curve_transforms.add(obj)
                if cmds.objectType(shape) == CURVE_TYPE_NURBS:
                    nurbs_shapes.append(shape)
                    valid_curve_transforms.add(obj)

        if not nurbs_shapes and not bezier_shapes:  # No valid shapes
            logger.warning(f"Unable to combine curves. No valid shapes were found under the provided objects.")
            return

        # Determine if converting Bezier curves
        if len(bezier_shapes) > 0 and show_bezier_conversion_dialog:
            user_input = cmds.confirmDialog(
                title="Bezier curve detected!",
                message="A bezier curve was found in your selection.\n"
                "Would you like to convert Bezier to NURBS before combining?",
                button=["Yes", "No"],
                defaultButton="Yes",
                cancelButton="No",
                dismissString="No",
                icon="warning",
            )
            convert_bezier_to_nurbs = True if user_input == "Yes" else False

        # Freeze Curves
        freeze_channels(list(valid_curve_transforms))

        # Combine
        combined_crv = combine_curves_list(selection, convert_bezier_to_nurbs=convert_bezier_to_nurbs)
        sys.stdout.write(f'\nSelected curves were combined into: "{combined_crv}".')
        cmds.select(combined_crv)
        return combined_crv

    except Exception as e:
        errors += str(e) + "\n"
        cmds.warning("An error occurred when combining the curves. Open the script editor for more information.")
    finally:
        cmds.undoInfo(closeChunk=True, chunkName=function_name)
    if errors != "":
        print("######## Errors: ########")
        print(errors)


def main():
    """
    Main function to execute when script is run directly
    """
    selected_curves_combine()


if __name__ == "__main__":
    main()