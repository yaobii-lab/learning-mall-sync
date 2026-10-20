# Codex Chrome 扩展同步流程

仅在当前会话提供 `cua_repl` 时使用。先按工具说明初始化并阅读返回文档；以下代码是顺序示例，句柄创建方式以现场 API 为准。不用 shell、Cookie 或另一套浏览器控制器替代它。

## 工作页与枚举

用 `cua.createBrowserTab("chrome", overviewUrl, {sessionName: "📚 课件同步"})` 创建自己的工作页，保留句柄。不要导航用户已有的课程标签页。课程标题必须包含课程代码与 config 里的学期码。如果目录未展开，点可见的 “Open course index”。

在 `course/overview.php?id=...&expand[]=resource` 上读取当前 DOM 的 `[id^="course-index-section-"]`：

- 周节名取该节的 `a[href*="/course/section.php"]` 文本，保留 LM 原名。
- 资源取节内 `a[href*="/mod/"]`；用 `a.closest('[id^="course-index-section-"]') === section` 排除嵌套子节的重复归属。
- 每种资源类型保留在清单；只解析主技能规定的文件类型，不点论坛、测验或完成状态。
- 使用完整 DOM 读取，不把被截断的 AX 输出当作全量目录。每批将课程 JSON 保存到临时目录，避免只存在 REPL 变量中。

解析 resource 时，`goto(viewHref + "&redirect=1")` 可能等待 PDF 导航超时。读 `tab.url()` 核对实际地址；若仍是旧 URL，读取页面状态后再检查，不以旧地址填充当前 item。内嵌文件从当前 DOM 的 pluginfile `href` / `src` / `data` 取得。解析阶段遇到直接下载，使用下述事件流程获取实际下载结果。

## 文件传输：先等待下载，再导航

使用 `plan` 返回的真实 `download_url`，不要用课程资源的 `view.php` 链接充当下载地址。先在一份文件上验证，然后串行处理同一标签页的其余文件。

```javascript
// tab 是自己的工作标签页；downloadUrl 来自本轮 plan。
// 立即接住拒绝，保证导航异常时也会结算下载等待。
const pending = tab.playwright
  .waitForEvent("download", { timeoutMs: 15000 })
  .then(async download => ({
    path: await download.path({ timeoutMs: 15000 })
  }))
  .catch(error => ({ error: String(error) }));

let navigationError;
try {
  await tab.goto(downloadUrl);
} catch (error) {
  navigationError = String(error);
}
const result = await pending;
nodeRepl.write({ navigationError, ...result });
```

`net::ERR_ABORTED` 加上下载事件返回的有效路径是正常的下载转交；事件超时、路径为空或文件不存在都不算成功。`ERR_BLOCKED_BY_CLIENT` 不能一律当作成功，也不能直接归因为学校封锁。确认浏览与下载权限后，仍失败就保留实际错误，不盲试、不修改访问控制。

同一标签页不要并发登记多个 download 等待；它们可能竞争同一个事件。少量串行分批即可：例如每批 1–3 个，每个 15 秒时，整次工具调用应给足等待时间；若预算不足则缩小批次。每批保存文件名、返回路径与错误到临时 JSON，之后用脚本 ingest 验格式、比字节和归档，不手动移动 materials。

## 权限与收尾

- 浏览允许不等于下载允许。需要授权时，使用应用支持的权限提示或设置，让用户只允许 `https://core.xjtlu.edu.cn` 下载，无需上传权限。
- 浏览器扩展可用时，不转到原生 `getApp("Google Chrome")`。2026-10-18 原生层返回过“当前网址不允许”，没有暴露被拒绝的网址或具体规则；同场扩展仍能合法下载，不能把两个通道的错误合成同一个原因。
- 工具明确拒绝或要求停止时遵守它的边界，不通过重置、改配置、Cookie 下载或其他通道绕过。脚本日志与 finish 仍须收尾。
- 下载结果以落盘和 ingest 为准。仅重跑部分课程时，脚本对 config 里全部课程的 run 可能标 partial；报告当前课程是否 pending=0，不冒充整轮完整成功。清单仅可复用本会话刚核对过的版本，历史缓存不代替新一轮页面检查。
- 关掉本轮自己创建的工作标签页。
