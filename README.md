# 建筑能耗分析平台

> 建筑能源消耗分析 · 碳排放计算 · 标准对标 · Word 报告生成

支持导入 Excel/CSV 能耗数据或粘贴表格，自动完成能耗折标煤、碳排放计算和多地区/多标准对标分析，一键下载 Word 报告。

## 快速开始

### 前提条件

- Python 3.9+
- Node.js 20+

### 安装 & 运行

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# 2. 前端（新终端）
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 即可使用。

### 生产部署

```bash
# 构建前端
cd frontend && npm run build

# 前端文件在 frontend/dist/，FastAPI 自动提供服务
cd ../backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Ant Design 5 + Recharts |
| 后端 | FastAPI + Uvicorn |
| 分析引擎 | Python (matplotlib, python-docx, openpyxl) |

## 功能特性

- 📥 **数据导入**：上传 Excel/CSV 或粘贴 Markdown 表格，自动识别能源列
- 📊 **能源分析**：折标煤比例、逐月趋势、季节性分析、异常检测
- 🌍 **碳排放**：中国六大区域电网排放因子，分省/分标准对标
- 🏛️ **标准库**：GB/T 51161-2016、DB31/T 783-2026（上海高校）、江苏旅馆限额等
- 📄 **报告下载**：一键生成 Word (.docx) 专业报告（含图表）

## 支持的标准

- GB/T 51161-2016《民用建筑能耗标准》（国家标准）
- DB31/T 783-2026《高等学校建筑合理用能指南》（上海高校）
- DB31/T 552-2017《大型商业建筑合理用能指南》（上海商业）
- DB31/T 1341-2021《商务办公建筑合理用能指南》（上海商务办公）
- 《江苏省公共建筑用能和碳排放限额指南》（江苏旅馆）
