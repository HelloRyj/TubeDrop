"""Windows 无控制台入口，保留可操作的启动错误提示。"""
import ctypes
import sys

try:
    from app import main
    sys.exit(main())
except Exception as error:
    ctypes.windll.user32.MessageBoxW(None, f'无法启动 TubeDrop：\n{error}\n请尝试重新安装。', 'TubeDrop', 0x10)
    raise
