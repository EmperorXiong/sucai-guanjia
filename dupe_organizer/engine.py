# -*- coding: utf-8 -*-
"""扫描与重复检测核心引擎（纯逻辑，不依赖界面，可独立测试）。

功能：
1. 多根目录（可跨硬盘/外接卷）扫描图片与视频文件；
2. 完全重复检测：文件大小 + 快特征 + SHA-256 全量哈希；
3. 相似图片检测：pHash，相似度百分比阈值（70%–100%）；
4. 相似视频检测：可选，借助 ffmpeg 抽帧做帧级 pHash 对比；
5. 增量缓存：记录 文件(mtime,size)→哈希，二次扫描跳过未变化文件；
6. 保留项建议：画质 / 文件大小 / 路径最短 / 最新修改。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".avif", ".cr2", ".nef", ".arw", ".dng", ".orf", ".rw2",
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".m4v",
    ".3gp", ".ts", ".m2ts", ".mpg", ".mpeg", ".vob", ".rmvb",
}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS

SKIP_DIR_NAMES = {
    ".Trashes", ".Spotlight-V100", ".fseventsd", ".Trash", ".TemporaryItems",
    ".DS_Store", ".apdisk", "@eaDir", "#recycle", "$RECYCLE.BIN", "System Volume Information",
}

CHUNK = 16 * 1024
CACHE_DIR = os.path.expanduser("~/.dupe_organizer")
CACHE_FILE = os.path.join(CACHE_DIR, "hash_cache.json")


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ALL_EXTS


def kind_of(path: str) -> str:
    return "image" if os.path.splitext(path)[1].lower() in IMAGE_EXTS else "video"


def volume_of(path: str) -> str:
    p = os.path.abspath(path)
    if p.startswith("/Volumes/"):
        parts = p.split("/")
        if len(parts) >= 3:
            return "/Volumes/" + parts[2]
    return "/"


def similarity_to_distance(pct) -> int:
    """相似度百分比 → 64 位 pHash 的允许汉明距离。越低越严格。"""
    return int(round((100.0 - float(pct)) / 100.0 * 64))


def path_depth(path: str) -> int:
    return len([x for x in path.split(os.sep) if x])


@dataclass(eq=False)
class MediaFile:
    path: str
    size: int
    kind: str
    mtime: float = 0.0


@dataclass
class DupGroup:
    kind: str
    hash_value: str
    label: str = "完全一致"
    items: list = field(default_factory=list)

    @property
    def saved_bytes(self) -> int:
        if not self.items:
            return 0
        return sum(i.size for i in self.items) - max(i.size for i in self.items)

    @property
    def total_bytes(self) -> int:
        return sum(i.size for i in self.items)

    @property
    def representative(self):
        return self.items[0] if self.items else None


@dataclass
class ScanResult:
    files: list = field(default_factory=list)
    exact_groups: list = field(default_factory=list)
    similar_groups: list = field(default_factory=list)

    @property
    def all_groups(self):
        return self.exact_groups + self.similar_groups

    @property
    def saved_bytes(self) -> int:
        return sum(g.saved_bytes for g in self.all_groups)


# ------------------------- 扫描 -------------------------

def scan_media(roots, min_size=0, on_progress=None, on_error=None, cancel=None):
    seen = set()
    files = []
    n = {"c": 0}

    def _walk(root):
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".")]
            for name in filenames:
                if cancel is not None and cancel.is_set():
                    return
                full = os.path.join(dirpath, name)
                try:
                    if not is_supported(full):
                        continue
                    rp = os.path.realpath(full)
                    if rp in seen:
                        continue
                    st = os.stat(full)
                    if st.st_size < min_size:
                        continue
                    seen.add(rp)
                    files.append(MediaFile(path=full, size=st.st_size, kind=kind_of(full),
                                           mtime=st.st_mtime))
                    n["c"] += 1
                    if on_progress and n["c"] % 25 == 0:
                        on_progress(n["c"], None)
                except OSError as e:
                    if on_error:
                        on_error(full, e)

    for root in roots:
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            if on_error:
                on_error(root, OSError("目录不存在或不可访问"))
            continue
        _walk(root)
    return files


# ------------------------- 哈希 -------------------------

def fast_signature(path: str, size: int) -> str:
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(CHUNK))
        if size > CHUNK:
            f.seek(max(0, size // 2 - CHUNK // 2))
            h.update(f.read(CHUNK))
            f.seek(max(0, size - CHUNK))
            h.update(f.read(CHUNK))
    return h.hexdigest()


def full_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _hash_worker(mf: MediaFile):
    return full_sha256(mf.path)


def phash_image(path: str, hash_size: int = 8):
    try:
        from imagehash import phash
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            return int(str(phash(im, hash_size=hash_size)), 16)
    except Exception:
        return None


def _phash_worker(mf: MediaFile):
    return phash_image(mf.path)


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _map_parallel(fn, items, workers, on_progress=None, cancel=None):
    results = {}
    if workers <= 1:
        for i, it in enumerate(items, 1):
            if cancel is not None and cancel.is_set(): break
            try: results[it] = fn(it)
            except Exception: results[it] = None
            if on_progress: on_progress(i, len(items))
        return results
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, it): it for it in items}
        done = 0
        for fut in as_completed(futs):
            if cancel is not None and cancel.is_set():
                for f in futs: f.cancel()
                break
            it = futs[fut]
            try: results[it] = fut.result()
            except Exception: results[it] = None
            done += 1
            if on_progress: on_progress(done, len(items))
    return results


# ------------------------- 增量缓存 -------------------------

def load_hash_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_hash_cache(cache):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


def _cache_hit(cache, f, key):
    rec = cache.get(f.path)
    if not rec:
        return None
    if rec.get("mtime") != f.mtime or rec.get("size") != f.size:
        return None
    return rec.get(key)


# ------------------------- 完全重复 -------------------------

def group_exact_duplicates(files, cache=None, workers=1, on_progress=None, on_file=None,
                           on_error=None, cancel=None):
    by_size = {}
    for f in files:
        by_size.setdefault((f.size, f.kind), []).append(f)

    groups = []
    if cache is None:
        cache = {}

    candidates = [b for b in by_size.values() if len(b) > 1]
    flat = [f for b in candidates for f in b]

    by_sig = {}
    total_sig = len(flat)
    def _sig_worker(f):
        return f, fast_signature(f.path, f.size)
    sig_results = _map_parallel(_sig_worker, flat, workers, on_progress, cancel)
    for f, sig in sig_results.items():
        if sig:
            by_sig.setdefault(sig, []).append(f)

    hash_candidates = [f for b in by_sig.values() if len(b) > 1 for f in b]
    sha_map = {}
    todo = []
    for f in hash_candidates:
        v = _cache_hit(cache, f, "sha")
        if v:
            sha_map[f] = v
        else:
            todo.append(f)

    if todo:
        res = _map_parallel(_hash_worker, todo, workers, on_progress, cancel)
        sha_map.update(res)

    by_hash = {}
    for f in hash_candidates:
        h = sha_map.get(f)
        if h:
            by_hash.setdefault(h, []).append(f)

    for h, bucket in by_hash.items():
        if len(bucket) > 1:
            g = DupGroup(kind=bucket[0].kind, hash_value=h, label="完全一致", items=bucket)
            g.items.sort(key=lambda x: -x.size)
            groups.append(g)

    groups.sort(key=lambda g: -g.saved_bytes)
    for f in hash_candidates:
        if f in sha_map:
            cache[f.path] = {"mtime": f.mtime, "size": f.size, "sha": sha_map[f]}
    return groups


# ------------------------- 相似图片 -------------------------

def group_similar_images(files, threshold=6, cache=None, workers=1,
                         on_progress=None, on_file=None, cancel=None):
    if not files:
        return []
    try:
        from imagehash import phash as _phash_fn  # noqa: F401
    except Exception:
        return []

    if cache is None:
        cache = {}
    phash_map = {}
    todo = []
    for f in files:
        v = _cache_hit(cache, f, "phash")
        if v is not None:
            phash_map[f] = v
        else:
            todo.append(f)

    if todo:
        if on_file:
            for f in todo:
                on_file(f.path)
        res = _map_parallel(_phash_worker, todo, workers, on_progress, cancel)
        phash_map.update(res)

    for f in files:
        v = phash_map.get(f)
        rec = cache.get(f.path, {})
        rec.update({"mtime": f.mtime, "size": f.size, "phash": v})
        cache[f.path] = rec

    valid = [(f, h) for f, h in phash_map.items() if h is not None]
    edges = {}

    def _compare_within(shift, mask):
        buckets = {}
        for f, h in valid:
            buckets.setdefault((h >> shift) & mask, []).append((f, h))
        for items in buckets.values():
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    fa, ha = items[i]
                    fb, hb = items[j]
                    if _hamming(ha, hb) <= threshold:
                        edges.setdefault(id(fa), set()).add(id(fb))
                        edges.setdefault(id(fb), set()).add(id(fa))

    _compare_within(52, 0xFFF)
    _compare_within(40, 0xFFF)
    if not edges:
        return []

    by_id = {id(f): f for f, _ in valid}
    parent = {x: x for x in edges}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, neigh in edges.items():
        for b in neigh:
            union(a, b)

    comps = {}
    for x in edges:
        comps.setdefault(find(x), set()).add(x)

    groups = []
    for comp in comps.values():
        if len(comp) < 2:
            continue
        items = [by_id[x] for x in comp]
        items.sort(key=lambda x: -x.size)
        groups.append(DupGroup(kind="image", hash_value="similar", label="相似(图片)", items=items))
    groups.sort(key=lambda g: -g.saved_bytes)
    return groups


# ------------------------- 相似视频（可选） -------------------------

FRAME_TIMES = (0.08, 0.28, 0.48, 0.68, 0.88)


def extract_video_frame_hashes(path, n_frames=5):
    import io
    import imagehash
    from PIL import Image
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        dur = float(probe.stdout.strip() or "0")
        if dur <= 0:
            return None
    except Exception:
        return None
    hashes = []
    for t in FRAME_TIMES[:n_frames]:
        try:
            p = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(dur * t), "-i", path,
                 "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                capture_output=True, timeout=60)
            if not p.stdout:
                continue
            im = Image.open(io.BytesIO(p.stdout)).convert("RGB")
            hashes.append(int(str(imagehash.phash(im, hash_size=8)), 16))
        except Exception:
            continue
    return hashes or None


def group_similar_videos(files, threshold=10, workers=1, on_progress=None, cancel=None):
    if not files:
        return []
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=10)
    except Exception:
        return []
    frame_maps = {}
    items = [(f.path, 5) for f in files]
    if workers <= 1:
        for i, (p, _) in enumerate(items, 1):
            if cancel is not None and cancel.is_set():
                break
            frame_maps[p] = extract_video_frame_hashes(p)
            if on_progress:
                on_progress(i, len(items))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(lambda a: (a[0], extract_video_frame_hashes(a[0], a[1])), it): it
                    for it in items}
            done = 0
            for fut in as_completed(futs):
                if cancel is not None and cancel.is_set():
                    for ff in futs:
                        ff.cancel()
                    break
                p, hs = fut.result()
                frame_maps[p] = hs
                done += 1
                if on_progress:
                    on_progress(done, len(items))
    valid = [f for f in files if frame_maps.get(f.path)]
    edges = {}
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            a, b = valid[i], valid[j]
            r = a.size / max(1, b.size)
            if not (0.3 <= r <= 3.0):
                continue
            ha, hb = frame_maps[a.path], frame_maps[b.path]
            dists = [_hamming(x, y) for x in ha for y in hb]
            avg = sum(dists) / len(dists) if dists else 64
            if avg <= threshold:
                edges.setdefault(id(a), set()).add(id(b))
                edges.setdefault(id(b), set()).add(id(a))
    by_id = {id(f): f for f in valid}
    parent = {x: x for x in edges}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, neigh in edges.items():
        for b in neigh:
            union(a, b)
    comps = {}
    for x in edges:
        comps.setdefault(find(x), set()).add(x)
    groups = []
    for comp in comps.values():
        if len(comp) < 2:
            continue
        items = [by_id[x] for x in comp]
        items.sort(key=lambda x: -x.size)
        groups.append(DupGroup(kind="video", hash_value="similar", label="相似(视频)", items=items))
    groups.sort(key=lambda g: -g.saved_bytes)
    return groups


# ------------------------- 编排 -------------------------

def find_duplicates(roots, min_size=0, exact=True, similar_images=True,
                    image_similarity=90.0, similar_videos=False, video_threshold=10,
                    workers=1, incremental=True, on_progress=None, on_file=None,
                    on_stage=None, on_error=None, cancel=None):
    cache = load_hash_cache() if incremental else {}
    if on_stage:
        on_stage("正在扫描文件…")
    files = scan_media(roots, min_size=min_size, on_error=on_error, cancel=cancel)

    exact_groups, similar_groups = [], []
    if exact:
        if on_stage:
            on_stage("正在比对完全重复…")
        exact_groups = group_exact_duplicates(
            files, cache=cache, workers=workers, on_progress=on_progress, on_file=on_file,
            on_error=on_error, cancel=cancel)

    if cancel is not None and cancel.is_set():
        if incremental:
            save_hash_cache(cache)
        return ScanResult(files=files, exact_groups=exact_groups)

    if similar_images:
        if on_stage:
            on_stage("正在计算相似图片…")
        threshold = similarity_to_distance(image_similarity)
        remaining = [f for f in files if f.kind == "image"]
        sim = group_similar_images(
            remaining, threshold=threshold, cache=cache, workers=workers,
            on_progress=on_progress, on_file=on_file, cancel=cancel)
        exact_sets = [{f.path for f in eg.items} for eg in exact_groups]
        for g in sim:
            s = {f.path for f in g.items}
            if any(s <= es for es in exact_sets):
                continue
            similar_groups.append(g)

    if cancel is not None and cancel.is_set():
        if incremental:
            save_hash_cache(cache)
        return ScanResult(files=files, exact_groups=exact_groups, similar_groups=similar_groups)

    if similar_videos:
        if on_stage:
            on_stage("正在比对相似视频…")
        similar_groups.extend(group_similar_videos(
            [f for f in files if f.kind == "video"], threshold=video_threshold,
            workers=workers, on_progress=on_progress, cancel=cancel))

    if incremental:
        save_hash_cache(cache)
    return ScanResult(files=files, exact_groups=exact_groups, similar_groups=similar_groups)


# ------------------------- 保留建议 -------------------------

def image_resolution(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width * im.height
    except Exception:
        return 0


def suggest_keep(group, preference="quality", primary_volume="/"):
    items = group.items
    if not items:
        return None
    if preference == "size":
        return max(range(len(items)), key=lambda i: items[i].size)
    if preference == "depth":
        return min(range(len(items)), key=lambda i: (path_depth(items[i].path), -items[i].size))
    if preference == "newest":
        return max(range(len(items)), key=lambda i: (items[i].mtime, items[i].size))
    if preference == "primary":
        on_p = [i for i, f in enumerate(items) if volume_of(f.path) == primary_volume]
        if on_p:
            return min(on_p, key=lambda i: -items[i].size)
        return max(range(len(items)), key=lambda i: items[i].size)
    if group.kind == "image":
        res = [image_resolution(f.path) for f in items]
        return max(range(len(items)), key=lambda i: (res[i], items[i].size, -i))
    return max(range(len(items)), key=lambda i: (items[i].size, -i))
