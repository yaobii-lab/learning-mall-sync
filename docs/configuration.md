# 配置与手动操作

[返回 README](../README.md)

## 手动安装

把整个 `learning-mall-sync` 文件夹安装到 harness 的 Skill 目录中，保持 `SKILL.md`、`scripts/` 和 `references/` 的相对位置。目录由 harness 决定，例如 Claude Code 的 `~/.claude/skills/`、Codex 的 `$CODEX_HOME/skills/`（默认 `~/.codex/skills/`）。Windows 的 `~` 指用户主目录。也可以把整个文件夹交给能读文件的 Dot / personal agent，请它先读 [SKILL.md](../SKILL.md)，再执行同步。

## 保存位置与首次设置

Agent 会读取你的课程列表，让你选择课程、作业说明附件、保存位置、同步周期和通知方式，然后展示待同步数量和每门课的完整保存路径。Harness 没有定时任务能力时，先用手动同步。

| 选项 | 保存位置 |
| --- | --- |
| 本地（默认） | macOS：`~/Documents/LearningMall`；Windows：`%USERPROFILE%\Documents\LearningMall` |
| 网盘同步文件夹 | 检测到的 Google Drive、OneDrive、Dropbox 或 iCloud 本机目录下的 `LearningMall` |
| 自选文件夹 | 用 agent 的文件夹选择器，或提供任意可写路径，包括其他盘符 |

macOS 检测 `~/Library/CloudStorage`、iCloud 与常见目录。Windows 检测 OneDrive 环境路径、Dropbox 客户端配置和用户主目录下的常见网盘目录。Google Drive 虚拟盘、自选盘符或重定向的 Documents 可直接选取，自动检测不保证列出所有安装方式。

文件写入网盘的本机同步文件夹后，由网盘客户端上传。Dot / personal agent 在远端运行时，路径属于那台机器，agent 会说明实际保存在哪里。

例如选择 `/Users/alex/Documents/LearningMall` 后：

```text
LearningMall/
  ADS205/
    _index.md
    Week 1/
      Lecture 1.pdf
      _旧版/
        Lecture 1 (2026-10-21).pdf
        Lecture 1 (2026-10-21) (2).pdf
```

Windows 使用相同的目录结构；文件名中的不兼容字符会替换成 `_`，保留中文。状态与配置单独放在用户主目录的 `.local/state/learning-mall-sync/`，也可用 `LM_SYNC_STATE` 指定。


## 命令行配置

正常使用只需要让 agent 读 Skill，再说“同步课件”或“Learning Mall 有没有更新”。课件按 LM 的周节命名，作业只下载说明附件。视频、论坛、成绩与同学提交不在同步范围。

想检查配置时，在本文件夹里运行：

```sh
# macOS
python3 scripts/lm_sync.py config show
python3 scripts/lm_sync.py config detect
```

```powershell
# Windows PowerShell
py -3 scripts/lm_sync.py config show
py -3 scripts/lm_sync.py config detect
```

保存路径可以包含空格，命令里用引号括起来。例如改默认位置：

```sh
python3 scripts/lm_sync.py config set --key root --value "/Users/alex/Documents/新学期课件"
```

```powershell
py -3 scripts/lm_sync.py config set --key root --value "D:\学习资料\LearningMall"
```

这会更新默认课程路径，单独用 `add-course --dir` 指定的课程目录保持原位置。旧目录里的文件保留，新位置缺少的课件在下一轮重新下载。换学期时移除旧课程、选择新的学期目录，再配置 term 和新课程，避免不同学期混在一起。

通知默认在聊天中汇报。macOS 可选系统通知；Windows 使用聊天或 agent 的推送工具。调整同步周期时，直接告诉 Agent 更新已有定时任务；一次只运行一轮同步。

## 同步历史和问题记录

在仓库根目录运行，`summary` 查看最近完整成功时间，`issues` 查看问题分类：

```sh
# macOS
python3 scripts/lm_sync.py summary
python3 scripts/lm_sync.py issues
```

```powershell
# Windows
py -3 scripts/lm_sync.py summary
py -3 scripts/lm_sync.py issues
```
