<div align="center">

<a href="README.md">简体中文</a> · <b>English</b>

<img src="assets/cover.png" alt="Learning Mall Sync" width="100%">

# Learning Mall Sync

**Let your AI agent automatically download XJTLU course materials on a schedule and organize them locally or in cloud storage.**

[![CI](https://github.com/yaobii-lab/learning-mall-sync/actions/workflows/tests.yml/badge.svg)](https://github.com/yaobii-lab/learning-mall-sync/actions/workflows/tests.yml) · [MIT](LICENSE) · macOS & Windows

<a href="#quick-start">🚀 Quick start</a> · <a href="#schedule">🗓️ Scheduled sync</a> · <a href="#storage">📁 Save locations</a> · <a href="https://github.com/yaobii-lab/learning-mall-sync/releases/latest">📦 Download Skill</a>

</div>

Give this Skill to WorkBuddy, Codex, Muse, or another capable AI agent. Choose your courses, save location, and sync schedule, then let it handle the updates.

## 💬 Just ask your agent

> Sync this semester's Learning Mall course materials to OneDrive. Check every two days, and notify me when new materials appear or a lecturer replaces a file.

On the first run, your agent guides you through choosing courses, connecting a browser, and confirming where and when to save files. You sign in and authorize browser access yourself. Later runs reuse that browser's login session.

| 🔐 Sign in once | 🗓️ Sync on your schedule | ☁️ Choose where files go |
| --- | --- | --- |
| Reuse your browser session | Daily, every two days, or weekly | Local folders or cloud sync folders |

New and replaced files are detected, previous versions are kept, and each course gets a clickable index.

<details>
<summary>📂 Preview the folder structure</summary>

Your folders will look like this (example):

```text
LearningMall/
└── ADS205/
    ├── _index.md
    ├── Week 1/
    │   └── Lecture 1.pdf
    └── Week 2/
        ├── Lecture 2.pdf
        └── _旧版/
            └── Lecture 2 (2026-10-21).pdf
```

`_旧版` holds previous versions. Course and section names follow Learning Mall.

</details>

<a id="quick-start"></a>

## 🚀 Quick start

### 1. Install the Skill

Give your agent the [repository link](https://github.com/yaobii-lab/learning-mall-sync) or the [Skill package from Releases](https://github.com/yaobii-lab/learning-mall-sync/releases/latest). Ask it to install the Skill and read [SKILL.md](SKILL.md). If your agent offers a Skill import screen, you can import the package there.

<details>
<summary>Install with the command line</summary>

If you prefer the command line, run this and choose your agent:

```bash
npx skills add yaobii-lab/learning-mall-sync -g
```

For other installation options, see [manual installation (Chinese)](docs/configuration.md#手动安装).

</details>

### 2. Tell your agent what you need

> Help me sync my Learning Mall course materials. This is my first time: guide me through choosing courses, a save location, and a sync schedule.

Your agent checks its browser tools first. If a new tool is needed, **CUA Driver** is the first recommendation; the host's recommended **browser-use** integration or an existing Dot / personal agent browser can also work. See the [browser setup notes (Chinese)](references/browser-tools.md).

### 3. Sign in, choose courses, and start

Sign in to [Learning Mall Core](https://core.xjtlu.edu.cn/) in your browser and authorize your agent to use it. The agent lists your courses and helps you choose a save location, whether to include assignment instruction attachments, a sync schedule, and notifications. It shows the pending download count and each course's full destination path before archiving files.

Requires Python 3.10+ and an agent that supports Skills, can run commands, read and write files, and operate a browser. The Python script uses only the standard library.

<a id="schedule"></a>

## 🗓️ Login and scheduled sync

**Sign in and authorize once, then reuse the session.** Sync uses the same browser environment. If the university's single sign-on session is still valid, sign-in can resume automatically. When the university requires verification again, your agent asks you to complete it in the browser.

**Choose your own schedule:** daily, every two days, weekly, or another supported time. For example:

> Sync every Sunday at 8 PM. Only notify me when course materials change.

Your agent host manages scheduling and needs access to the browser and destination folder when the task runs. For local execution, keep the computer and agent running. If your host does not support scheduling, ask it to sync manually whenever you need.

<a id="storage"></a>

## 📁 Where files go

| Destination | What happens |
| --- | --- |
| A folder on your computer | Defaults to `LearningMall` under your user's Documents folder; you can choose another folder or drive |
| Google Drive, OneDrive, iCloud Drive, or Dropbox | Files are saved in the desktop client's local sync folder, then uploaded by that client for access on other devices |

Cloud sync requires the provider's desktop client to be installed and signed in. The agent helps find or select its local sync folder and shows the full path. If your Dot / personal agent runs remotely, it explains where files are saved on that machine.

## 💬 FAQ

**What gets downloaded?** Course files and, optionally, attachments in assignment instructions. Recordings, forums, grades, and student submissions are excluded.

**Does every run download everything again?** Files with revision identifiers are skipped when the local file is present and the revision is unchanged. Assignment attachments and some direct downloads must be downloaded again to compare their contents; identical content is not saved twice.

**What if sync gets stuck?** Your agent reports the affected course and cause. `partial` means work remains; `blocked` means something such as sign-in needs attention. The [configuration guide (Chinese)](docs/configuration.md) explains how to inspect settings, sync history, and recorded issues.

## 🛠️ Development and feedback

<details>
<summary>Run the tests and report an issue</summary>

The CLI regression tests use temporary folders and synthetic files on macOS and Windows. From the repository folder, run:

```sh
# macOS
python3 -m unittest discover -s tests -v
```

```powershell
# Windows
py -3 -m unittest discover -s tests -v
```

Validate browser sign-in and a real download with one file in your chosen agent host. For bug reports, include your operating system, host, browser tool, and redacted errors. See [Contributing (Chinese)](CONTRIBUTING.md); English reports are welcome.

</details>

## 📄 License

[MIT](LICENSE). An unofficial XJTLU project. Course materials remain the property of their respective rights holders and are for your personal study. Do not publicly upload course materials or login data.

The cover uses an edited [LM Core dashboard](https://core.xjtlu.edu.cn/my/) with illustrative course data. The interface and university marks belong to XJTLU.
