"""Learning Mall 课件同步的机械部分：比对、收件、核验、归档、索引、日志、问题回路。

浏览器部分由 agent 完成，只需每门课交一个 JSON（格式见 SKILL.md「课程清单 JSON」）。
课程、存放位置、通知方式都在 config.json 里，由初始化流程用 `config` 子命令写入。
本脚本不联网、不读 Cookie。

Creator: Yaobii <github.com/yaobii-lab>
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import uuid

try:
    import fcntl
except ImportError:  # Windows：没有 flock，单机单进程跑，不加锁
    fcntl = None

STATE = Path(os.environ.get("LM_SYNC_STATE", Path.home() / ".local/state/learning-mall-sync")).expanduser()
LM_BASE = "https://core.xjtlu.edu.cn"

FILE_MODS = {"resource", "folder", "assign"}
SKIP_MODS = {"forum", "moodleoverflow", "bigbluebuttonbn", "url", "page", "quiz", "label", "lti",
             "choice", "feedback", "workshop", "glossary", "zoom", "h5pactivity", "scorm",
             "questionnaire", "attendance", "data", "wiki", "lesson", "book", "chat", "survey",
             "panopto", "turnitintooltwo", "hvp", "subsection"}
RECORDING_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mp3", ".m4a", ".wav"}
MAGIC = {".pdf": b"%PDF-", ".zip": b"PK\x03\x04", ".pptx": b"PK\x03\x04", ".docx": b"PK\x03\x04",
         ".xlsx": b"PK\x03\x04", ".ipynb": b"{"}


def now():
    return datetime.now(timezone.utc)


def today():
    return datetime.now().strftime("%Y-%m-%d")


def die(msg):
    print(f"lm_sync: {msg}", file=sys.stderr)
    sys.exit(2)


def lock(f, exclusive):
    if fcntl:
        fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)


def read_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        lock(f, False)
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, event):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    event = {"at": now().isoformat(), **event}
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        lock(f, True)
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return event


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------- config ----------

def config_path():
    return STATE / "config.json"


def load_config():
    cfg = load_json(config_path(), None)
    if cfg is None:
        die(f"还没有初始化（{config_path()} 不存在）。先按 SKILL.md「初始化」走一遍。")
    if not cfg.get("courses"):
        die("config 里还没有课程，先用 config add-course 加课。")
    return cfg


def courses():
    return tuple(load_config()["courses"])


def downloads_dir():
    return Path(load_config()["downloads"]).expanduser()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def runs_path():
    return STATE / "runs.jsonl"


def issues_path():
    return STATE / "issues.jsonl"


def manifest_path():
    return STATE / "manifest.json"


def plan_path(run, course):
    return STATE / "plans" / f"{run}-{course}.json"


def require_run(run):
    events = read_jsonl(runs_path())
    if not any(e["event"] == "begin" and e["run_id"] == run for e in events):
        die("run_id 没有 begin 记录")
    if any(e["event"] == "finish" and e["run_id"] == run for e in events):
        die("这一轮已经 finish")
    return events


def record_issue(run, course, kind, detail):
    seen = {i["kind"] for i in read_jsonl(issues_path())}
    return append_jsonl(issues_path(), {"run_id": run, "course": course, "kind": kind,
                                        "detail": detail, "first_seen": kind not in seen})


def mod_of(href):
    m = re.search(r"/mod/([a-z0-9_]+)/view\.php\?(?:.*&)?id=(\d+)", href or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def file_rel(url):
    """pluginfile URL → (版本串, 文件相对路径)。版本串含 Moodle 的 content 修订号，老师替换文件时会变。"""
    path = unquote(urlsplit(url).path)
    m = re.search(r"/pluginfile\.php/\d+/[a-z0-9_]+/[a-z0-9_]+/(\d+)/(.+)$", path)
    if not m:
        return None, None
    return path, m.group(2)


def safe_dir(label):
    label = re.sub(r"[\\/:*?\"<>|]+", " ", (label or "").strip()).strip(" .!")
    label = re.sub(r"[\x00-\x1f]", " ", label)
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", label, re.I):
        label = "_" + label
    return label or "Other"


def safe_filename(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).rstrip(" .")
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I):
        name = "_" + name
    return name if name not in {"", ".", ".."} else "file"


def materials(course):
    return Path(load_config()["courses"][course]["dir"]).expanduser()


# ---------- plan ----------

def cmd_plan(args):
    require_run(args.run)
    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    course = data.get("course")
    if course not in courses():
        die(f"未知课程 {course}，config 里的课程是 {', '.join(courses())}")
    take_assign = load_config().get("assignment_attachments", True)
    manifest = load_json(manifest_path(), {}).get(course, {})
    downloads, skipped, unchanged = [], Counter(), 0
    for section in data.get("sections", []):
        label = section.get("label") or "Other"
        for item in section.get("items", []):
            if item.get("skip") == "recording":
                skipped["recording"] += 1
                continue
            mod, mid = mod_of(item.get("href"))
            if mod is None:
                record_issue(args.run, course, "unparsed_href", item.get("href"))
                continue
            if mod in SKIP_MODS or (mod == "assign" and not take_assign):
                skipped[mod] += 1
                continue
            if mod not in FILE_MODS:
                record_issue(args.run, course, f"unknown_mod:{mod}", item.get("href"))
                continue
            if mod == "resource" and item.get("direct"):
                # 浏览器不能预览的格式（csv 等）打开即下载，拿不到 pluginfile 地址；每轮重下，靠字节判断变化。
                name = item["direct"]
                downloads.append({"key": f"resource:{mid}", "section": label, "title": item.get("title") or name,
                                  "view": item.get("href"), "url": item.get("href"), "download_url": None,
                                  "name": name, "version": "direct", "replaces": f"resource:{mid}" in manifest})
                continue
            files = item.get("files") or []
            if mod == "resource" and not files:
                record_issue(args.run, course, "resource_unresolved", item.get("href"))
                continue
            for url in files:
                version, rel = file_rel(url)
                if version is None:
                    record_issue(args.run, course, "not_pluginfile", url)
                    continue
                name = PurePosixPath(rel).name
                if Path(name).suffix.lower() in RECORDING_EXT:
                    skipped["recording"] += 1
                    continue
                key = f"{mod}:{mid}" if mod == "resource" else f"{mod}:{mid}:{rel}"
                prev = manifest.get(key)
                # assign 附件的 URL 不带修订号，替换后看不出来，所以每轮重下、靠字节判断。
                if mod != "assign" and prev and prev["version"] == version and (materials(course) / prev["local"]).is_file():
                    unchanged += 1
                    continue
                base = url.split("?")[0]
                downloads.append({"key": key, "section": label, "title": item.get("title") or name,
                                  "view": item.get("href"), "url": base,
                                  "download_url": base + "?forcedownload=1",
                                  "name": name, "version": version, "replaces": bool(prev)})
    begun = next(e["at"] for e in read_jsonl(runs_path()) if e["event"] == "begin" and e["run_id"] == args.run)
    plan = {"run_id": args.run, "course": course, "planned_at": now().isoformat(), "begun_at": begun,
            "sections": [s.get("label") for s in data.get("sections", [])],
            "downloads": downloads, "skipped": dict(skipped), "unchanged": unchanged}
    save_json(plan_path(args.run, course), plan)
    append_jsonl(runs_path(), {"event": "plan", "run_id": args.run, "course": course,
                               "to_download": len(downloads), "unchanged": unchanged, "skipped": dict(skipped)})
    print(json.dumps({"course": course, "to_download": [{"name": d["name"], "section": d["section"],
                      "download_url": d["download_url"]} for d in downloads if d["download_url"]],
                      "already_downloaded_direct": [d["name"] for d in downloads if not d["download_url"]],
                      "unchanged": unchanged, "skipped": dict(skipped)}, ensure_ascii=False, indent=2))


# ---------- ingest ----------

def find_download(name, since):
    directory = downloads_dir()
    if not directory.is_dir():
        return None
    patterns = [re.compile(re.escape(Path(n).stem) + r"( \(\d+\))?" + re.escape(Path(n).suffix) + r"$")
                for n in {name, safe_filename(name)}]
    cands = [p for p in directory.iterdir() if p.is_file() and any(pat.fullmatch(p.name) for pat in patterns)
             and p.stat().st_mtime >= since.timestamp() - 5]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def looks_valid(path):
    with path.open("rb") as f:
        head = f.read(512)
    if not head:
        return False, "empty"
    expect = MAGIC.get(path.suffix.lower())
    if expect and not head.startswith(expect):
        return False, f"magic mismatch for {path.suffix}"
    if head.lstrip().lower().startswith((b"<!doctype html", b"<html")) and path.suffix.lower() not in {".html", ".htm"}:
        return False, "html page instead of file"
    return True, ""


def retire(path, section_dir, tag):
    """被替换的旧版挪进该周的 _旧版/，不删除。"""
    dest = section_dir / "_旧版"
    dest.mkdir(exist_ok=True)
    target = dest / f"{path.stem} ({tag}){path.suffix}"
    n = 2
    while target.exists():
        target = dest / f"{path.stem} ({tag}) ({n}){path.suffix}"
        n += 1
    path.rename(target)


def unmapped_local(course, manifest):
    mapped = {v["local"] for v in manifest.values()}
    root = materials(course)
    return {p.name: p for p in root.rglob("*") if p.is_file() and not p.name.startswith(("_", "."))
            and str(p.relative_to(root)) not in mapped and "_旧版" not in p.parts}


def cmd_ingest(args):
    require_run(args.run)
    plan = load_json(plan_path(args.run, args.course), None)
    if plan is None:
        die("这门课本轮还没有 plan")
    all_manifest = load_json(manifest_path(), {})
    manifest = all_manifest.setdefault(args.course, {})
    since = datetime.fromisoformat(plan.get("begun_at", plan["planned_at"]))
    root = materials(args.course)
    results = []
    for d in plan["downloads"]:
        if d.get("done"):
            continue
        got = find_download(d["name"], since)
        if got is None:
            results.append({"name": d["name"], "status": "missing"})
            continue
        ok, why = looks_valid(got)
        if not ok:
            record_issue(args.run, args.course, "invalid_download", f"{d['name']}: {why}")
            got.unlink()
            results.append({"name": d["name"], "status": "invalid", "reason": why})
            continue
        digest, size = sha256(got), got.stat().st_size
        section_dir = root / safe_dir(d["section"])
        section_dir.mkdir(parents=True, exist_ok=True)
        prev = manifest.get(d["key"])
        old = root / prev["local"] if prev and (root / prev["local"]).is_file() else None
        local = None if prev else unmapped_local(args.course, manifest).get(d["name"])
        handled = old or local
        filename = safe_filename(d["name"])
        target = section_dir / filename
        if target.exists() and target != handled:
            target = section_dir / f"{Path(filename).stem} [{d['key'].split(':')[1]}]{Path(filename).suffix}"
            n = 2
            while target.exists() and target != handled:
                target = section_dir / f"{Path(filename).stem} [{d['key'].split(':')[1]}] ({n}){Path(filename).suffix}"
                n += 1
        if handled is not None and sha256(handled) == digest:
            action = "same_bytes" if old else "adopted"
            got.unlink()
            if handled != target:
                handled.rename(target)
        else:
            if old is not None:
                retire(old, section_dir, today())
                action = "updated"
            elif local is not None:
                retire(local, section_dir, "本地")
                action = "adopted_replaced"
            else:
                action = "new"
            shutil.move(str(got), target)
        rel_target = target.relative_to(root).as_posix()
        manifest[d["key"]] = {"title": d["title"], "section": d["section"], "view": d["view"], "url": d["url"],
                              "version": d["version"], "local": rel_target, "sha256": digest, "size": size,
                              "first_seen": (prev or {}).get("first_seen", today()),
                              "updated": today() if action in ("new", "updated", "adopted_replaced") else (prev or {}).get("updated", today())}
        d["done"] = True
        append_jsonl(runs_path(), {"event": "asset", "run_id": args.run, "course": args.course, "source": d["key"],
                                   "version": d["version"], "local_path": str(target), "size": size, "action": action})
        results.append({"name": d["name"], "status": action, "local": rel_target})
    save_json(manifest_path(), all_manifest)
    save_json(plan_path(args.run, args.course), plan)
    write_index(args.course, manifest)
    print(json.dumps(results, ensure_ascii=False, indent=2))


def write_index(course, manifest):
    root = materials(course)
    by_section = {}
    for v in manifest.values():
        by_section.setdefault(v["section"], []).append(v)

    def order(label):
        m = re.match(r"(?:W|Week\s*|Lecture\s*)(\d+)", label, re.I) or re.match(r"(\d+)\.", label)
        return (0, int(m.group(1))) if m else (-1, 0) if label.lower().startswith("welcome") else (1, 0)

    lines = [f"# {course} 课件", "", f"由 learning-mall-sync 自动生成，更新于 {datetime.now().strftime('%Y-%m-%d %H:%M')}。手动修改会被覆盖。", ""]
    for label in sorted(by_section, key=lambda s: (order(s), s)):
        lines += [f"## {label}", "", "| 文件 | 更新 | LM |", "| --- | --- | --- |"]
        for v in sorted(by_section[label], key=lambda v: v["local"]):
            lines.append(f"| [{Path(v['local']).name}](<{v['local']}>) | {v['updated']} | [打开]({v['view']}) |")
        lines.append("")
    extra = sorted(unmapped_local(course, manifest))
    if extra:
        lines += ["## 不在 LM 上的本地文件", ""] + [f"- {n}" for n in extra] + [""]
    root.mkdir(parents=True, exist_ok=True)
    (root / "_index.md").write_text("\n".join(lines), encoding="utf-8")


# ---------- finish / report ----------

def cmd_issue(args):
    require_run(args.run)
    print(json.dumps(record_issue(args.run, args.course, args.kind, args.detail), ensure_ascii=False))


def cmd_finish(args):
    events = require_run(args.run)
    start = next(e for e in events if e["event"] == "begin" and e["run_id"] == args.run)
    plans = {c: load_json(plan_path(args.run, c), None) for c in start["requested"]}
    planned = [c for c, p in plans.items() if p]
    unchecked = [c for c, p in plans.items() if not p]
    pending = [(c, d["name"]) for c, p in plans.items() if p for d in p["downloads"] if not d.get("done")]
    issues = [i for i in read_jsonl(issues_path()) if i["run_id"] == args.run]
    problems = [i for i in issues if i["kind"] not in {"possible_video_skipped", "assign_no_attachment"}
                and (i["kind"] != "invalid_download" or any(c == i["course"] for c, _ in pending))]
    assets = [e for e in events if e["event"] == "asset" and e["run_id"] == args.run]
    changed = [e for e in assets if e["action"] in ("new", "updated", "adopted_replaced")]
    if args.blocked:
        status = "blocked"
    elif unchecked or pending or problems:
        status = "partial"
    else:
        status = "changed" if changed else "unchanged"
    finish = append_jsonl(runs_path(), {"event": "finish", "run_id": args.run, "status": status,
                                        "checked": planned, "uploaded": len(changed), "failed": len(pending),
                                        "unchecked": unchecked, "issues": len(problems),
                                        "pending": [f"{c}:{n}" for c, n in pending], "reason": args.blocked or args.note or "",
                                        "duration_seconds": round((now() - datetime.fromisoformat(start["at"])).total_seconds(), 1)})
    visible_issues = [i for i in issues if i in problems or i["first_seen"]]
    report = build_report(status, changed, pending, visible_issues, args.blocked)
    if unchecked:
        report += ("\n" if report else "") + "尚未检查课程：" + "，".join(unchecked)
    (STATE / "last_report.txt").write_text(report, encoding="utf-8")
    notify = load_config().get("notify", {"via": "chat"})
    if report and notify.get("via") == "system":
        system_notify(report)
    print(json.dumps({"status": status, "notify": notify if report else None, "report": report, "finish": finish},
                     ensure_ascii=False, indent=2))


def system_notify(text):
    if sys.platform != "darwin":
        return
    script = f"display notification {json.dumps(text[:200])} with title \"Learning Mall 课件\""
    subprocess.run(["osascript", "-e", script], check=False)


def build_report(status, changed, pending, new_issues, blocked):
    parts = []
    if blocked:
        parts.append(f"Learning Mall 同步卡住了：{blocked}")
    by_course = {}
    for e in changed:
        kind = "更新" if e["action"] != "new" else "新增"
        path = Path(e["local_path"])
        by_course.setdefault(e["course"], {}).setdefault((path.parent.name, kind), []).append(path.stem)
    for c, groups in by_course.items():
        chunks = []
        for (week, kind), names in groups.items():
            lead = next((n for n in names if "lecture" in n.lower()), names[0])
            chunks.append(f"{week} {kind} {lead}" + (f" 等 {len(names)} 个" if len(names) > 1 else ""))
        parts.append(f"{c}：" + "；".join(chunks))
    if pending:
        parts.append("没下载成功：" + "，".join(f"{c} {n}" for c, n in pending))
    for i in new_issues:
        parts.append(f"需要留意（{i['course']}）：{i['kind']} — {i['detail']}")
    return "\n".join(parts)


def cmd_begin(args):
    print(json.dumps(append_jsonl(runs_path(), {"event": "begin", "run_id": str(uuid.uuid4()),
                                                "requested": list(courses())}), ensure_ascii=False))


def cmd_summary(args):
    events = read_jsonl(runs_path())
    cutoff = now() - timedelta(days=args.days)
    begins = {e["run_id"]: e for e in events if e["event"] == "begin" and datetime.fromisoformat(e["at"]) >= cutoff}
    finishes = {e["run_id"]: e for e in events if e["event"] == "finish"}
    statuses = Counter(finishes[r]["status"] if r in finishes else "unfinished" for r in begins)
    ok = [finishes[r] for r in begins if r in finishes and finishes[r]["status"] in ("changed", "unchanged")]
    manifest = load_json(manifest_path(), {})
    print(json.dumps({"days": args.days, "runs": len(begins), "statuses": dict(statuses),
                      "last_full_success": max((f["at"] for f in ok), default=None),
                      "files_per_course": {c: len(manifest.get(c, {})) for c in courses()}},
                     ensure_ascii=False, indent=2))


def cmd_issues(args):
    rows = {}
    for i in read_jsonl(issues_path()):
        r = rows.setdefault(i["kind"], {"count": 0, "first": i["at"], "last": i["at"], "example": i["detail"]})
        r["count"] += 1
        r["last"] = i["at"]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cloud_folders():
    """本机可能存在的网盘同步文件夹。放进去的文件由网盘客户端自己上传，脚本不碰任何网盘 API。"""
    home = Path.home()
    found = []
    def add(kind, path):
        path = Path(path).expanduser()
        if path.is_dir() and not any(Path(f["path"]) == path for f in found):
            found.append({"kind": kind, "path": str(path)})

    for p in sorted((home / "Library/CloudStorage").glob("*")) if (home / "Library/CloudStorage").is_dir() else []:
        if not p.is_dir() or p.name.startswith("."):
            continue
        name = p.name.lower()
        kind = ("Google Drive" if name.startswith("googledrive") else "OneDrive" if name.startswith("onedrive")
                else "Dropbox" if name.startswith("dropbox") else p.name)
        base = next((p / s for s in ("My Drive", "我的云端硬盘") if (p / s).is_dir()), p)
        add(kind, base)
    icloud = home / "Library/Mobile Documents/com~apple~CloudDocs"
    if icloud.is_dir():
        add("iCloud Drive", icloud)
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(key):
            add("OneDrive", os.environ[key])
    for name, kind in (("Google Drive", "Google Drive"), ("OneDrive", "OneDrive"),
                       ("Dropbox", "Dropbox"), ("iCloudDrive", "iCloud Drive"),
                       ("iCloud Drive", "iCloud Drive")):
        if not any(f["kind"] == kind for f in found):
            add(kind, home / name)
    # Dropbox 可安装到自选盘符，客户端配置比猜盘符可靠。
    for env_key in ("APPDATA", "LOCALAPPDATA"):
        if not os.environ.get(env_key):
            continue
        info = Path(os.environ[env_key]) / "Dropbox/info.json"
        try:
            accounts = load_json(info, {})
            for account in accounts.values():
                if account.get("path"):
                    add("Dropbox", account["path"])
        except (OSError, ValueError, AttributeError):
            continue
    return found


def cmd_config(args):
    cfg = load_json(config_path(), None)
    if args.action == "show":
        print(json.dumps({"config_path": str(config_path()), "config": cfg}, ensure_ascii=False, indent=2))
    elif args.action == "detect":
        print(json.dumps({"default_root": str(Path.home() / "Documents/LearningMall"),
                          "downloads": str(Path.home() / "Downloads"),
                          "cloud_folders": cloud_folders()}, ensure_ascii=False, indent=2))
    elif args.action == "init":
        if cfg and not args.force:
            die("已经有 config 了；要重来加 --force（课程列表会清空，已下载的文件和 manifest 不动）。")
        root = Path(args.root).expanduser().absolute()
        root.mkdir(parents=True, exist_ok=True)
        cfg = {"root": str(root), "downloads": str(Path(args.downloads).expanduser().absolute()), "term": args.term or "",
               "assignment_attachments": args.assignments == "yes",
               "notify": {"via": args.notify, "hint": args.notify_hint or ""}, "courses": {}}
        save_json(config_path(), cfg)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
    else:
        if cfg is None:
            die("先 config init。")
        if args.action == "add-course":
            if not args.code or not args.id:
                die("add-course 需要 --code 和 --id")
            previous = cfg["courses"].get(args.code, {})
            d = (Path(args.dir).expanduser().absolute() if args.dir else
                 Path(previous.get("dir", Path(cfg["root"]) / safe_dir(args.code))))
            cfg["courses"][args.code] = {"id": int(args.id), "url": f"{LM_BASE}/course/view.php?id={args.id}",
                                         "title": args.title or "", "dir": str(d)}
        elif args.action == "remove-course":
            cfg["courses"].pop(args.code, None)
        elif args.action == "set":
            if not args.key or args.value is None:
                die("set 需要 --key 和 --value")
            value = {"true": True, "false": False}.get(args.value, args.value)
            if args.key in ("notify.via", "notify.hint"):
                if args.key == "notify.via" and value not in {"chat", "system", "agent"}:
                    die("notify.via 必须是 chat、system 或 agent")
                cfg.setdefault("notify", {})[args.key.split(".")[1]] = value
            elif args.key == "root":
                value = str(Path(value).expanduser().absolute())
                for code, course in cfg["courses"].items():
                    if Path(course["dir"]) == Path(cfg["root"]) / safe_dir(code):
                        course["dir"] = str(Path(value) / safe_dir(code))
                cfg["root"] = value
            elif args.key == "downloads":
                cfg["downloads"] = str(Path(value).expanduser().absolute())
            elif args.key == "assignment_attachments":
                if not isinstance(value, bool):
                    die("assignment_attachments 必须是 true 或 false")
                cfg[args.key] = value
            elif args.key == "term":
                cfg[args.key] = value
            else:
                die(f"不认识的 key：{args.key}")
        save_json(config_path(), cfg)
        print(json.dumps(cfg, ensure_ascii=False, indent=2))


def main(argv=None):
    # Windows 控制台的默认编码未必能表示中文课程名；CLI JSON 统一输出 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("config")
    s.add_argument("action", choices=["show", "detect", "init", "add-course", "remove-course", "set"])
    s.add_argument("--root"); s.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    s.add_argument("--term"); s.add_argument("--assignments", choices=["yes", "no"], default="yes")
    s.add_argument("--notify", choices=["chat", "system", "agent"], default="chat"); s.add_argument("--notify-hint")
    s.add_argument("--force", action="store_true")
    s.add_argument("--code"); s.add_argument("--id"); s.add_argument("--title"); s.add_argument("--dir")
    s.add_argument("--key"); s.add_argument("--value")
    sub.add_parser("begin")
    s = sub.add_parser("plan"); s.add_argument("--run", required=True); s.add_argument("--input", required=True)
    s = sub.add_parser("ingest"); s.add_argument("--run", required=True); s.add_argument("--course", required=True)
    s = sub.add_parser("issue"); s.add_argument("--run", required=True); s.add_argument("--course", required=True)
    s.add_argument("--kind", required=True); s.add_argument("--detail", default="")
    s = sub.add_parser("finish"); s.add_argument("--run", required=True); s.add_argument("--blocked"); s.add_argument("--note")
    s = sub.add_parser("summary"); s.add_argument("--days", type=int, default=14)
    sub.add_parser("issues")
    args = p.parse_args(argv)
    if args.cmd == "config" and args.action == "init" and not args.root:
        p.error("config init 需要 --root")
    if args.cmd == "ingest" and args.course not in courses():
        die(f"未知课程 {args.course}")
    {"config": cmd_config, "begin": cmd_begin, "plan": cmd_plan, "ingest": cmd_ingest, "issue": cmd_issue, "finish": cmd_finish,
     "summary": cmd_summary, "issues": cmd_issues}[args.cmd](args)


if __name__ == "__main__":
    main()
