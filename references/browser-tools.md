# 浏览器工具接入

先检查当前 agent 已有的工具。可以读课程 DOM、读取当前 URL、下载并取得实际文件路径，就可以直接用，不需要为了这个 Skill 换浏览器。

需要安装时：

| 选择 | 安装与接入 |
| --- | --- |
| CUA Driver（首推） | 读 [CUA 接入说明](cua-driver.md)，按官方文档选择 macOS / Windows 版本，连接到 harness 的 MCP 或 CLI |
| harness 推荐的 browser-use | 使用 harness 推荐的发行版及安装方式；Browser Use 官方 [项目入口](https://github.com/browser-use/browser-use) 与 [Browser Harness 安装文档](https://github.com/browser-use/browser-harness/blob/main/install.md) 可作参考 |
| Dot / personal agent 内置浏览器 | 按已有工具说明操作；确认下载文件能被运行 Python 脚本的环境读到，向用户展示完整保存路径 |
| Codex 浏览器扩展 | 按 [Codex 流程](codex-chrome.md) 读取 DOM、等待下载并核对落盘路径 |

接好后试一次：用户登录 `https://core.xjtlu.edu.cn/`，agent 开自己的课程工作页，读取课程名与资源链接，再下载一份小课件，执行 ingest 确认能归档。安装、授权和 API 以当前工具提供的说明为准。

浏览器有时将文件放入专用下载目录。将 `config set --key downloads --value "<实际目录>"` 指向它；最终保存位置是 config 中每门课的 `dir`，两者会在初始化时说明。
