# 素材管家 by 熊高祖

macOS 上的重复视频/图片查找与素材归档整理工具，Apple Silicon 原生运行。

## 功能

- **极速扫描**：按文件名+大小分组，十万文件秒级出结果
- **完整扫描**：SHA-256 精确去重 + pHash 相似图片检测
- **视频封面**：ffmpeg 自动抽帧生成缩略图
- **安全删除**：隔离区 → 回收站 → 直接删除，三步确认
- **自动归档**：按类型/年月/拍摄设备/GPS位置归类
- **批量重命名**：按拍摄时间或自定义模板
- **结果持久化**：关掉再打开结果还在

## 下载

去 [Releases](../../releases) 下载 zip，解压后双击运行。

## 环境要求

- macOS Apple Silicon（M 系列芯片）
- 视频封面：`brew install ffmpeg`（可选）

## 从源码运行

    python3 -m pip install -r requirements.txt
    python3 run.py
