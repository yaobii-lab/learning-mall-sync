# CUA Driver 接入

需要新装浏览器工具时首推 [CUA Driver](https://github.com/trycua/cua/tree/main/libs/cua-driver)。它提供 MCP / CLI；安装和接入按 [官方文档](https://cua.ai/docs) 及对应操作系统说明进行，macOS 与 Windows 使用各自的安装包和权限流程。

1. 安装对应版本，把 `cua-driver mcp` 注册到 harness（或使用它支持的 CLI 接入）。运行官方诊断，按提示完成操作系统权限。
2. 加载安装包提供的 CUA Skill 和当前工具 schema，按现场 API 创建工作会话。
3. 使用有 Learning Mall 登录态的浏览器。连接现有 Chromium profile 时，走 CUA 的 existing-profile 授权流程；也可以在新环境中让用户登录一次。
4. 新建自己的工作标签页，读取课程目录、资源链接和当前 URL。每次重新绑定浏览器后，根据 URL 找回工作页，旧 tab ID 可能已失效。
5. 先测试一份文件的下载，取得实际落盘路径，把 downloads 配置指向该目录，再交给脚本 ingest。

使用既有 profile 的授权由启动器或宿主按官方流程提供，参数以安装版本的说明为准。权限拒绝时按工具提示处理。

枚举用 overview 页的课程目录。页面快照被截断时改为完整 DOM 读取或分段枚举，不能把前几百个元素当全量。导航超时先核对 URL；确认文件落盘才算下载成功。同步后关掉本轮新建的工作页。
