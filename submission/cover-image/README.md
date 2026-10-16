# CareSteps Cover Image

已完成：英文项目封面，采用既有 CareSteps 心电标志、品牌文字和真实应用界面。

## 提交文件

| 文件 | 尺寸 | 用途 |
|---|---|---|
| [CareSteps_Cover.png](CareSteps_Cover.png) | **1920 x 1080，16:9** | **主提交文件**，用于展示页和演示 |
| [CareSteps_Cover_380x216.png](CareSteps_Cover_380x216.png) | **380 x 216** | 手册推荐像素尺寸，采用独立排版，保留醒目标题 |
| [CareSteps_Cover_1280x720.png](CareSteps_Cover_1280x720.png) | 1280 x 720，16:9 | 较小的标准比例版本 |
| [CareSteps_Cover_1200x630.png](CareSteps_Cover_1200x630.png) | 1200 x 630 | 原规划中的分享图尺寸，**不是手册要求的 16:9** |
| [CareSteps_Cover_Preview.png](CareSteps_Cover_Preview.png) | 1280 x 1055 | 大图与实际尺寸缩略图的对照预览，不作为提交封面 |

四张封面均为 RGB PNG，单张小于 300 KiB，低于实际表单的 1 MB 限制。主提交文件完整保留 16:9；如果表单要求精确 380 x 216，请改用相应缩略图。

## 手册与规划依据

本地手册 `Copy of AI CAN DO IT Tencent Cloud AI Singapore Hackathon 2026 Handbook.pdf` 第 **37 页**将 Cover Image 列为 Required，要求 **16:9**，推荐 **380 x 216 px**。

380/216 约为 1.759，而 16/9 约为 1.778，因此分别制作标准比例与精确推荐像素版本。没有将同一张图拉伸成不同宽高比。1200 x 630 是额外分享图规格，不视为赛事规定。

采用原规划的方案 A：**应用截图 + 既有品牌**。没有使用外部图库、生成式假界面、厂商标志或未确认的团队署名。

## 设计内容

- **名称**：CareSteps。
- **主题**：Blood pressure support for older adults.
- **核心流程**：Record. Understand. Prepare.
- **设计特性**：Safety gates before AI；Confirm before saving，后者对应封面展示的血压录入流程。
- **标识**：Healthcare / Challenge 2；Tencent Cloud AI Singapore Hackathon 2026。
- **数据说明**：Prototype / Simulated data。
- **配色**：医疗蓝 `#0052CC`、科技青 `#00B4A6`、深青 `#008678` 和白色；保留应用现有 favicon 的绿色心电标志。
- **字体**：Arimo Bold / Regular，与架构材料一致。

主封面突出名称和使用场景，右侧展示首页的三项真实操作，以及血压录入页的真实输入框。没有将架构信息、测试数量或技术栈塞入封面。

## 截图来源

原始素材位于 [assets/](assets/)，取自当前 FastAPI 应用：

| 素材 | 来源 |
|---|---|
| `caresteps-mark.png` | `app/templates/base.html` 的现有 SVG favicon，由浏览器渲染成 PNG |
| `home-actions.png` | `/app`，包含问候语与三项首页操作 |
| `reading-values.png` | `/readings/new` 的 `.bp-inputs` 区域 |
| `reading-entry.png` | 录入页的较大上下文截图，包含尚未保存的提示 |
| `home-full.png` | 首页整页截图，保留原型及 Limited mode 说明供核对 |
| `trends-full.png` / `trends-chart.png` | 取图时保存的趋势页参考，未用于最终封面 |
| `capture-info.json` | 路径、裁剪坐标、浏览器尺寸和运行模式记录 |

截图使用单独的临时演示数据库及 `LLM_FORCE_DEGRADED=1`。Mdm Tan 是项目自带的虚构角色；138 / 82 是在表单中临时填写、**没有提交保存**的演示数值，不是患者信息或医疗结论。

未修改页面 HTML、CSS、提示文字、图表数据或模式状态以制造截图。封面使用局部裁剪，完整页中的原型和 Limited mode 提示保存在原始素材中。封面另有自己的原型与虚构数据标记；它不宣称 live 模型已经验证。

## 制作与再生成

所有最终图像都由 Pillow 排版，源文件和截图一同保存。生成封面不需要联网或运行应用：

```bash
python3 submission/cover-image/build_cover.py
```

需要 Python 3、Pillow，以及 Arimo 字体。若没有 Arimo，脚本回退至 DejaVu Sans；字体变化可能需要重新检查排版。导出的 PNG 带有标题、原型说明和制作软件 metadata，不含会话 cookie 或凭据。

重新截图需要本地 Playwright 及 Chromium。先以独立临时数据库启动演示实例：

```bash
CARESTEPS_DB=/tmp/caresteps-cover-fresh.db LLM_FORCE_DEGRADED=1 \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

在另一个终端执行：

```bash
node submission/cover-image/capture_assets.cjs
```

如果应用运行在其他地址，可设置 `CARESTEPS_COVER_ORIGIN`。如果当前 Playwright 未配套安装浏览器，可用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指定已有 Chromium。脚本使用独立的非持久化浏览器 context，不复用个人浏览器登录态。

[cover-manifest.json](cover-manifest.json) 保存导出尺寸、文件大小、文件指纹、排版文字边界和使用素材的指纹。上一版封面已移入本地归档，最终选择以本目录文件为准。

## 检查结果

- [x] 主封面与中尺寸封面为准确 16:9。
- [x] 推荐尺寸为准确 380 x 216，单独排版后按实际像素查看。
- [x] 所有封面小于实际表单的 1 MB 限制。
- [x] 名称、主题、比赛标识、原型说明均在画布内，无文字重叠。
- [x] 已核对4种尺寸、PNG完整性、RGB模式、文件指纹及48个排版文字区域的边界与相互间距。
- [x] UI 素材等比例放置，不拉伸，不伪造界面。
- [x] 所用图片为应用截图和已有品牌，不含外部图片版权依赖。
- [x] 无真实患者信息、API key 或浏览器凭据；取图浏览器无脚本错误。
- [x] 未使用 WCAG AA+ 认证、临床验证或特定 live 模型接入等未经验证的宣称。
- [x] 应用代码未修改；取图临时服务已停止。

制作完成：2026-10-16。
