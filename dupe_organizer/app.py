# -*- coding: utf-8 -*-
"""去重归档助手 —— PySide6 图形界面（macOS 深色主题）。"""
from __future__ import annotations

import os, subprocess, sys, threading, time
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox, QComboBox, QProgressBar,
    QLabel, QFileDialog, QMessageBox, QGroupBox, QPlainTextEdit, QStyle,
    QDialog, QLineEdit, QSlider, QTreeWidget, QTreeWidgetItem, QSpinBox, QRadioButton,
)

from . import classifier, engine

APP_TITLE = "素材管家 by 熊高祖"

# macOS 深色配色
BG = "#1c1c1e"
CARD = "#2c2c2e"
INPUT = "#1a1a1c"
BORDER = "#48484a"
TEXT = "#f5f5f7"
DIM = "#98989d"
ACCENT = "#0A84FF"
DANGER = "#ff453a"

STYLE = f"""
QMainWindow, QDialog, QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QTabWidget::pane {{ border: none; background: {BG}; }}
QTabBar::tab {{
    background: transparent; color: {DIM}; padding: 9px 20px; border: none; font-size: 14px;
}}
QTabBar::tab:selected {{ background: {CARD}; border-radius: 8px; color: white; }}
QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    margin-top: 8px; padding-top: 20px; font-weight: 600; color: white;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; background: {CARD}; }}
QPushButton {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 14px; color: {TEXT};
}}
QPushButton:hover {{ background: #3a3a3c; }}
QPushButton:disabled {{ color: #6b6b6b; background: {INPUT}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; padding: 9px 16px; }}
QPushButton#primary:hover {{ background: #2b9bff; }}
QPushButton#danger {{ background: {DANGER}; border: none; color: white; font-weight: 600; }}
QPushButton#danger:hover {{ background: #ff6b60; }}
/* ===== 统一输入控件 ===== */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QListWidget {{
    background: #1E1E1E; border: 1px solid #3A3A3A; border-radius: 6px;
    padding: 5px 8px; color: {TEXT}; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {DIM}; margin-right: 8px; }}
QComboBox QAbstractItemView {{ background: {CARD}; color: {TEXT}; selection-background-color: {ACCENT}; border: 1px solid {BORDER}; border-radius: 6px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; background: transparent; border: none; }}
QSpinBox::up-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid {DIM}; }}
QSpinBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {DIM}; }}
QListWidget::item {{ color: {TEXT}; padding: 2px; }}
QListWidget::item:selected {{ background: rgba(10,132,255,0.35); border-radius: 6px; }}
QHeaderView::section {{ background: {CARD}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px; color: {DIM}; }}
QProgressBar {{
    border: 1px solid {BORDER}; border-radius: 7px; background: #1E1E1E;
    height: 12px; text-align: center; color: {DIM};
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QLabel#statV {{ font-size: 22px; font-weight: 700; color: white; }}
QLabel#statT {{ font-size: 11px; color: {DIM}; }}
QLabel#hint {{ color: {DIM}; font-size: 12px; }}
/* ===== 复选框 ===== */
QCheckBox {{ color: {TEXT}; spacing: 8px; padding: 2px 0; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #555; background: #2A2A2A; }}
QCheckBox::indicator:hover {{ border: 1px solid #888; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
/* ===== 单选按钮 ===== */
QRadioButton {{ color: {TEXT}; spacing: 8px; padding: 2px 0; }}
QRadioButton::indicator {{ width: 18px; height: 18px; border-radius: 9px; border: 1px solid #555; background: #2A2A2A; }}
QRadioButton::indicator:checked {{ background: {ACCENT}; border: 5px solid {ACCENT}; }}
/* ===== 滑块 ===== */
QSlider::groove:horizontal {{ height: 5px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; border: none; width: 15px; height: 15px; margin: -6px 0; border-radius: 8px; }}
QToolTip {{ background: {CARD}; color: white; border: 1px solid {BORDER}; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def fmt_size(n):
    if n < 1024: return "%d B" % n
    if n < 1024**2: return "%.1f KB" % (n/1024)
    if n < 1024**3: return "%.1f MB" % (n/1024**2)
    return "%.2f GB" % (n/1024**3)


def fmt_time(ts):
    try: return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except: return "—"


def trash_with_finder(paths):
    if sys.platform != "darwin": return [], "仅在 macOS 上可用"
    ok, errors = [], []
    for p in paths:
        esc = p.replace('"', '\\"')
        r = subprocess.run(["osascript","-e",
            'tell application "Finder" to delete (POSIX file "%s" as alias)' % esc],
            capture_output=True, text=True)
        if r.returncode == 0: ok.append(p)
        else: errors.append(os.path.basename(p))
    return ok, "；".join(errors[:5])


import hashlib as _hl
_THUMB_CACHE = os.path.expanduser("~/.dupe_organizer/thumbs")
os.makedirs(_THUMB_CACHE, exist_ok=True)

def _ffmpeg_path():
    from shutil import which
    return which("ffmpeg"), which("ffprobe")

def _video_duration(path):
    ffprobe = _ffmpeg_path()[1]
    if not ffprobe: return 0
    try:
        r = subprocess.run([ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", path], capture_output=True, text=True, timeout=10)
        import json
        return float(json.loads(r.stdout)["format"]["duration"])
    except: return 0

def thumb(path, size=180):
    try:
        st = os.stat(path)
        key = _hl.md5((path + str(st.st_mtime) + str(st.st_size)).encode()).hexdigest()
        cache = os.path.join(_THUMB_CACHE, key + ".jpg")
        if os.path.exists(cache):
            pix = QPixmap(cache)
            if not pix.isNull(): return QIcon(pix)
        from PIL import Image
        kind = engine.kind_of(path)
        if kind == "video":
            ffmpeg, ffprobe = _ffmpeg_path()
            if not ffmpeg: return QIcon()
            dur = _video_duration(path)
            t = max(0.5, dur/2) if dur > 2 else 1
            tmp = os.path.join(_THUMB_CACHE, "_tmp_%d.jpg" % os.getpid())
            for seek in [t, 1, max(0, dur-1)]:
                try:
                    subprocess.run([ffmpeg, "-ss", str(seek), "-i", path,
                        "-vframes", "1", "-vf", "scale=%d:-1" % (size*2),
                        "-q:v", "5", "-y", tmp],
                        capture_output=True, timeout=15)
                    if os.path.exists(tmp) and os.path.getsize(tmp) > 1000: break
                except: pass
            if not os.path.exists(tmp) or os.path.getsize(tmp) < 1000: return QIcon()
            im = Image.open(tmp); im.thumbnail((size, size)); im.convert("RGB").save(cache, "JPEG", quality=80)
            if os.path.exists(tmp): os.remove(tmp)
        else:
            try:
                import pillow_heif; pillow_heif.register_heif_opener()
            except: pass
            im = Image.open(path); im.thumbnail((size, size)); im.convert("RGB").save(cache, "JPEG", quality=85)
        pix = QPixmap(cache)
        if not pix.isNull(): return QIcon(pix)
    except Exception as e:
        print("thumb fail:", path, e)
    return QIcon()


# ---------------------------------------------------------------- 线程
class ScanWorker(QThread):
    progress = Signal(int,int); stage = Signal(str); curfile = Signal(str)
    done = Signal(object); failed = Signal(str)
    def __init__(self, roots, opts, cancel):
        super().__init__(); self.roots=roots; self.opts=opts; self.cancel=cancel
    def run(self):
        try:
            want_img = self.opts.get("want_image", True)
            want_vid = self.opts.get("want_video", True)
            min_sz = self.opts.get("min_size", 0)
            max_sz = self.opts.get("max_size", 0)
            def _filter(files):
                out = []
                for f in files:
                    if f.kind == "image" and not want_img: continue
                    if f.kind == "video" and not want_vid: continue
                    if min_sz and f.size < min_sz: continue
                    if max_sz and f.size > max_sz: continue
                    out.append(f)
                return out
            if self.opts.get("speed_mode"):
                res = self._speed_scan()
                res.files = _filter(res.files)
            else:
                res = engine.find_duplicates(
                    self.roots, min_size=0, exact=self.opts["exact"],
                    similar_images=self.opts["similar_images"],
                    image_similarity=self.opts["image_similarity"], similar_videos=False,
                    workers=max(8, (os.cpu_count() or 4) * 2), incremental=self.opts["incremental"],
                    on_progress=lambda d,t: self.progress.emit(d,t or 0),
                    on_file=lambda p: self.curfile.emit(p),
                    on_stage=lambda s: self.stage.emit(s),
                    on_error=lambda p,e: None, cancel=self.cancel)
                res.files = _filter(res.files)
            self.done.emit(res)
        except Exception as e: self.failed.emit(str(e))
    def _speed_scan(self):
        self.stage.emit("极速模式：扫描文件列表…")
        files = engine.scan_media(self.roots, min_size=0,
            on_progress=lambda d,t: self.progress.emit(d, t or 0),
            on_error=lambda p,e: None, cancel=self.cancel)
        self.stage.emit("极速模式：按文件名+大小分组…")
        by = {}
        for f in files:
            by.setdefault((os.path.basename(f.path).lower(), f.size), []).append(f)
        groups = []
        for bucket in by.values():
            if len(bucket) > 1:
                bucket.sort(key=lambda x: -x.size)
                groups.append(engine.DupGroup(kind=bucket[0].kind, hash_value="speed",
                    label="同名同大小", items=bucket))
        groups.sort(key=lambda g: -g.saved_bytes)
        self.progress.emit(len(files), len(files))
        return engine.ScanResult(files=files, exact_groups=groups)


class PlanWorker(QThread):
    built = Signal(list); failed = Signal(str)
    progress = Signal(int,int); stage = Signal(str)
    def __init__(self, roots, dest, opts, cancel):
        super().__init__(); self.roots=roots; self.dest=dest; self.opts=opts; self.cancel=cancel
    def run(self):
        try:
            self.stage.emit("扫描源文件夹…")
            min_sz = self.opts.get("min_size", 0)
            files = engine.scan_media(self.roots, min_size=min_sz, cancel=self.cancel,
                on_progress=lambda d,t: self.progress.emit(d,t or 0),
                on_error=lambda p,e: None)
            self.stage.emit("生成整理计划（读取 EXIF）…")
            plan = classifier.plan_organize(files, self.dest,
                by_type=self.opts["byType"], by_date=self.opts["byDate"],
                by_device=self.opts["byDevice"], by_location=self.opts["byLocation"],
                rename_mode=self.opts["renameMode"], rename_template=self.opts["renameTemplate"],
                conflict=self.opts["conflict"],
                on_progress=lambda d,t: self.progress.emit(d,t or 0),
                cancel=self.cancel)
            self.built.emit(plan)
        except Exception as e: self.failed.emit(str(e))


class ExecWorker(QThread):
    progress = Signal(int,int); done = Signal(int,int,list); failed = Signal(str)
    def __init__(self, plan, copy_mode, cancel):
        super().__init__(); self.plan=plan; self.copy_mode=copy_mode; self.cancel=cancel
    def run(self):
        try:
            ok, fail, logs = classifier.execute_plan(self.plan, copy_mode=self.copy_mode,
                on_progress=lambda d,t: self.progress.emit(d,t or 0), cancel=self.cancel)
            self.done.emit(ok, fail, logs)
        except Exception as e: self.failed.emit(str(e))


class PreviewDialog(QDialog):
    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.setWindowTitle("整理预览"); self.resize(760,520)
        lay = QVBoxLayout(self); lay.addWidget(QLabel("原路径 → 新路径（按目标文件夹分组）："))
        tree = QTreeWidget(); tree.setHeaderLabels(["新文件","原路径"]); tree.setColumnWidth(0,340)
        groups = {}
        for src,dest in plan:
            groups.setdefault(os.path.dirname(dest),[]).append((src,dest))
        for folder,items in sorted(groups.items()):
            root = QTreeWidgetItem(tree,["%s（%d 个）"%(os.path.basename(folder) or folder, len(items)),""])
            for src,dest in items: QTreeWidgetItem(root,[os.path.basename(dest), src])
        tree.expandAll(); lay.addWidget(tree)
        row = QHBoxLayout()
        row.addWidget(QLabel("共 %d 个文件" % len(plan)))
        row.addStretch(1)
        b = QPushButton("关闭"); b.clicked.connect(self.reject); row.addWidget(b)
        b = QPushButton("✅ 确认执行"); b.setObjectName("primary"); b.clicked.connect(self.accept); row.addWidget(b)
        lay.addLayout(row)


# ---------------------------------------------------------------- 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE); self.resize(1100,720)
        self.roots = []; self.exact_groups = []; self.similar_groups = []
        self.keep_state = {}; self.cancel = threading.Event(); self.worker = None
        self._scan_t0 = None; self._current_mode = "exact"; self._scanning = False
        tabs = QTabWidget()
        tabs.addTab(self._build_dup_tab(), "  查找重复  ")
        tabs.addTab(self._build_org_tab(), "  整理归档  ")
        self.setCentralWidget(tabs); self.setStyleSheet(STYLE)
        self._load_last_scan()
        self._update_org_src_empty()
        self.org_pb.setVisible(False)
        self._check_ffmpeg()

    def _last_scan_path(self):
        return os.path.expanduser("~/.dupe_organizer/last_scan.json")

    def _load_last_scan(self):
        import json
        try:
            with open(self._last_scan_path(), "r") as f:
                data = json.load(f)
            self.exact_groups = [engine.DupGroup(kind=g["kind"], hash_value="", label=g["label"],
                items=[engine.MediaFile(**it) for it in g["items"]]) for g in data.get("exact",[])]
            self.similar_groups = [engine.DupGroup(kind=g["kind"], hash_value="", label=g["label"],
                items=[engine.MediaFile(**it) for it in g["items"]]) for g in data.get("similar",[])]
            self._refilter_groups()
            self.lbl_eta.setText("已载入上次扫描结果（%d 组重复、%d 组相似）" % (len(self.exact_groups), len(self.similar_groups)))
            self.btn_cleanall.setEnabled(bool(self.exact_groups or self.similar_groups))
        except Exception: pass

    def _save_last_scan(self):
        import json
        try:
            data = {
                "exact": [{"kind": g.kind, "label": g.label,
                    "items": [{"path": f.path, "size": f.size, "kind": f.kind, "mtime": f.mtime} for f in g.items]}
                    for g in self.exact_groups],
                "similar": [{"kind": g.kind, "label": g.label,
                    "items": [{"path": f.path, "size": f.size, "kind": f.kind, "mtime": f.mtime} for f in g.items]}
                    for g in self.similar_groups],
            }
            with open(self._last_scan_path(), "w") as f:
                json.dump(data, f)
        except Exception: pass

    def closeEvent(self, event):
        if self._scanning: self.cancel.set()
        box = QMessageBox(self)
        box.setWindowTitle(APP_TITLE); box.setIcon(QMessageBox.Question)
        box.setText("确定要退出吗？"); box.setInformativeText("未整理的扫描结果会丢失。")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No); box.setDefaultButton(QMessageBox.No)
        if box.exec() == QMessageBox.Yes: event.accept()
        else: event.ignore()

    def _card(self, title):
        box = QWidget(); box.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER}; border-radius:12px;")
        v = QVBoxLayout(box); v.setContentsMargins(14,12,14,12); v.setSpacing(10)
        t = QLabel(title); t.setStyleSheet("font-weight:600; font-size:13px; color:white;")
        v.addWidget(t)
        return box, v
    def _stat(self, title):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(14,10,14,10)
        t = QLabel(title); t.setObjectName("statT"); v = QLabel("0"); v.setObjectName("statV")
        lay.addWidget(t); lay.addWidget(v)
        w.setStyleSheet(f"background:{CARD}; border:1px solid {BORDER}; border-radius:12px;")
        return w, v

    def _build_dup_tab(self):
        page = QWidget(); outer = QHBoxLayout(page)
        left = QWidget(); left.setFixedWidth(260)
        lv = QVBoxLayout(left); lv.setContentsMargins(0,0,8,0); lv.setSpacing(6)

        box,v = self._card("扫描位置")
        self.roots_list = QListWidget(); self.roots_list.setMaximumHeight(80); v.addWidget(self.roots_list)
        row = QHBoxLayout()
        for t,fn in [("文件夹",self._add_folder),("磁盘",self._add_disk),("移除",self._remove_root)]:
            b = QPushButton(t); b.clicked.connect(fn); row.addWidget(b)
        v.addLayout(row); lv.addWidget(box)

        box,v = self._card("扫描模式")
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        row = QHBoxLayout()
        self.rb_quick = QRadioButton("极速"); row.addWidget(self.rb_quick)
        self.rb_full = QRadioButton("完整"); self.rb_full.setChecked(True); row.addWidget(self.rb_full)
        v.addLayout(row)
        self.chk_exact = QCheckBox("完全重复（逐字节哈希）"); self.chk_exact.setChecked(True)
        self.chk_sim = QCheckBox("相似图片（pHash）"); self.chk_sim.setChecked(True)
        self.chk_incr = QCheckBox("增量扫描"); self.chk_incr.setChecked(True)
        v.addWidget(self.chk_exact); v.addWidget(self.chk_sim); v.addWidget(self.chk_incr)
        self.rb_quick.toggled.connect(self._on_mode_toggle)
        self.rb_full.toggled.connect(self._on_mode_toggle)
        lv.addWidget(box)

        box,v = self._card("文件过滤")
        row = QHBoxLayout(); row.setSpacing(20)
        self.chk_img = QCheckBox("图片"); self.chk_img.setChecked(True)
        self.chk_vid = QCheckBox("视频"); self.chk_vid.setChecked(True)
        row.addWidget(self.chk_img); row.addWidget(self.chk_vid); row.addStretch(1)
        v.addLayout(row)
        # 忽略小于
        self.chk_min = QCheckBox("忽略小于")
        self.in_min = QLineEdit("1"); self.in_min.setFixedWidth(70)
        self.lbl_min_mb = QLabel("MB")
        row = QHBoxLayout(); row.setSpacing(6); row.addWidget(self.chk_min); row.addWidget(self.in_min); row.addWidget(self.lbl_min_mb); row.addStretch(1)
        def _toggle_min(v):
            self.in_min.setVisible(v); self.lbl_min_mb.setVisible(v)
        self.chk_min.toggled.connect(_toggle_min)
        self.in_min.setVisible(False); self.lbl_min_mb.setVisible(False)
        v.addLayout(row)
        # 忽略大于
        self.chk_max = QCheckBox("忽略大于")
        self.in_max = QLineEdit("0"); self.in_max.setFixedWidth(70)
        self.lbl_max_mb = QLabel("MB")
        row = QHBoxLayout(); row.setSpacing(6); row.addWidget(self.chk_max); row.addWidget(self.in_max); row.addWidget(self.lbl_max_mb); row.addStretch(1)
        def _toggle_max(v):
            self.in_max.setVisible(v); self.lbl_max_mb.setVisible(v)
        self.chk_max.toggled.connect(_toggle_max)
        self.in_max.setVisible(False); self.lbl_max_mb.setVisible(False)
        v.addLayout(row)
        lv.addWidget(box)

        box,v = self._card("相似阈值")
        row = QHBoxLayout(); self.sim_label = QLabel("≥ 90%"); row.addWidget(self.sim_label); row.addStretch(1); v.addLayout(row)
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(70,100); self.slider.setValue(90)
        self.slider.valueChanged.connect(lambda val: self.sim_label.setText("≥ %d%%" % val))
        v.addWidget(self.slider); lv.addWidget(box)
        self._on_mode_toggle()

        box,v = self._card("保留规则")
        row = QHBoxLayout(); row.addWidget(QLabel("自动保留"))
        self.cmb_keep = QComboBox(); self.cmb_keep.addItems(["画质最高","文件最大","路径最短","最新修改"])
        row.addWidget(self.cmb_keep,1); v.addLayout(row); lv.addWidget(box)
        lv.addStretch(1)

        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(8,0,0,0); rv.setSpacing(8)
        # 顶部操作栏（横排）
        bar = QHBoxLayout()
        self.btn_start = QPushButton("开始扫描"); self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start_scan)
        self.btn_stop = QPushButton("停止"); self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_scan)
        self.btn_cleanall = QPushButton("一键清理全部重复")
        self.btn_cleanall.clicked.connect(self._clean_all)
        self.btn_cleanall.setEnabled(False)
        bar.addWidget(self.btn_start); bar.addWidget(self.btn_stop); bar.addWidget(self.btn_cleanall)
        bar.addStretch(1)
        rv.addLayout(bar)
        self.progress = QProgressBar(); rv.addWidget(self.progress)
        self.lbl_eta = QLabel("就绪。"); self.lbl_eta.setObjectName("hint"); self.lbl_eta.setWordWrap(True)
        rv.addWidget(self.lbl_eta)

        stats = QGridLayout()
        self.stat_files,v1 = self._stat("扫描文件"); self.stat_exact,v2 = self._stat("重复组")
        self.stat_similar,v3 = self._stat("相似组"); self.stat_saved,v4 = self._stat("可释放")
        stats.addWidget(self.stat_files,0,0); stats.addWidget(self.stat_exact,0,1)
        stats.addWidget(self.stat_similar,0,2); stats.addWidget(self.stat_saved,0,3)
        rv.addLayout(stats)

        row = QHBoxLayout()
        self.search_box = QLineEdit(); self.search_box.setPlaceholderText("🔍 按文件名过滤…")
        self.search_box.textChanged.connect(lambda: self._refilter_groups())
        row.addWidget(self.search_box)
        row.addWidget(QLabel("排序"))
        self.cmb_sort = QComboBox(); self.cmb_sort.addItems(["占用空间最大","文件数最多","最新修改"])
        self.cmb_sort.currentIndexChanged.connect(lambda: self._refilter_groups())
        row.addWidget(self.cmb_sort)
        rv.addLayout(row)

        self.dup_tabs = QTabWidget()
        self._build_exact_panel(); self._build_similar_panel()
        self.dup_tabs.currentChanged.connect(lambda i: setattr(self,"_current_mode","exact" if i==0 else "similar") or self._rebuild_grid(self._current_mode))
        rv.addWidget(self.dup_tabs,1)
        outer.addWidget(left); outer.addWidget(right,1)
        return page

    def _build_exact_panel(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,0)
        self.exact_gl = QListWidget(); self.exact_gl.setViewMode(QListWidget.IconMode)
        self.exact_gl.setIconSize(QSize(90,90)); self.exact_gl.setGridSize(QSize(160,120))
        self.exact_gl.setResizeMode(QListWidget.Adjust); self.exact_gl.setMovement(QListWidget.Static)

        self.exact_gl.currentItemChanged.connect(lambda: self._rebuild_grid("exact"))
        lay.addWidget(QLabel("重复组（点击查看）"))
        self.exact_empty = QLabel("扫描完成后，重复文件会按组显示在这里")
        self.exact_empty.setStyleSheet("color:#6b6b6b; padding:40px;")
        self.exact_empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.exact_empty)
        lay.addWidget(self.exact_gl)
        self.exact_grid = QListWidget(); self.exact_grid.setViewMode(QListWidget.IconMode)
        self.exact_grid.setIconSize(QSize(180,180)); self.exact_grid.setGridSize(QSize(210,230))
        self.exact_grid.setResizeMode(QListWidget.Adjust); self.exact_grid.setMovement(QListWidget.Static)

        lay.addWidget(QLabel("组内文件（点缩略图切换 保留/重复）")); lay.addWidget(self.exact_grid,1)
        row = QHBoxLayout()
        b = QPushButton("自动保留"); b.clicked.connect(self._apply_keep); row.addWidget(b)
        b = QPushButton("删除本组其余文件"); b.clicked.connect(lambda: self._quick_delete("exact")); row.addWidget(b)
        b = QPushButton("应用到全部组"); b.clicked.connect(lambda: self._apply_all("exact")); row.addWidget(b)
        row.addStretch(1); lay.addLayout(row)
        self.dup_tabs.addTab(w, "重复")

    def _build_similar_panel(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,0)
        self.sim_gl = QListWidget(); self.sim_gl.setViewMode(QListWidget.IconMode)
        self.sim_gl.setIconSize(QSize(90,90)); self.sim_gl.setGridSize(QSize(160,120))
        self.sim_gl.setResizeMode(QListWidget.Adjust); self.sim_gl.setMovement(QListWidget.Static)

        self.sim_gl.currentItemChanged.connect(lambda: self._rebuild_grid("similar"))
        lay.addWidget(QLabel("相似组（点击查看）"))
        self.sim_empty = QLabel("扫描完成后，相似图片会按组显示在这里")
        self.sim_empty.setStyleSheet("color:#6b6b6b; padding:40px;")
        self.sim_empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.sim_empty)
        lay.addWidget(self.sim_gl)
        self.sim_grid = QListWidget(); self.sim_grid.setViewMode(QListWidget.IconMode)
        self.sim_grid.setIconSize(QSize(180,180)); self.sim_grid.setGridSize(QSize(210,230))
        self.sim_grid.setResizeMode(QListWidget.Adjust); self.sim_grid.setMovement(QListWidget.Static)

        lay.addWidget(QLabel("组内文件（点缩略图切换 保留/重复）")); lay.addWidget(self.sim_grid,1)
        row = QHBoxLayout()
        b = QPushButton("自动保留"); b.clicked.connect(self._apply_keep); row.addWidget(b)
        b = QPushButton("删除本组其余文件"); b.clicked.connect(lambda: self._quick_delete("similar")); row.addWidget(b)
        b = QPushButton("应用到全部组"); b.clicked.connect(lambda: self._apply_all("similar")); row.addWidget(b)
        row.addStretch(1); lay.addLayout(row)
        self.dup_tabs.addTab(w, "相似图片")

    def _on_mode_toggle(self):
        quick = self.rb_quick.isChecked()
        self.chk_exact.setEnabled(not quick)
        self.chk_sim.setEnabled(not quick)
        self.slider.setEnabled(not quick)
        self.chk_incr.setEnabled(not quick)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self,"选择文件夹")
        if d: self._append(d)
    def _add_disk(self):
        vols = ["/"]
        try:
            for n in sorted(os.listdir("/Volumes")):
                p = os.path.join("/Volumes", n)
                if os.path.isdir(p): vols.append(p)
        except: pass
        items = ["主磁盘 → /"] + ["%s → %s" % (os.path.basename(v),v) for v in vols[1:]]
        dlg = QDialog(self); dlg.setWindowTitle("选择磁盘"); dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg); lst = QListWidget()
        for it in items: lst.addItem(it)
        lay.addWidget(lst); b = QPushButton("确定"); b.clicked.connect(dlg.accept); lay.addWidget(b)
        if dlg.exec() == QDialog.Accepted and lst.currentItem():
            self._append(lst.currentItem().text().split("→")[-1].strip())
    def _append(self, p):
        p = os.path.abspath(p)
        if p not in self.roots and os.path.isdir(p):
            self.roots.append(p); self.roots_list.addItem(p)
    def _remove_root(self):
        r = self.roots_list.currentRow()
        if r >= 0: self.roots.pop(r); self.roots_list.takeItem(r)

    def _start_scan(self):
        if not self.roots:
            QMessageBox.warning(self, APP_TITLE, "请先添加扫描位置。"); return
        self.cancel = threading.Event(); self._scan_t0 = time.time(); self._scanning = True
        opts = {"speed_mode": self.rb_quick.isChecked(), "exact": self.chk_exact.isChecked(),
                "similar_images": self.chk_sim.isChecked(),
                "image_similarity": float(self.slider.value()),
                "incremental": self.chk_incr.isChecked(),
                "want_image": self.chk_img.isChecked(), "want_video": self.chk_vid.isChecked(),
                "min_size": int(self.in_min.text() or 0) * 1048576 if self.chk_min.isChecked() else 0,
                "max_size": int(self.in_max.text() or 0) * 1048576 if self.chk_max.isChecked() else 0}
        self.worker = ScanWorker(self.roots[:], opts, self.cancel)
        self.worker.progress.connect(self._on_progress)
        self.worker.stage.connect(lambda s: self.lbl_eta.setText(s))
        self.worker.curfile.connect(lambda p: self.lbl_eta.setText("处理：%s" % os.path.basename(p)))
        self.worker.done.connect(self._apply_result)
        self.worker.failed.connect(lambda e: (QMessageBox.critical(self,APP_TITLE,e), self._set_busy(False)))
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.progress.setRange(0,0); self.worker.start()
    def _stop_scan(self): self.cancel.set(); self.lbl_eta.setText("停止中…")
    def _set_busy(self, b):
        self.btn_start.setEnabled(not b); self.btn_stop.setEnabled(False); self._scanning = b
    def _on_progress(self, done, total):
        if total and total > 0:
            self.progress.setRange(0,int(total)); self.progress.setValue(int(done))
            if self._scan_t0 and done > 3:
                el = time.time()-self._scan_t0; remain = el/done*(total-done)
                self.lbl_eta.setText("%d / %d　剩余 %.0fs" % (done,total,remain))
        else:
            self.progress.setRange(0,0)
            self.lbl_eta.setText("已扫描 %d 个文件…" % done)

    def _apply_result(self, result):
        self.exact_groups = list(result.exact_groups)
        self.similar_groups = list(result.similar_groups)
        self.keep_state.clear()
        self.progress.setRange(0,1); self.progress.setValue(1)
        self._set_stat(self.stat_files, str(len(result.files)))
        self._set_stat(self.stat_exact, str(len(self.exact_groups)))
        self._set_stat(self.stat_similar, str(len(self.similar_groups)))
        self._set_stat(self.stat_saved, fmt_size(result.saved_bytes))
        self._refilter_groups()
        self._save_last_scan()
        self.lbl_eta.setText("完成：%d 组重复、%d 组相似，省 %s" % (
            len(self.exact_groups), len(self.similar_groups), fmt_size(result.saved_bytes)))
        self.btn_cleanall.setEnabled(bool(self.exact_groups or self.similar_groups))
    def _set_stat(self, card, val):
        card.findChildren(QLabel)[-1].setText(val)

    def _rebuild_groups(self, groups, lw):
        lw.clear()
        for g in groups:
            rep = g.representative
            ic = thumb(rep.path, 90) if rep else QIcon()
            it = QListWidgetItem(ic, "%d 个\n省 %s" % (len(g.items), fmt_size(g.saved_bytes)))
            lw.addItem(it)
        if groups: lw.setCurrentRow(0)
        # toggle empty label
        if lw == self.exact_gl:
            self.exact_empty.setVisible(not groups)
            self.exact_gl.setVisible(bool(groups))
        elif lw == self.sim_gl:
            self.sim_empty.setVisible(not groups)
            self.sim_gl.setVisible(bool(groups))

    def _refilter_groups(self):
        """按搜索框和排序刷新组列表。"""
        query = self.search_box.text().strip().lower()
        sort_by = self.cmb_sort.currentText()
        def _sort(groups):
            gs = list(groups)
            if sort_by == "占用空间最大": gs.sort(key=lambda g: -g.saved_bytes)
            elif sort_by == "文件数最多": gs.sort(key=lambda g: -len(g.items))
            elif sort_by == "最新修改": gs.sort(key=lambda g: -max(f.mtime for f in g.items))
            return gs
        def _filter(groups):
            if not query: return groups
            return [g for g in groups if any(query in os.path.basename(f.path).lower() for f in g.items)]
        self._rebuild_groups(_filter(_sort(self.exact_groups)), self.exact_gl)
        self._rebuild_groups(_filter(_sort(self.similar_groups)), self.sim_gl)
        self._current_filtered_exact = _filter(_sort(self.exact_groups))
        self._current_filtered_similar = _filter(_sort(self.similar_groups))

    def _rebuild_grid(self, mode):
        if mode == "exact":
            groups = getattr(self, '_current_filtered_exact', self.exact_groups)
            gl = self.exact_gl
        else:
            groups = getattr(self, '_current_filtered_similar', self.similar_groups)
            gl = self.sim_gl
        grid = self.exact_grid if mode=="exact" else self.sim_grid
        grid.clear()
        row = gl.currentRow()
        if not (0 <= row < len(groups)): return
        g = groups[row]
        try: grid.itemClicked.disconnect()
        except: pass
        for f in g.items:
            keep = self.keep_state.get(f.path, True)
            ic = thumb(f.path, 180)
            mark = "✓ 保留" if keep else "✗ 重复"
            it = QListWidgetItem(ic, "%s\n%s\n%s · %s" % (
                mark, os.path.basename(f.path), fmt_size(f.size), fmt_time(f.mtime)))
            it.setToolTip(f.path); it.setData(Qt.UserRole, f.path)
            grid.addItem(it)
        grid.itemClicked.connect(lambda it: self._toggle(it.data(Qt.UserRole), mode))

    def _toggle(self, path, mode):
        self.keep_state[path] = not self.keep_state.get(path, True)
        self._rebuild_grid(mode)

    def _current_group(self):
        gl = self.exact_gl if self._current_mode=="exact" else self.sim_gl
        groups = self.exact_groups if self._current_mode=="exact" else self.similar_groups
        r = gl.currentRow(); return groups[r] if 0<=r<len(groups) else None
    def _dup_paths(self):
        g = self._current_group()
        return [f.path for f in g.items if not self.keep_state.get(f.path, True)] if g else []
    def _apply_keep(self):
        g = self._current_group()
        if not g: return
        pref = {"画质最高":"quality","文件最大":"size","路径最短":"depth","最新修改":"newest"}.get(self.cmb_keep.currentText(),"quality")
        idx = engine.suggest_keep(g, pref)
        for i,f in enumerate(g.items): self.keep_state[f.path] = (i==idx)
        self._rebuild_grid(self._current_mode)

    def _choose_delete_method(self, preview_text):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("选择删除方式")
        dlg.setText(preview_text)
        dlg.setInformativeText("隔离区（推荐）：移到 ~/重复文件待确认/，看完再手动清\n回收站：可恢复，跨盘较慢\n直接删除：立即删除，不可恢复，最快")
        b0 = dlg.addButton("隔离区（推荐）", QMessageBox.AcceptRole)
        b1 = dlg.addButton("送回收站", QMessageBox.ActionRole)
        b2 = dlg.addButton("直接删除", QMessageBox.DestructiveRole)
        dlg.addButton("取消", QMessageBox.RejectRole)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked == b0: return "quarantine"
        if clicked == b1: return "trash"
        if clicked == b2: return "delete"
        return None

    def _do_delete(self, paths):
        if not paths: return
        total = sum(os.path.getsize(p) for p in paths if os.path.exists(p))
        size_str = fmt_size(total)
        preview = "将处理 %d 个文件，共 %s。\n\n请选择删除方式：" % (len(paths), size_str)
        method = self._choose_delete_method(preview)
        if not method: return
        if method == "delete":
            warn = "⚠ 将永久删除 %d 个文件（%s），不进回收站，无法恢复！" % (len(paths), size_str)
        elif method == "quarantine":
            warn = "将把 %d 个文件（%s）移到隔离区 ~/重复文件待确认/，确认无误后可手动清空。" % (len(paths), size_str)
        else:
            warn = "将把 %d 个文件（%s）移到回收站，可恢复。" % (len(paths), size_str)
        reply = QMessageBox.warning(self, APP_TITLE, warn + "\n\n确定继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes: return
        done = []
        if method == "quarantine":
            import shutil
            qdir = os.path.expanduser("~/重复文件待确认")
            os.makedirs(qdir, exist_ok=True)
            for p in paths:
                try:
                    newp = classifier.unique_path(os.path.join(qdir, os.path.basename(p)), "rename")
                    shutil.move(p, newp); done.append(p)
                except: pass
            QMessageBox.information(self, APP_TITLE,
                "已移到隔离区 %d 个文件。\n去 %s 确认无误后，手动清空该文件夹。" % (len(done), qdir))
        elif method == "trash":
            ok, err = trash_with_finder(paths); done = ok
            QMessageBox.information(self, APP_TITLE, "已送回收站 %d 个。%s" % (len(ok), err))
        else:
            for p in paths:
                try: os.remove(p); done.append(p)
                except OSError: pass
            QMessageBox.information(self, APP_TITLE, "已永久删除 %d 个（释放 %s）" % (len(done), size_str))
        self._after_cleanup(done)

    def _quick_delete(self, mode):
        g = self._current_group()
        if not g: return
        # 自动选保留
        pref = {"画质最高":"quality","文件最大":"size","路径最短":"depth","最新修改":"newest"}.get(self.cmb_keep.currentText(),"quality")
        idx = engine.suggest_keep(g, pref)
        for i,f in enumerate(g.items): self.keep_state[f.path] = (i==idx)
        paths = [f.path for i,f in enumerate(g.items) if i != idx]
        self._do_delete(paths)

    def _clean_all(self):
        all_groups = self.exact_groups + self.similar_groups
        if not all_groups:
            QMessageBox.information(self, APP_TITLE, "没有重复组。"); return
        pref = {"画质最高":"quality","文件最大":"size","路径最短":"depth","最新修改":"newest"}.get(self.cmb_keep.currentText(),"quality")
        all_dup = []
        for g in all_groups:
            idx = engine.suggest_keep(g, pref)
            for i,f in enumerate(g.items):
                if i != idx: all_dup.append(f.path)
        if not all_dup:
            QMessageBox.information(self, APP_TITLE, "没有可删除的文件。"); return
        total = sum(os.path.getsize(p) for p in all_dup if os.path.exists(p))
        QMessageBox.information(self, APP_TITLE,
            "共 %d 组重复，将自动保留每组最好的一个，删除 %d 个文件（%s）。\n点确定后选择删除方式。" % (
                len(all_groups), len(all_dup), fmt_size(total)))
        self._do_delete(all_dup)

    def _apply_all(self, mode):
        groups = self.exact_groups if mode=="exact" else self.similar_groups
        if not groups: return
        pref = {"画质最高":"quality","文件最大":"size","路径最短":"depth","最新修改":"newest"}.get(self.cmb_keep.currentText(),"quality")
        all_dup = []
        for g in groups:
            idx = engine.suggest_keep(g, pref)
            for i,f in enumerate(g.items):
                if i != idx: all_dup.append(f.path)
        if not all_dup:
            QMessageBox.information(self, APP_TITLE, "没有可删除的文件。"); return
        self._do_delete(all_dup)

    def _after_cleanup(self, removed):
        rm = set(removed)
        for gl in (self.exact_groups, self.similar_groups):
            for g in gl: g.items = [f for f in g.items if f.path not in rm]
        for p in rm: self.keep_state.pop(p, None)
        self.exact_groups = [g for g in self.exact_groups if len(g.items)>=2]
        self.similar_groups = [g for g in self.similar_groups if len(g.items)>=2]
        self._rebuild_groups(self.exact_groups, self.exact_gl)
        self._rebuild_groups(self.similar_groups, self.sim_gl)
        self.btn_cleanall.setEnabled(bool(self.exact_groups or self.similar_groups))

    # ============================================================ 整理归档
    def _build_org_tab(self):
        page = QWidget(); outer = QHBoxLayout(page)
        left = QWidget(); left.setFixedWidth(260)
        lv = QVBoxLayout(left); lv.setContentsMargins(0,0,8,0); lv.setSpacing(10)
        box,v = self._card("源文件夹")
        self.org_src = QListWidget(); self.org_src.setMaximumHeight(70); v.addWidget(self.org_src)
        self.org_src_empty = QLabel("点击下方「添加」选择文件夹，或「从扫描页导入」")
        self.org_src_empty.setStyleSheet("color:#6b6b6b; padding:20px;"); self.org_src_empty.setAlignment(Qt.AlignCenter)
        self.org_src_empty.setWordWrap(True)
        v.addWidget(self.org_src_empty)
        row = QHBoxLayout()
        b = QPushButton("＋添加"); b.clicked.connect(self._org_add); row.addWidget(b)
        b = QPushButton("从扫描页导入"); b.clicked.connect(self._org_use); row.addWidget(b)
        v.addLayout(row); lv.addWidget(box)
        box,v = self._card("目标目录")
        row = QHBoxLayout(); self.org_dest = QLineEdit(); self.org_dest.setPlaceholderText("选择目标…")
        b = QPushButton("浏览"); b.clicked.connect(self._org_browse)
        row.addWidget(self.org_dest); row.addWidget(b); v.addLayout(row); lv.addWidget(box)
        box,v = self._card("归档维度")
        self.org_type = QCheckBox("按类型"); self.org_type.setChecked(True)
        self.org_date = QCheckBox("按 年-月"); self.org_date.setChecked(True)
        self.org_device = QCheckBox("按拍摄设备")
        self.org_loc = QCheckBox("按拍摄地点")
        v.addWidget(self.org_type); v.addWidget(self.org_date); v.addWidget(self.org_device); v.addWidget(self.org_loc)
        self.chk_org_min = QCheckBox("忽略小于指定大小的文件")
        self.org_min_edit = QLineEdit("1"); self.org_min_edit.setFixedWidth(70)
        self.org_min_mb = QLabel("MB")
        def _toggle_org_min(v):
            self.org_min_edit.setVisible(v); self.org_min_mb.setVisible(v)
        self.chk_org_min.toggled.connect(_toggle_org_min)
        self.org_min_edit.setVisible(False); self.org_min_mb.setVisible(False)
        v.addWidget(self.chk_org_min)
        row = QHBoxLayout(); row.setContentsMargins(24,0,0,0); row.setSpacing(4)
        row.addWidget(self.org_min_edit); row.addWidget(self.org_min_mb); row.addStretch(1)
        v.addLayout(row); lv.addWidget(box)
        box,v = self._card("重命名")
        self.cmb_rename = QComboBox(); self.cmb_rename.addItems(["保留原名","按拍摄时间 20240115_203015","自定义模板"])
        v.addWidget(self.cmb_rename)
        self.tpl = QLineEdit("{date}_{model}")
        self.tpl.setPlaceholderText("可用 {date} {model} {original}")
        self.tpl.textChanged.connect(self._update_tpl_preview)
        v.addWidget(self.tpl)
        self.tpl_preview = QLabel("预览：20240115_Apple iPhone 15.jpg")
        self.tpl_preview.setStyleSheet("color:#6b6b6b; font-size:11px;")
        v.addWidget(self.tpl_preview)
        row = QHBoxLayout(); row.addWidget(QLabel("同名冲突:"))
        self.cmb_conf = QComboBox(); self.cmb_conf.addItems(["自动加序号","跳过","覆盖"])
        row.addWidget(self.cmb_conf); row.addStretch(1); v.addLayout(row)
        lv.addWidget(box)
        # 复制而非移动 —— 独立一行，醒目
        self.org_copy = QCheckBox("☑ 复制而非移动（原文件保留在原位）")
        self.org_copy.setToolTip("勾选后原文件保留在原位，仅复制到目标目录")
        lv.addWidget(self.org_copy)
        row = QHBoxLayout()
        b = QPushButton("预览"); b.clicked.connect(self._org_preview); row.addWidget(b)
        b = QPushButton("开始整理"); b.setObjectName("primary"); b.clicked.connect(self._org_start); row.addWidget(b)
        lv.addLayout(row)
        self.org_pb = QProgressBar(); lv.addWidget(self.org_pb)
        self.org_hint = QLabel(""); self.org_hint.setObjectName("hint"); self.org_hint.setWordWrap(True)
        lv.addWidget(self.org_hint); lv.addStretch(1)
        # 右侧：无粗边框的日志/预览区
        self.org_log = QPlainTextEdit(); self.org_log.setReadOnly(True)
        self.org_log.setStyleSheet("QPlainTextEdit { border: none; background: #2a2a2c; border-radius: 10px; padding: 8px; }")
        self.org_placeholder = QLabel("点击「预览」查看文件将被整理到哪里")
        self.org_placeholder.setStyleSheet("color:#6b6b6b; padding:60px; background: transparent;")
        self.org_placeholder.setAlignment(Qt.AlignCenter)
        outer.addWidget(left); outer.addWidget(self.org_log,1)
        self.org_log.setVisible(False)
        return page

    def _update_tpl_preview(self):
        t = self.tpl.text().strip() or "{original}"
        self.tpl_preview.setText("预览：" + t.replace("{date}","20240115_203015").replace("{model}","Apple iPhone 15").replace("{original}","IMG_001") + ".jpg")
    def _org_add(self):
        d = QFileDialog.getExistingDirectory(self,"选择源文件夹")
        if d and not any(self.org_src.item(i).text()==d for i in range(self.org_src.count())):
            self.org_src.addItem(d)
        self._update_org_src_empty()
    def _org_use(self):
        for r in self.roots:
            if not any(self.org_src.item(i).text()==r for i in range(self.org_src.count())):
                self.org_src.addItem(r)
        self._update_org_src_empty()
    def _check_ffmpeg(self):
        ff, fp = _ffmpeg_path()
        if not ff:
            self.lbl_eta.setText("提示：未检测到 ffmpeg，视频缩略图无法生成。终端运行 brew install ffmpeg 安装。")
    def _update_org_src_empty(self):
        has = self.org_src.count() > 0
        self.org_src.setVisible(has)
        self.org_src_empty.setVisible(not has)
    def _org_browse(self):
        d = QFileDialog.getExistingDirectory(self,"选择目标目录")
        if d: self.org_dest.setText(d)
    def _org_opts(self):
        return {"byType":self.org_type.isChecked(),"byDate":self.org_date.isChecked(),
                "byDevice":self.org_device.isChecked(),"byLocation":self.org_loc.isChecked(),
                "renameMode":{"保留原名":"keep","按拍摄时间 20240115_203015":"time","自定义模板":"template"}[self.cmb_rename.currentText()],
                "renameTemplate":self.tpl.text().strip(),
                "conflict":{"自动加序号":"rename","跳过":"skip","覆盖":"overwrite"}[self.cmb_conf.currentText()],
                "min_size": int(self.org_min_edit.text() or 0) * 1048576 if self.chk_org_min.isChecked() else 0}
    def _org_validate(self):
        roots = [self.org_src.item(i).text() for i in range(self.org_src.count())]
        dest = self.org_dest.text().strip()
        if not roots: QMessageBox.warning(self,APP_TITLE,"请添加源文件夹。"); return None,None
        if not dest: QMessageBox.warning(self,APP_TITLE,"请选目标目录。"); return None,None
        return roots,dest
    def _org_preview(self):
        roots,dest = self._org_validate()
        if not roots: return
        c = threading.Event()
        self.org_pb.setVisible(True); self.org_pb.setValue(0)
        self.org_hint.setText("生成预览…")
        self._pw = PlanWorker(roots,dest,self._org_opts(),c)
        self._pw.progress.connect(lambda d,t: (self.org_pb.setValue(int(d/t*100) if t else 0), self.org_hint.setText("%d/%d" % (d,t))))
        self._pw.stage.connect(self.org_hint.setText)
        def _show(plan):
            self.org_pb.setValue(100); self.org_pb.setVisible(False)
            if not plan:
                self.org_hint.setText("没有需要整理的文件。"); return
            self.org_log.setVisible(True); self.org_log.clear()
            self.org_log.appendPlainText("原路径 → 新路径：\n")
            for s,d in plan[:500]:
                self.org_log.appendPlainText("%s\n  → %s" % (s, d))
            if len(plan) > 500:
                self.org_log.appendPlainText("\n… 共 %d 个，仅显示前 500 条" % len(plan))
            dlg = PreviewDialog(plan, self)
            if dlg.exec() == QDialog.Accepted:
                self._org_exec(plan, dest)
        self._pw.built.connect(_show)
        self._pw.failed.connect(lambda e: (self.org_pb.setVisible(False), self.org_hint.setText("出错"), QMessageBox.critical(self,APP_TITLE,e)))
        self._pw.start()
    def _org_start(self):
        roots,dest = self._org_validate()
        if not roots: return
        c = threading.Event(); self.org_pb.setVisible(True); self.org_pb.setValue(0); self.org_hint.setText("生成计划…")
        self._pw = PlanWorker(roots,dest,self._org_opts(),c)
        self._pw.progress.connect(lambda d,t: (self.org_pb.setValue(int(d/t*100) if t else 0), self.org_hint.setText("%d/%d" % (d,t))))
        self._pw.stage.connect(self.org_hint.setText)
        self._pw.built.connect(lambda plan: self._org_exec(plan,dest))
        self._pw.failed.connect(lambda e: (self.org_pb.setVisible(False), self.org_hint.setText("出错"), QMessageBox.critical(self,APP_TITLE,e)))
        self._pw.start()
    def _org_exec(self, plan, dest):
        if not plan: self.org_hint.setText("无需整理。"); return
        if QMessageBox.question(self,APP_TITLE,"整理 %d 个文件？"%len(plan),
            QMessageBox.Yes|QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes: return
        c = threading.Event()
        self._ew = ExecWorker(plan, self.org_copy.isChecked(), c)
        self._ew.progress.connect(lambda d,t: (self.org_pb.setValue(int(d/t*100) if t else 0), self.org_hint.setText("%d/%d"%(d,t))))
        self._ew.done.connect(lambda ok,fail,logs: self._org_done(ok,fail,logs,dest))
        self._ew.failed.connect(lambda e: QMessageBox.critical(self,APP_TITLE,e))
        self._ew.start()
    def _org_done(self, ok, fail, logs, dest):
        self.org_pb.setValue(100); self.org_pb.setVisible(False)
        self.org_hint.setText("完成：共整理 %d 个文件，失败 %d 个" % (ok, fail))
        try:
            p = classifier.write_log(dest, logs)
            self.org_log.setVisible(True)
            self.org_log.appendPlainText("\n日志已保存：" + p)
        except: pass
        QMessageBox.information(self,APP_TITLE,"完成：成功 %d，失败 %d"%(ok,fail))


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv); app.setApplicationName(APP_TITLE)
    win = MainWindow(); win.show(); sys.exit(app.exec())

if __name__ == "__main__": main()
