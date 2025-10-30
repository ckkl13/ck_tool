"""
拖放这个文件到Maya视口中以安装CK工具
Drag and drop this file into the Maya viewport to install CK Tool
"""

import maya.cmds as cmds
import sys
import os
from importlib import import_module, reload


def find_file_in_directory(directory, filename):
    """
    在指定目录中查找指定文件名的文件。
    """
    directory = os.path.normpath(directory)
    for root, dirs, files in os.walk(directory):
        if filename in files:
            return os.path.normpath(os.path.join(root, filename))
    return None


def add_to_shelf(script_path, icon_path):
    """将工具按钮添加到Maya工具架，使用动态导入"""
    try:
        current_shelf = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
        if not current_shelf:
            raise ValueError("未找到活动工具架")

        module_name = "ck_tool"
        script_dir = os.path.dirname(script_path).replace("\\", "\\\\")
        # 热重载版命令：先关闭旧窗口→清理模块→重新导入并启动
        command_script = f'''import maya.cmds as cmds
import sys, importlib

# 确保工具目录在路径中
script_dir = r"{script_dir}"
if script_dir not in sys.path:
    sys.path.append(script_dir)

# 尝试关闭已打开的综合工具窗口，避免旧信号引用
try:
    from ui import CombinedTool
    CombinedTool.get_instance().close()
except Exception:
    pass

# 失效缓存并清理相关模块，确保干净重载
importlib.invalidate_caches()
for _name in list(sys.modules):
    if _name.startswith(('ck_tool','ui','controllers','tool','external_reference')):
        sys.modules.pop(_name, None)

# 重新导入并启动
try:
    import ck_tool
    ck_tool.run_tool()
except Exception as e:
    cmds.error(f"启动CK Tool失败: {{e}}")
'''
        # 如果已存在同名按钮，则更新其命令与图标；否则创建新按钮
        existing_btn = None
        try:
            children = cmds.shelfLayout(current_shelf, q=True, childArray=True) or []
            for child in children:
                # 过滤出shelfButton类型的UI对象
                try:
                    lbl = cmds.shelfButton(child, q=True, label=True)
                    ann = cmds.shelfButton(child, q=True, annotation=True)
                except Exception:
                    continue
                if lbl == 'CK_Tool' or ann == 'CK Tool':
                    existing_btn = child
                    break
        except Exception:
            pass

        if existing_btn:
            cmds.shelfButton(existing_btn, e=True,
                             command=command_script,
                             image1=icon_path,
                             annotation="CK Tool",
                             label="CK_Tool")
            print(f"已更新现有工具架按钮: {existing_btn}")
        else:
            cmds.shelfButton(
                annotation="CK Tool",
                label="CK_Tool",
                image1=icon_path,
                command=command_script,
                sourceType="python",
                style="iconOnly",
                width=35,
                height=35,
                parent=current_shelf
            )
            print(f"成功将 'CK_Tool' 添加到工具架: {current_shelf}")
        return True
    except Exception as e:
        cmds.warning(f"添加到工具架失败: {e}")
        return False


def create_installer_gui():
    """创建安装器GUI界面"""
    # 窗口尺寸和标题
    window_width = 450
    window_height = 350
    
    # 如果窗口已存在则删除
    if cmds.window("ckToolInstallerWindow", exists=True):
        cmds.deleteUI("ckToolInstallerWindow")
    
    # 创建主窗口
    window = cmds.window("ckToolInstallerWindow", title="CK Tool 安装向导", 
                         width=window_width, height=window_height, sizeable=False,
                         backgroundColor=[0.2, 0.2, 0.2])
    
    # 主布局
    main_layout = cmds.columnLayout(adjustableColumn=True, columnOffset=["both", 15], 
                                   rowSpacing=10, columnAttach=["both", 15])
    
    # 标题区域
    cmds.separator(height=10, style="none")
    cmds.text(label="CK Tool 安装向导", font="boldLabelFont", height=40, backgroundColor=[0.2, 0.3, 0.4])
    cmds.separator(height=1, style="in")
    cmds.separator(height=10, style="none")
    
    # 图标区域（如果有图标）
    icon_placeholder = cmds.iconTextStaticLabel(style='iconOnly', 
                                              image1='menuIconHelp.png',
                                              width=64, height=64)
    
    # 信息区域
    cmds.separator(height=10, style="none")
    cmds.text(label="欢迎使用CK Tool安装向导！", align="center", font="boldLabelFont")
    cmds.separator(height=10, style="none")
    
    # 说明文本区域
    cmds.frameLayout(label="安装说明", collapsable=False, 
                    marginWidth=5, marginHeight=5, width=window_width-30)
    cmds.columnLayout(adjustableColumn=True, columnOffset=["both", 5], rowSpacing=5)
    cmds.text(label="• 本安装向导将帮助您安装CK工具到Maya当前活动的工具架中", align="left", wordWrap=True)
    cmds.text(label="• 您需要选择包含tool.jpg和ck_tool.py的文件夹", align="left", wordWrap=True)
    cmds.text(label="• 安装完成后，您可以直接从Maya工具架访问该工具", align="left", wordWrap=True)
    cmds.setParent('..')
    cmds.setParent('..')
    
    # 文件夹选择区域
    cmds.frameLayout(label="文件选择", collapsable=False,
                    marginWidth=5, marginHeight=5, width=window_width-30)
    cmds.columnLayout(adjustableColumn=True, columnOffset=["both", 5], rowSpacing=5)
    
    # 文件夹路径显示
    folder_text = cmds.textFieldButtonGrp(
        label="工具文件夹: ", 
        buttonLabel="浏览...",
        columnWidth=[(1, 80), (2, 230), (3, 60)],
        adjustableColumn=2,
        buttonCommand=lambda: browse_folder(folder_text)
    )
    
    # 状态信息
    file_status = cmds.text(label="请选择包含工具文件的文件夹", align="left")
    cmds.setParent('..')
    cmds.setParent('..')
    
    # 状态区域
    cmds.separator(height=10, style="none")
    status_text = cmds.text(label="准备就绪，请选择文件夹后点击\"安装\"按钮", align="center")
    cmds.separator(height=15, style="none")
    
    # 按钮区域
    cmds.separator(height=1, style="in")
    button_row = cmds.rowLayout(numberOfColumns=2, columnWidth2=[window_width/2-20, window_width/2-20], 
                              columnAlign2=["center", "center"], columnAttach=[(1, "both", 10), (2, "both", 10)])
    
    # 安装按钮
    install_btn = cmds.button(label="安装", width=window_width/2-20, height=35, 
                             backgroundColor=[0.2, 0.4, 0.6],
                             command=lambda x: install_with_feedback(folder_text, file_status, status_text))
    
    # 取消按钮                        
    cancel_btn = cmds.button(label="取消", width=window_width/2-20, height=35, 
                            command=lambda x: cmds.deleteUI(window))
    
    # 版权信息
    cmds.setParent(main_layout)
    cmds.separator(height=10, style="none")
    current_year = cmds.about(currentTime=True)
    year_str = str(current_year).split("-")[0] if "-" in str(current_year) else "2024"
    cmds.text(label="CK Tool © " + year_str, align="center", font="smallFixedWidthFont")
    
    # 显示窗口
    cmds.showWindow(window)
    
    # 浏览文件夹函数
    def browse_folder(text_field):
        folder = cmds.fileDialog2(caption="选择包含工具文件的文件夹", fileMode=3, okCaption="选择")
        if folder and len(folder) > 0:
            cmds.textFieldButtonGrp(text_field, edit=True, text=folder[0])
            validate_folder(folder[0], file_status)
    
    # 验证选择的文件夹是否包含必要文件
    def validate_folder(folder_path, status_field):
        if not folder_path:
            cmds.text(status_field, edit=True, label="请选择文件夹", backgroundColor=[0.5, 0.0, 0.0])
            return False
            
        # 查找工具文件
        icon_path = find_file_in_directory(folder_path, "tool.jpg")
        script_path = find_file_in_directory(folder_path, "ck_tool.py")
        
        if not icon_path:
            cmds.text(status_field, edit=True, label="错误: 未找到tool.jpg文件", backgroundColor=[0.5, 0.0, 0.0])
            return False
        
        if not script_path:
            cmds.text(status_field, edit=True, label="错误: 未找到ck_tool.py文件", backgroundColor=[0.5, 0.0, 0.0])
            return False
        
        # 所有文件都找到了
        cmds.text(status_field, edit=True, label="文件验证成功，可以安装", backgroundColor=[0.0, 0.3, 0.0])
        return True
    
    # 安装逻辑函数
    def install_with_feedback(folder_field, file_status_field, status_label):
        try:
            # 获取用户选择的文件夹路径
            folder_path = cmds.textFieldButtonGrp(folder_field, query=True, text=True)
            
            # 验证文件夹
            if not validate_folder(folder_path, file_status_field):
                cmds.text(status_label, edit=True, label="安装失败: 文件验证未通过", backgroundColor=[0.5, 0.0, 0.0])
                return
            
            # 更新状态
            cmds.text(status_label, edit=True, label="正在安装中...", backgroundColor=[0.3, 0.3, 0.0])
            
            # 查找所需文件
            icon_path = find_file_in_directory(folder_path, "tool.jpg")
            script_path = find_file_in_directory(folder_path, "ck_tool.py")
            
            # 将脚本路径添加到sys.path
            script_dir = os.path.dirname(script_path)
            if script_dir not in sys.path:
                sys.path.append(script_dir)
            
            # 添加到工具架
            if add_to_shelf(script_path, icon_path):
                # 显示成功信息
                cmds.confirmDialog(title="安装成功", 
                                  message="CK工具已成功添加到当前工具架！\n现在可以直接从工具架启动该工具。", 
                                  button=["确定"], defaultButton="确定", icon="information")
                
                # 更新状态
                cmds.text(status_label, edit=True, label="安装成功！", backgroundColor=[0.0, 0.3, 0.0])
                
                # 延时关闭窗口
                cmds.evalDeferred(lambda: close_window_delayed(window), lowestPriority=True)
            else:
                cmds.text(status_label, edit=True, label="添加到工具架失败", backgroundColor=[0.5, 0.0, 0.0])
                raise RuntimeError("添加到工具架失败")
                
        except Exception as e:
            cmds.text(status_label, edit=True, label=f"安装失败: {e}", backgroundColor=[0.5, 0.0, 0.0])
            cmds.confirmDialog(title="安装错误", message=f"安装过程中发生错误: {e}", 
                              button=["确定"], defaultButton="确定", icon="critical")
            cmds.error(f"安装过程中发生错误: {e}")
    
    # 延时关闭窗口函数
    def close_window_delayed(win):
        # 等待2秒后关闭窗口
        cmds.pause(seconds=2)
        if cmds.window(win, exists=True):
            cmds.deleteUI(win)


def onMayaDroppedPythonFile(*args):
    """
    当脚本被拖入 Maya 的视口时执行的函数。
    这是 Maya 拖放机制的入口点，名称不可更改。
    """
    # 检查 Python 版本
    if sys.version_info.major < 3:
        user_version = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        error = "不兼容的Python版本。需要Python 3及以上版本。当前版本: " + user_version
        raise ImportError(error)

    # 初始反馈
    print("_" * 50)
    print("正在初始化CK Tool安装向导...")

    # 获取拖放位置并添加到 sys.path
    parent_dir = os.path.dirname(__file__)
    print('拖放位置: "' + parent_dir + '"')
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # 启动安装器GUI
    print("启动安装向导界面...")
    create_installer_gui()
    print("_" * 50)


# 如果脚本直接运行（不是通过拖放）
if __name__ == "__main__":
    create_installer_gui()
