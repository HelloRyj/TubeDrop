"""Windows 后台入口：使用 console bootloader 保留重定向的 JSON 输出。"""
import sys

from worker import run

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
