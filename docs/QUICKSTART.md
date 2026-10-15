# CareSteps 快速体验指南

## 5分钟快速启动

### 1. 环境准备

确保已安装Python 3.11+，然后设置环境：

```bash
# 进入项目目录
cd /path/to/caresteps

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 设置实时模型配置（可选，不设置则使用降级模式）
export LLM_BASE_URL="https://api.tiantoken.com/v1"
export LLM_API_KEY="REDACTED_API_KEY"
export LLM_MODEL="claude-sonnet-5-5"
```

### 2. 启动应用

```bash
# 启动开发服务器
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 或使用 make 命令
make serve
```

应用将在 **http://127.0.0.1:8000** 启动。

### 3. 验证启动状态

浏览器访问：
- **主页**: http://127.0.0.1:8000/app
- **健康检查**: http://127.0.0.1:8000/healthz
- **透明度页面**: http://127.0.0.1:8000/trace

---

## 核心功能快速体验

### 🩺 功能1：记录血压读数

**路径**: 首页 → "Record blood pressure"

1. 点击首页的第一个绿色卡片
2. 输入两个数字：
   - 收缩压（上压）：140
   - 舒张压（下压）：85
3. 选择测量时间（默认当前时间）
4. 点击 "Preview" 查看确认页
5. 点击 "Save this reading" 保存

**预期结果**：
- ✅ 返回首页看到刚记录的读数
- ✅ "Most recent reading" 卡片显示 140/85 mmHg

**测试边界情况**：
- 尝试输入过高值（如 200/120）- 应正常保存但不做判断
- 尝试输入过低值（如 80/50）- 应正常保存

### 📊 功能2：查看趋势和统计

**路径**: 首页 → "My numbers" 导航栏 或 点击 "See my numbers over time"

**查看内容**：
1. **平均值卡片** - 显示收缩压和舒张压的平均值、范围
2. **趋势图表** - SVG图表显示每日血压变化
3. **数据完整性** - 显示记录覆盖率
4. **周期对比** - 当前周期 vs 上一周期
5. **用药记录** - 同期服药依从性统计

**预期结果**：
- ✅ 图表可交互，显示数据点
- ✅ "Show these numbers as a list" 展开后显示表格
- ✅ 所有数字都带有分母（如"基于14天中的12次记录"）

**测试点**：
- 记录不足3天时，应显示"Not enough recorded to describe an average"
- 图表中断点（missing days）应显示为虚线

### 💊 功能3：用药管理

**路径**: 首页 → "Confirm my medicine"

**操作流程**：
1. 查看当前用药列表（demo数据包含：Amlodipine、Losartan、Hydrochlorothiazide）
2. 每种药物显示：
   - 用途说明（"What this is for"）
   - 来源（care plan / prescription）
   - 确认状态（confirmed / not confirmed）

**预期结果**：
- ✅ 药物信息清晰易读
- ✅ 无临床建议，只有描述性信息
- ✅ 明确标注"This app cannot change your prescription"

### 🤚 功能4：报告困难（Barriers）

**路径**: 首页 → "Something is difficult"

**测试场景**：
1. 输入自由文本，例如：
   - "I keep forgetting to take my medicine in the morning"
   - "The blood pressure cuff is hard to use with one hand"
2. 系统分析并提供：
   - 困难分类建议（categorical classification）
   - 可选的应对策略（actions）
3. 选择或跳过分类
4. 选择一个行动计划（或不选）

**预期结果**：
- ✅ 用户原文被完整保留（"in your own words"）
- ✅ 分类和行动都是可选的，可以"I would rather not say"
- ✅ 在首页"Still open"部分可以看到未解决的困难

**测试对话模式**：
- 如果配置了live model，应走真实AI对话
- 如果降级模式，应走规则引擎并显示"Limited mode"横幅

### 📋 功能5：就诊总结

**路径**: 首页底部 → "Prepare for my appointment" 或 顶部导航 → "Appointment"

**生成内容**：
1. **个人信息** - 姓名、年龄段、目标血压
2. **血压统计** - 平均值、范围、记录天数
3. **用药依从性** - 服药记录统计
4. **困难清单** - 已报告的barriers
5. **问题列表** - 想问医生的问题

**操作**：
- 点击 "Print or save as PDF" 测试打印样式
- 检查是否有"This document is fictional"的原型声明

**预期结果**：
- ✅ 所有数据都标注了来源和时间窗口
- ✅ 打印样式友好（去掉导航栏、按钮、背景色）
- ✅ 无临床判断，只有数据描述

---

## 🤖 AI 对话功能测试

### 实时模型对话

**前提**: 必须设置环境变量（见上方启动步骤）

**路径**: `/support/ask` 或首页 "Something is difficult"

**测试对话**：

1. **普通医疗咨询**：
   ```
   "Can you explain what amlodipine is for?"
   ```
   **预期**: AI使用知识库工具查询药物信息并回答

2. **数据查询**：
   ```
   "What was my blood pressure reading yesterday?"
   ```
   **预期**: AI调用 `reading_search` 工具查询数据

3. **紧急关键词触发**（Red Flag）：
   ```
   "I have chest pain"
   ```
   **预期**:
   - ✅ 立即显示红色紧急面板
   - ✅ 显示995急救电话（新加坡）
   - ✅ 对话被安全守卫拦截
   - ✅ 不继续普通对话流程

4. **其他紧急触发词**：
   - "severe headache and vision problems"
   - "difficulty breathing"
   - "sudden weakness on one side"
   
   **预期**: 均应触发紧急响应

### 降级模式（Degraded Mode）

**测试方法**: 不设置 LLM 环境变量，或设置错误的 API key

```bash
# 启动时故意不设置环境变量
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**预期行为**：
- ✅ 首页顶部显示黄色 "Limited mode" 横幅
- ✅ 说明"answered by a simpler set of rules"
- ✅ 血压记录、趋势、用药等功能完全正常
- ✅ 对话降级到规则引擎（keywords matching）

---

## 🔍 透明度和审计功能

### 透明度页面

**路径**: http://127.0.0.1:8000/trace

**显示内容**：
1. **模型状态**:
   - Connected / Not connected
   - 模型名称（如 claude-sonnet-5-5）
   - API endpoint（隐藏key，只显示host）
   
2. **规则引擎**:
   - 规则版本号
   - Safety patterns（红旗关键词列表）
   - 工具清单（tool inventory）
   
3. **审计日志**:
   - 最近的对话记录
   - 工具调用历史（tool_call events）
   - 时间戳和会话ID

**验证点**：
- ✅ `/healthz` 返回健康状态JSON
- ✅ `/trace` 中 `live: true` 表示真实模型已连接
- ✅ 审计日志包含 `tool_name`、`arguments`、`result` 字段

### 健康检查端点

```bash
# 在终端测试
curl http://127.0.0.1:8000/healthz | jq
```

**预期输出**：
```json
{
  "status": "ok",
  "llm": {
    "configured": true,
    "live": true,
    "model": "claude-sonnet-5-5"
  },
  "rules": {
    "version": "2025-W01",
    "loaded": true
  }
}
```

---

## 🔄 Demo 重置功能

### Reset Demo Data

**路径**: 首页最底部 → "Demo Controls" 卡片

**操作流程**：
1. 点击 "Reset demo data" 按钮
2. 确认对话框："Reset all data back to the demo state? This cannot be undone."
3. 点击 "OK"
4. 状态显示："Resetting..."
5. 成功后自动刷新页面

**预期结果**：
- ✅ 所有用户输入的血压记录被清除
- ✅ 恢复到初始demo患者（Chen Wei, 70-75岁）
- ✅ 知识库重置到初始状态
- ✅ 页面自动重载，显示demo数据

**验证**：
重置后检查：
- 最近血压读数应该是demo数据
- 用药列表恢复到3种药物
- 无自定义barriers

---

## 🎨 UI 新设计验证

### 视觉检查清单

**配色方案**：
- ✅ 品牌色：医疗蓝 `#0052CC` + 科技青 `#00B4A6`
- ✅ 渐变效果：按钮和卡片有渐变背景
- ✅ 阴影层次：卡片有细腻的阴影

**交互效果**：
- ✅ 卡片悬停上浮（hover: translateY(-2px)）
- ✅ 按钮悬停加深颜色
- ✅ 导航栏当前页面有下划线
- ✅ 平滑过渡动画（250ms）

**可访问性保持**：
- ✅ 48px 最小触控目标
- ✅ 19px 基础字号
- ✅ WCAG AA+ 对比度
- ✅ Focus 状态清晰可见

### 响应式测试

**桌面端** (> 720px):
- 卡片最大宽度720px居中
- 双列表单布局

**平板** (640px - 720px):
- 单列布局
- 保持所有功能

**移动端** (< 640px):
- 字号略微缩小到18px
- 导航栏堆叠
- 触控目标保持48px

---

## 🧪 完整测试流程（5分钟演示脚本）

### 分钟1：启动和状态验证
```bash
export LLM_BASE_URL="https://api.tiantoken.com/v1"
export LLM_API_KEY="REDACTED_API_KEY"
export LLM_MODEL="claude-sonnet-5-5"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- 打开 http://127.0.0.1:8000/app
- 检查无 "Limited mode" 横幅
- 打开 /trace 确认 `live: true`

### 分钟2：记录和查看
- 记录一次血压：145/88
- 查看 My numbers 页面
- 展开 "Show these numbers as a list"

### 分钟3：AI对话测试
- 询问："What is my average blood pressure this week?"
- 观察工具调用
- 触发红旗："I have severe chest pain"
- 确认紧急面板出现

### 分钟4：用药和困难
- 查看 Medicines 页面
- 报告困难："Hard to remember the evening dose"
- 选择分类和行动

### 分钟5：总结和重置
- 生成就诊总结
- 测试打印预览
- Reset demo data
- 确认恢复到初始状态

---

## 📊 测试套件验证

### 运行自动化测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块
pytest tests/test_agent.py -v
pytest tests/test_safety.py -v
pytest tests/test_readings.py -v

# 查看覆盖率
pytest tests/ --cov=app --cov-report=html
```

**预期结果**: 170 passed

### 关键测试覆盖

- ✅ Safety guard 红旗检测
- ✅ 工具调用链路
- ✅ 降级模式fallback
- ✅ 血压CRUD操作
- ✅ 知识库查询
- ✅ Demo重置功能
- ✅ API端点响应

---

## 🔧 常见问题排查

### 问题1: "Limited mode" 横幅一直显示

**原因**: LLM 配置未生效

**解决**:
```bash
# 确认环境变量已设置
echo $LLM_BASE_URL
echo $LLM_MODEL
echo $LLM_API_KEY  # 不应该为空

# 重启服务器使环境变量生效
```

### 问题2: 对话无工具调用

**原因**: 模型未正确配置或API key无效

**解决**:
1. 访问 /trace 查看 `llm.live` 状态
2. 检查 API key 是否正确
3. 测试 endpoint:
```bash
curl -X POST https://api.tiantoken.com/v1/chat/completions \
  -H "Authorization: Bearer REDACTED_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-5-5","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
```

### 问题3: 图表不显示

**原因**: SVG渲染问题或数据不足

**解决**:
- 确保至少记录了3天的数据
- 检查浏览器控制台是否有JS错误
- 尝试不同浏览器（Chrome/Firefox/Edge）

### 问题4: Reset 按钮无响应

**原因**: JavaScript未加载或API返回错误

**解决**:
1. 打开浏览器开发者工具 (F12)
2. 查看 Console 和 Network 标签
3. 确认 `/api/demo/reset` 返回 `{"ok": true}`
4. 检查是否有CORS错误

### 问题5: 端口8000已被占用

**解决**:
```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# 或使用其他端口
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

---

## 📖 扩展阅读

- **架构文档**: `docs/ARCHITECTURE.md` - 系统设计和组件说明
- **部署指南**: `docs/DEPLOYMENT.md` - Render/Railway 部署步骤
- **API文档**: `docs/API.md` - 所有端点的详细说明
- **安全设计**: `docs/SAFETY.md` - 安全守卫和红旗机制
- **提交材料**: `docs/SUBMISSION.md` - Hackathon 提交清单

---

## 🎯 评委快速演示建议

**3分钟核心演示路径**：

1. **打开首页** (30秒)
   - 展示现代化UI设计
   - 指出透明声明："This is a prototype"

2. **记录血压** (45秒)
   - 快速输入 → 预览 → 保存
   - 展示大字号、清晰布局

3. **AI对话** (60秒)
   - 咨询药物信息（展示工具调用）
   - 触发红旗（展示安全机制）

4. **透明度页面** (30秒)
   - 显示实时模型连接状态
   - 展示审计日志

5. **总结报告** (15秒)
   - 生成就诊总结
   - 强调"所有数字都有分母"的设计原则

**核心价值传达**：
- ✅ 真实可用（live model + 完整功能）
- ✅ 安全优先（red flags + degraded mode）
- ✅ 透明可审计（trace page + audit log）
- ✅ 适老设计（19px字号 + 48px触控）
- ✅ 临床严谨（never judge + always show denominators）

---

*最后更新: 2026-10-16*  
*CareSteps v1.0 - Tencent Hackathon 提交版本*
