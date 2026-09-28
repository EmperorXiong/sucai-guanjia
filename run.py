#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去重归档助手 启动入口。

用法：python3 run.py
打包后：双击 去重归档助手.app
"""
import multiprocessing
import sys
import os

# 让 macOS 以 spawn 方式启动多进程哈希时能找到主入口
if __name__ == "__main__":
    multiprocessing.freeze_support()
    # 把项目根目录加入模块搜索路径（兼容直接运行与打包两种方式）
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    from dupe_organizer.app import main
    main()
