# 变更记录（Yaobii 自用阶段，公开化之前）

- 2026-10-08：初版，目标是 Google Drive，靠 `downloadMedia` 下载，多次超时，定时任务没有启用。
- 2026-10-11：目标改成 Vault materials 并按周分文件夹，录播跳过（她定的）。下载改用 `forcedownload`，CUA 守护进程加上 existing-profile grant；机械部分移到 `lm_sync.py`，增加 `_index.md` 和问题回路。
- 2026-10-12：四门课首次补齐（74 个文件），枚举改用 overview 页的课程目录，补上子节、作业附件、视频跳过、直接下载类型（csv、mlx、zip）的处理。
- 2026-10-18：补上 Codex Chrome 扩展入口；下载改为先登记 download 事件、再打开 forcedownload 地址并核验返回路径，记录与原生 Chrome 权限拒绝的区别；增加分批保存和防止误用上一份文件 URL 的检查。
