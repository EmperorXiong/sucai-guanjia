# -*- coding: utf-8 -*-
"""整理归类模块：按类型/年月/设备/位置多层归档，支持重命名规则、冲突策略、CSV 日志。"""
from __future__ import annotations

import csv
import os
import shutil
import urllib.request
from datetime import datetime

from . import engine

_city_cache = {}


def get_exif_date(path: str) -> datetime:
    if engine.kind_of(path) == "image":
        try:
            from PIL import Image
            with Image.open(path) as im:
                ex = im.getexif()
                raw = ex.get(36867) or ex.get(36868)
                if raw:
                    return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    try:
        return datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return datetime.now()


def get_exif_model(path: str) -> str:
    try:
        from PIL import Image
        with Image.open(path) as im:
            m = im.getexif().get(272)
            if m:
                return str(m).strip().replace("\x00", "")
    except Exception:
        pass
    return ""


def get_gps_deg(path: str):
    """返回 (lat, lon) 十进制度，失败 None。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            gps = im.getexif().get_ifd(0x8825)

            def deg(coord, ref):
                d, m, s = coord
                v = float(d) + float(m) / 60 + float(s) / 3600
                return -v if ref in ("S", "W") else v

            lat = deg(gps[2], gps[1])
            lon = deg(gps[4], gps[3])
            return round(lat, 6), round(lon, 6)
    except Exception:
        return None


def gps_city(lat: float, lon: float = 0.0):
    """离线失败时返回空串；用 Nominatim 反查城市，结果按坐标缓存。"""
    key = (round(float(lat), 2), round(float(lon), 2))
    if key in _city_cache:
        return _city_cache[key]
    city = ""
    try:
        url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
               "&lat=%.5f&lon=%.5f&zoom=10&accept-language=zh" % (lat, lon))
        req = urllib.request.Request(url, headers={"User-Agent": "DupeOrganizer/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            import json
            data = json.load(r)
        a = data.get("address", {})
        city = (a.get("city") or a.get("town") or a.get("municipality")
                or a.get("county") or a.get("state") or "")
    except Exception:
        city = ""
    _city_cache[key] = city
    return city


def safe_name(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()


def unique_path(dest: str, conflict: str = "rename") -> str:
    if not os.path.exists(dest) or conflict == "overwrite":
        return dest
    if conflict == "skip":
        return ""  # 空串表示跳过
    base, ext = os.path.splitext(dest)
    i = 1
    while True:
        cand = "%s (%d)%s" % (base, i, ext)
        if not os.path.exists(cand):
            return cand
        i += 1


def new_filename(f, mode="keep", template="") -> str:
    root, ext = os.path.splitext(os.path.basename(f.path))
    if mode == "keep":
        return os.path.basename(f.path)
    d = get_exif_date(f.path)
    if mode == "time":
        return d.strftime("%Y%m%d_%H%M%S") + ext
    if mode == "template":
        model = get_exif_model(f.path) if f.kind == "image" else ""
        repl = {
            "{date}": d.strftime("%Y%m%d_%H%M%S"),
            "{year}": d.strftime("%Y"), "{month}": d.strftime("%m"),
            "{day}": d.strftime("%d"), "{time}": d.strftime("%H%M%S"),
            "{model}": model or "未知设备", "{camera}": model or "未知设备",
            "{original}": root,
        }
        s = template or "{original}"
        for k, v in repl.items():
            s = s.replace(k, v)
        return safe_name(s) + ext
    return os.path.basename(f.path)


def folder_parts(f, by_type=True, by_date=True, by_device=False, by_location=False):
    parts = []
    if by_type:
        parts.append("图片" if f.kind == "image" else "视频")
    if by_date:
        parts.append(get_exif_date(f.path).strftime("%Y-%m"))
    if by_device and f.kind == "image":
        m = get_exif_model(f.path)
        if m:
            parts.append("设备_" + safe_name(m))
    if by_location and f.kind == "image":
        gps = get_gps_deg(f.path)
        if gps:
            city = gps_city(gps[0], gps[1])
            if city:
                parts.append("位置_" + safe_name(city))
    return parts


def plan_organize(files, dest_root, by_type=True, by_date=True,
                  by_device=False, by_location=False,
                  rename_mode="keep", rename_template="",
                  conflict="rename", on_progress=None, cancel=None):
    """生成 (源路径, 目标路径) 计划。不实际移动。"""
    plan = []
    used = {}  # 计划内已用目标路径，避免两个文件撞名
    for i, f in enumerate(files, 1):
        if cancel is not None and cancel.is_set():
            break
        parts = folder_parts(f, by_type, by_date, by_device, by_location)
        folder = os.path.join(dest_root, *parts) if parts else dest_root
        name = new_filename(f, rename_mode, rename_template)
        dest = os.path.join(folder, name)
        dest = unique_path(dest, conflict)
        # 计划内再去一次重（两个文件同名时按顺序加序号）
        if dest:
            while dest in used:
                base, ext = os.path.splitext(dest)
                used[dest] = used.get(dest, 0) + 1
                dest = "%s (%d)%s" % (base, used[dest], ext)
            used[dest] = 0
            plan.append((f.path, dest))
        if on_progress:
            on_progress(i, len(files))
    return plan


def execute_plan(plan, copy_mode=False, on_progress=None, on_error=None, cancel=None):
    """执行计划，返回 (成功数, 失败数, 日志行)。"""
    import datetime
    ok = fail = 0
    logs = []
    total = len(plan)
    for i, (src, dest) in enumerate(plan, 1):
        if cancel is not None and cancel.is_set():
            break
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if copy_mode:
                shutil.copy2(src, dest)
            else:
                shutil.move(src, dest)
            ok += 1
            logs.append([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "复制" if copy_mode else "移动", src, dest])
        except Exception as e:  # noqa: BLE001
            fail += 1
            if on_error:
                on_error(src, dest, e)
        if on_progress:
            on_progress(i, total)
    return ok, fail, logs


def write_log(dest_root, logs):
    """把操作日志写成 UTF-8-SIG CSV（Excel 可直接打开中文）。"""
    os.makedirs(dest_root, exist_ok=True)
    p = os.path.join(dest_root, "操作日志_%s.csv"
                     % datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["时间", "操作", "源路径", "目标路径"])
        for row in logs:
            w.writerow(row)
    return p
