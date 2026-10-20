# Contributing

欢迎西浦同学试用与反馈（English reports are welcome too）。

## 报告问题

请通过 GitHub Issue 描述：操作系统、Python 版本、Agent/Harness、浏览器工具、触发步骤、预期行为、实际行为和同步的最终状态（changed / unchanged / partial / blocked）。优先提供可复现的**合成数据**。

请勿提交密码、Cookie、Token、个人课件、课程私有附件、完整浏览器 Profile、包含会话信息的下载链接或未经脱敏的日志。

## 本地开发与验证

- Python 3.10+，脚本仅使用 Python 标准库。
- 不需要登录 Learning Mall 即可运行本地单测：

```bash
python -m unittest discover -s tests -v
```

- 涉及下载、归档、索引的修改请附对应的回归测试。
- 浏览器端到端测试需要自己有权限访问的 Learning Mall 账号，不应把私人数据保存进仓库。
- 代码与文档沿用 MIT License。课件本身不由本项目授权。

第一次试用如果完成了完整同步，非常欢迎分享使用的 Harness、浏览器工具，以及首次上手最困难的一步。
