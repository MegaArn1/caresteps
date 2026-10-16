# CareSteps 提交核查清单

核查日期：**2026-10-16**。依据本地手册 PDF 第 35、37 页及实际提交表单 PDF 第 1–3 页。
实际表单的必填星号优先于手册中的 Optional 描述。

## 实际表单逐项核对

| 项目 | 真实要求 | 最终材料 / 状态 |
|---|---|---|
| Project Title | 必填 | `CareSteps 乐护同行` |
| Short Blurb | 必填，严格少于 10 个英文词 | `Everyday support for seniors managing blood pressure`，8 词 |
| Project Description | 必填，含场景、痛点来源、业务/技术设计、提示词和价值 | [description.md](description.md) |
| Cover Image | 必填，1 个文件，≤1 MB，16:9，推荐 380×216 | [CareSteps_Cover.png](cover-image/CareSteps_Cover.png)，1920×1080，295,723 bytes；另有推荐像素版 |
| Project Web Link | **必填**，可在浏览器在线体验 | **待部署并验证公共 URL**；不能用 GitHub 地址或 Local Only 替代 |
| Demo Video Link | **必填**，5–8 分钟，概览/核心 Agent 用法/构建反思 | [caresteps-demo-gemini.mp4](demo-video/caresteps-demo-gemini.mp4)，441.934 秒；**待托管并验证可播放 URL** |
| WorkBuddy/CodeBuddy Conversation History | **必填**，聊天记录及至少 3 张截图；1 个文件，≤10 MB | [CareSteps_WorkBuddy_Evidence.pdf](tool-evidence/CareSteps_WorkBuddy_Evidence.pdf)，三张现有截图；见[贡献范围](../docs/development.md) |
| Architecture Diagram PPT | **必填**，1 个文件，≤10 MB | [CareSteps_Architecture_Diagram.pptx](architecture-diagram/CareSteps_Architecture_Diagram.pptx)，9 页；PDF 为附加阅读版 |
| Source Code | **必填**，GitHub 仓库 URL | [MegaArn1/caresteps](https://github.com/MegaArn1/caresteps) |
| Social Media Post Link | Bonus，可选；指定四个 hashtags | 未发布，不影响必填项 |

## 工具证据

手册要求项目原创、基于 CodeBuddy 或 WorkBuddy 产品，并提供使用证据。
现有三张截图记录 WorkBuddy 的统计 API、测试与部署指南任务，已封装为一个 PDF。
任务过程和可验证成果见[开发流程](../docs/development.md)与证据目录。

## 本地验证

- [x] 现有自动化套件 170 项通过。
- [x] 27/27 路由演示场景通过。
- [x] 密钥从待发布正文清除；发布历史副本单独脱敏，原始历史保留本地。
- [x] 旧计划、agent memory、未引用 CSS、重复成品和原始音视频移入本地归档。
- [x] 短简介、文档路径、启动命令、真实工具数量和原型边界统一。
- [ ] 公共 Web URL 从未登录浏览器打开，验证表单、样式、Limited mode 和已配置的 live 路径。
- [ ] 视频托管链接从未登录浏览器打开，确认无需申请权限且可播放。
- [ ] GitHub 仓库公开可访问或已给评审访问权限；从 fresh clone 运行成功。
- [ ] 确认材料中的第三方素材使用权；源内容引用与原型声明保留。
- [ ] 按表单上传正确的三个文件，并填写三个必填链接。
- [ ] 提交表单后保存回执。

## 截止时间

手册只给 **2026-10-16**，两份 PDF 均未注明具体时刻和时区。旧文件中的
`2026-10-16 23:59 SGT` 缺少来源，已撤下。不要将它当成已确认截止时间。

[表单文案](project-info/SUBMISSION_CONTENT.md) · [部署](web-deployment/DEPLOYMENT_STRATEGY.md) ·
[验证记录](../docs/evaluation.md)
