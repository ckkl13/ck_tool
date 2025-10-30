import maya.cmds as cmds
import math

def create_sphere_controller(ctrl_name, size=1.0):
    """创建球形控制器"""
    # 创建六边形环
    points = [(x * size, y * size, z * size) for x, y, z in [
        (0, 0, -1), (0.5, 0, -0.866), (0.866, 0, -0.5), (1, 0, 0),
        (0.866, 0, 0.5), (0.5, 0, 0.866), (0, 0, 1), (-0.5, 0, 0.866),
        (-0.866, 0, 0.5), (-1, 0, 0), (-0.866, 0, -0.5), (-0.5, 0, -0.866),
        (0, 0, -1)
    ]]
    circle1 = cmds.curve(name=ctrl_name, degree=1, point=points)
    
    # 创建第二个环
    points = [(x * size, y * size, z * size) for x, y, z in [
        (0, -1, 0), (0.5, -0.866, 0), (0.866, -0.5, 0), (1, 0, 0),
        (0.866, 0.5, 0), (0.5, 0.866, 0), (0, 1, 0), (-0.5, 0.866, 0),
        (-0.866, 0.5, 0), (-1, 0, 0), (-0.866, -0.5, 0), (-0.5, -0.866, 0),
        (0, -1, 0)
    ]]
    circle2 = cmds.curve(degree=1, point=points)
    
    # 创建第三个环
    points = [(x * size, y * size, z * size) for x, y, z in [
        (0, -1, 0), (0, -0.866, 0.5), (0, -0.5, 0.866), (0, 0, 1),
        (0, 0.5, 0.866), (0, 0.866, 0.5), (0, 1, 0), (0, 0.866, -0.5),
        (0, 0.5, -0.866), (0, 0, -1), (0, -0.5, -0.866), (0, -0.866, -0.5),
        (0, -1, 0)
    ]]
    circle3 = cmds.curve(degree=1, point=points)
    
    # 合并形状
    cmds.parent(cmds.listRelatives(circle2, shapes=True)[0], circle1, shape=True, relative=True)
    cmds.parent(cmds.listRelatives(circle3, shapes=True)[0], circle1, shape=True, relative=True)
    cmds.delete(circle2, circle3)
    
    return circle1

def create_cube_controller(ctrl_name, size=1.0):
    """创建立方体控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1),
        (1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1), (-1, 1, -1)
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_circle_controller(ctrl_name, size=1.0):
    """创建圆形控制器"""
    ctrl = cmds.circle(
        name=ctrl_name,
        center=(0, 0, 0),
        normal=(1, 0, 0),
        sweep=360,
        radius=size,
        degree=3,
        ut=0,
        tolerance=0.01,
        sections=16,
        constructionHistory=1
    )[0]
    return ctrl

def create_arrow_controller(ctrl_name, size=1.0):
    """创建箭头控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        (0.9999999999999999, 0.0, -1.6653345369377348e-16), 
        (1.6653345369377348e-16, 0.0, 0.9999999999999999), 
        (8.326672684688674e-17, 0.0, 0.49999999999999994), 
        (-1.0000000000000002, 0.0, 0.5000000000000002), 
        (-0.9999999999999998, 0.0, -0.4999999999999998), 
        (-8.326672684688674e-17, 0.0, -0.49999999999999994), 
        (-1.6653345369377348e-16, 0.0, -0.9999999999999999), 
        (0.9999999999999999, 0.0, -1.6653345369377348e-16)
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_gear_controller(ctrl_name, size=1.0):
    """创建齿轮控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        (-1.6653345369377348e-16, 1.8665999999999996, -3.2333999999999996), 
        (-1.6653345369377348e-16, 1.1219999999999999, -3.5444999999999993), 
        (-8.326672684688674e-17, 0.5609999999999999, -5.1), 
        (8.326672684688674e-17, -0.5609999999999999, -5.1), 
        (1.6653345369377348e-16, -1.1219999999999999, -3.5444999999999993), 
        (1.6653345369377348e-16, -1.8665999999999996, -3.2333999999999996), 
        (0.0, -2.5092, -2.7387), 
        (4.440892098500626e-16, -4.136099999999999, -3.0344999999999995), 
        (1.1102230246251565e-15, -4.691999999999998, -2.0655), 
        (1.1102230246251565e-16, -3.6261000000000005, -0.8007), 
        (3.3306690738754696e-16, -3.733199999999999, 0.0), 
        (1.1102230246251565e-16, -3.6261000000000005, 0.8007), 
        (1.1102230246251565e-15, -4.691999999999998, 2.0655), 
        (4.440892098500626e-16, -4.136099999999999, 3.0344999999999995), 
        (0.0, -2.5092, 2.7387), 
        (1.6653345369377348e-16, -1.8665999999999996, 3.2333999999999996), 
        (1.6653345369377348e-16, -1.1219999999999999, 3.5444999999999993), 
        (8.326672684688674e-17, -0.5609999999999999, 5.1), 
        (-8.326672684688674e-17, 0.5609999999999999, 5.1), 
        (-1.6653345369377348e-16, 1.1219999999999999, 3.5444999999999993), 
        (-1.6653345369377348e-16, 1.8665999999999996, 3.2333999999999996), 
        (0.0, 2.5092, 2.7387), 
        (-4.440892098500626e-16, 4.136099999999999, 3.0344999999999995), 
        (-1.1102230246251565e-15, 4.691999999999998, 2.0655), 
        (-1.1102230246251565e-16, 3.6261000000000005, 0.8007), 
        (-3.3306690738754696e-16, 3.733199999999999, 0.0), 
        (-1.1102230246251565e-16, 3.6261000000000005, -0.8007), 
        (-1.1102230246251565e-15, 4.691999999999998, -2.0655), 
        (-4.440892098500626e-16, 4.136099999999999, -3.0344999999999995), 
        (0.0, 2.5092, -2.7387), 
        (-1.6653345369377348e-16, 1.8665999999999996, -3.2333999999999996), 
        (-1.6653345369377348e-16, 1.1219999999999999, -3.5444999999999993), 
        (-8.326672684688674e-17, 0.5609999999999999, -5.1)
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_cone_controller(ctrl_name, size=1.0):
    """创建圆锥控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        [0.5, 0.0, 0.866], [-0.5, 0.0, 0.866], [0.0, 2.0, 0.0], [0.5, 0.0, 0.866], 
        [1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.5, 0.0, -0.866], [1.0, 0.0, 0.0], 
        [0.0, 2.0, 0.0], [-0.5, 0.0, -0.866], [0.5, 0.0, -0.866], [0.0, 2.0, 0.0], 
        [-1.0, 0.0, -0.0], [-0.5, 0.0, -0.866], [0.0, 2.0, 0.0], [-0.5, 0.0, 0.866], 
        [-1.0, 0.0, -0.0]
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_cross_controller(ctrl_name, size=1.0):
    """创建十字形控制器"""
    points = [(-size, 0, 0), (size, 0, 0), (0, 0, 0), (0, -size, 0), (0, size, 0)]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_diamond_controller(ctrl_name, size=1.0):
    """创建钻石形控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), 
        (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), 
        (0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_rectangle_controller(ctrl_name, size=1.0):
    """创建矩形控制器"""
    points = [(x * size, y * size, z * size) for x, y, z in [
        (-1.6653345369377348e-16, -0.5, 0.9999999999999999), 
        (1.6653345369377348e-16, -0.5, -0.9999999999999999), 
        (1.6653345369377348e-16, 0.5, -0.9999999999999999), 
        (-1.6653345369377348e-16, 0.5, 0.9999999999999999), 
        (-1.6653345369377348e-16, -0.5, 0.9999999999999999)
    ]]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_square_controller(ctrl_name, size=1.0):
    """创建正方形控制器"""
    points = [(0, size, size), (0, size, -size), (0, -size, -size), (0, -size, size), (0, size, size)]
    ctrl = cmds.curve(name=ctrl_name, degree=1, point=points)
    return ctrl

def create_custom_controller(ctrl_name, controller_type="sphere", size=1.0):
    """根据控制器类型创建对应的控制器
    
    参数:
        ctrl_name (str): 控制器名称
        controller_type (str): 控制器类型，可选值: sphere, cube, circle, arrow, gear, cone, cross, diamond, rectangle, square
        size (float): 控制器大小

    返回:
        str: 创建的控制器名称
    """
    print(f"DEBUG: controller_shapes.create_custom_controller被调用: 名称={ctrl_name}, 类型={controller_type}, 大小={size}")
    
    controller_functions = {
        "sphere": create_sphere_controller,
        "cube": create_cube_controller,
        "circle": create_circle_controller,
        "arrow": create_arrow_controller,
        "gear": create_gear_controller,
        "cone": create_cone_controller,
        "cross": create_cross_controller,
        "diamond": create_diamond_controller,
        "rectangle": create_rectangle_controller,
        "square": create_square_controller
    }
    
    # 查找对应的创建函数
    create_func = controller_functions.get(controller_type.lower())
    
    # 如果找不到指定类型，默认使用球形
    if not create_func:
        print(f"未知控制器类型: {controller_type}，使用默认类型(sphere)")
        create_func = create_sphere_controller
    else:
        print(f"DEBUG: 使用控制器类型: {controller_type}, 对应函数: {create_func.__name__}")
    
    # 创建控制器
    ctrl = create_func(ctrl_name, size)
    print(f"DEBUG: 控制器已创建: {ctrl}")
    return ctrl

def apply_color_to_controller(ctrl, color_rgb=(1.0, 1.0, 1.0)):
    """为控制器应用颜色
    
    参数:
        ctrl (str): 控制器名称
        color_rgb (tuple): RGB颜色值，范围0-1
    """
    shapes = cmds.listRelatives(ctrl, shapes=True) or []
    for shape in shapes:
        cmds.setAttr(f"{shape}.overrideEnabled", 1)
        cmds.setAttr(f"{shape}.overrideRGBColors", 1)
        cmds.setAttr(f"{shape}.overrideColorRGB", *color_rgb)

def rename_controller_shape(ctrl):
    """重命名控制器的形状节点
    
    参数:
        ctrl (str): 控制器名称
    """
    shapes = cmds.listRelatives(ctrl, shapes=True, fullPath=True) or []
    if shapes:
        shape_name = f"{ctrl}_Shape"
        cmds.rename(shapes[0], shape_name)
        print(f"控制器 '{ctrl}' 的形状节点已重命名为 '{shape_name}'")
        return shape_name
    return None