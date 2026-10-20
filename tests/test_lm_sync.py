"""Portable CLI integration tests using synthetic course files only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lm_sync.py"


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lm-sync-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.downloads = self.base / "下载 Downloads"
        self.downloads.mkdir()
        self.root = self.base / "课程 LearningMall"
        self.env = {**os.environ, "LM_SYNC_STATE": str(self.base / "state"),
                    "HOME": str(self.base), "USERPROFILE": str(self.base),
                    "APPDATA": str(self.base / "AppData/Roaming"),
                    "LOCALAPPDATA": str(self.base / "AppData/Local")}
        for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            self.env.pop(key, None)
        self.cli("config", "init", "--root", self.root, "--downloads", self.downloads,
                 "--term", "2627-S1")
        self.cli("config", "add-course", "--code", "TEST101", "--id", "1")

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                env=self.env, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def item(self, revision=1, mid=1, name="讲义.pdf"):
        return {"href": f"https://core.xjtlu.edu.cn/mod/resource/view.php?id={mid}",
                "files": [f"https://core.xjtlu.edu.cn/pluginfile.php/1/mod_resource/content/{revision}/{name}"]}

    def plan(self, items):
        run = self.cli("begin")["run_id"]
        source = self.base / "课程.json"
        source.write_text(json.dumps({"course": "TEST101", "sections": [
            {"label": "Week 1", "items": items}]}, ensure_ascii=False), encoding="utf-8")
        plan = self.cli("plan", "--run", run, "--input", source)
        return run, plan

    def sync(self, revision):
        run, _ = self.plan([self.item(revision)])
        (self.downloads / "讲义.pdf").write_bytes(f"%PDF-{revision}".encode())
        self.cli("ingest", "--run", run, "--course", "TEST101")
        return self.cli("finish", "--run", run)

    def test_same_day_replacements_preserve_all_old_bytes(self):
        for revision in (1, 2, 3):
            self.assertEqual(self.sync(revision)["status"], "changed")
        week = self.root / "TEST101" / "Week 1"
        self.assertEqual((week / "讲义.pdf").read_bytes(), b"%PDF-3")
        self.assertEqual(sorted(p.read_bytes() for p in (week / "_旧版").iterdir()),
                         [b"%PDF-1", b"%PDF-2"])

    def test_unresolved_resource_stays_partial_and_visible_on_every_run(self):
        for _ in range(2):
            run, _ = self.plan([{"href": self.item()["href"], "files": []}])
            result = self.cli("finish", "--run", run)
            self.assertEqual(result["status"], "partial")
            self.assertIn("resource_unresolved", result["report"])
        self.assertIsNone(self.cli("summary")["last_full_success"])

    def test_unchecked_course_is_reported(self):
        self.cli("config", "add-course", "--code", "TEST102", "--id", "2")
        run, _ = self.plan([])
        result = self.cli("finish", "--run", run)
        self.assertEqual(result["status"], "partial")
        self.assertIn("TEST102", result["report"])

    def test_changing_root_retargets_default_courses_and_preserves_custom_dir(self):
        custom = self.base / "自选目录"
        self.cli("config", "add-course", "--code", "TEST102", "--id", "2", "--dir", custom)
        self.sync(1)
        new_root = self.base / "新目录"
        self.cli("config", "set", "--key", "root", "--value", new_root)
        cfg = self.cli("config", "show")["config"]
        self.assertEqual(Path(cfg["courses"]["TEST101"]["dir"]), new_root / "TEST101")
        self.assertEqual(Path(cfg["courses"]["TEST102"]["dir"]), custom)
        self.assertTrue((self.root / "TEST101/Week 1/讲义.pdf").is_file())
        _, plan = self.plan([self.item()])
        self.assertEqual(len(plan["to_download"]), 1)

    def test_missing_download_directory_is_partial_instead_of_crashing(self):
        self.downloads.rmdir()
        run, _ = self.plan([self.item()])
        result = self.cli("ingest", "--run", run, "--course", "TEST101")
        self.assertEqual(result[0]["status"], "missing")
        self.assertEqual(self.cli("finish", "--run", run)["status"], "partial")

    def test_windows_reserved_section_and_filename_are_portable(self):
        run = self.cli("begin")["run_id"]
        source = self.base / "input.json"
        source.write_text(json.dumps({"course": "TEST101", "sections": [
            {"label": "CON", "items": [self.item(name="A%3AB.pdf")]}]}), encoding="utf-8-sig")
        self.cli("plan", "--run", run, "--input", source)
        # A real Windows browser replaces characters it cannot save.
        (self.downloads / "A_B.pdf").write_bytes(b"%PDF-portable")
        result = self.cli("ingest", "--run", run, "--course", "TEST101")
        self.assertEqual(result[0]["status"], "new")
        self.assertEqual((self.root / "TEST101/_CON/A_B.pdf").read_bytes(), b"%PDF-portable")

    def test_unchanged_run_does_not_download_or_notify(self):
        self.sync(1)
        run, plan = self.plan([self.item()])
        self.assertEqual(plan["to_download"], [])
        result = self.cli("finish", "--run", run)
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(result["report"], "")

    def test_html_login_response_is_rejected(self):
        run, _ = self.plan([self.item()])
        (self.downloads / "讲义.pdf").write_text("<!DOCTYPE html><html>Login</html>", encoding="utf-8")
        result = self.cli("ingest", "--run", run, "--course", "TEST101")
        self.assertEqual(result[0]["status"], "invalid")
        self.assertEqual(self.cli("finish", "--run", run)["status"], "partial")

    def test_valid_retry_can_finish_successfully_after_invalid_download(self):
        run, _ = self.plan([self.item()])
        (self.downloads / "讲义.pdf").write_bytes(b"<html>Login</html>")
        self.cli("ingest", "--run", run, "--course", "TEST101")
        (self.downloads / "讲义.pdf").write_bytes(b"%PDF-valid")
        self.cli("ingest", "--run", run, "--course", "TEST101")
        self.assertEqual(self.cli("finish", "--run", run)["status"], "changed")

    def test_repeated_assignment_with_same_bytes_does_not_notify(self):
        item = {"href": "https://core.xjtlu.edu.cn/mod/assign/view.php?id=9",
                "files": ["https://core.xjtlu.edu.cn/pluginfile.php/1/mod_assign/introattachment/0/task.pdf"]}
        for expected in ("changed", "unchanged"):
            run, _ = self.plan([item])
            (self.downloads / "task.pdf").write_bytes(b"%PDF-task")
            self.cli("ingest", "--run", run, "--course", "TEST101")
            self.assertEqual(self.cli("finish", "--run", run)["status"], expected)

    def test_detect_finds_windows_onedrive_environment_path(self):
        folder = self.base / "OneDrive - University"
        folder.mkdir()
        self.env["OneDriveCommercial"] = str(folder)
        detected = self.cli("config", "detect")["cloud_folders"]
        self.assertIn({"kind": "OneDrive", "path": str(folder)}, detected)

    def test_course_with_custom_dir_keeps_it_when_title_is_refreshed(self):
        custom = self.base / "自选"
        self.cli("config", "add-course", "--code", "TEST101", "--id", "1", "--dir", custom)
        self.cli("config", "add-course", "--code", "TEST101", "--id", "1", "--title", "New title")
        cfg = self.cli("config", "show")["config"]
        self.assertEqual(Path(cfg["courses"]["TEST101"]["dir"]), custom)

    def test_recording_is_skipped_without_incomplete_status(self):
        run, plan = self.plan([{"href": self.item()["href"], "skip": "recording"}])
        self.assertEqual(plan["to_download"], [])
        self.assertEqual(self.cli("finish", "--run", run)["status"], "unchanged")

    def test_manual_file_is_adopted_and_index_is_written(self):
        manual = self.root / "TEST101" / "讲义.pdf"
        manual.parent.mkdir(parents=True)
        manual.write_bytes(b"%PDF-1")
        result = self.sync(1)
        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(manual.exists())
        index = (manual.parent / "_index.md").read_text(encoding="utf-8")
        self.assertIn("讲义.pdf", index)
        self.assertIn("Week 1", index)
        self.assertIn("[讲义.pdf](<Week 1/讲义.pdf>)", index)

    def test_browser_numbered_filename_is_received(self):
        run, _ = self.plan([self.item()])
        (self.downloads / "讲义 (1).pdf").write_bytes(b"%PDF-1")
        result = self.cli("ingest", "--run", run, "--course", "TEST101")
        self.assertEqual(result[0]["status"], "new")
        self.assertEqual(self.cli("finish", "--run", run)["status"], "changed")

    def test_detect_finds_macos_cloudstorage(self):
        cloud = self.base / "Library/CloudStorage/GoogleDrive-test/My Drive"
        cloud.mkdir(parents=True)
        detected = self.cli("config", "detect")["cloud_folders"]
        self.assertIn({"kind": "Google Drive", "path": str(cloud)}, detected)

    def test_detect_finds_windows_dropbox_custom_drive(self):
        cloud = self.base / "自选 Dropbox"
        cloud.mkdir()
        info = Path(self.env["APPDATA"]) / "Dropbox/info.json"
        info.parent.mkdir(parents=True)
        info.write_text(json.dumps({"personal": {"path": str(cloud)}}), encoding="utf-8")
        detected = self.cli("config", "detect")["cloud_folders"]
        self.assertIn({"kind": "Dropbox", "path": str(cloud)}, detected)


if __name__ == "__main__":
    unittest.main()
