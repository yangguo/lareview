# LA Review 权限核对智能体

基于 LangChain Agent 的自动化权限审计工具，通过对话式交互完成系统账号清单与HR人员名单的智能核对。

## 功能

- 上传系统账号清单、HR在职清单、HR离职清单（CSV/Excel）
- 智能识别表结构和字段映射（零Token启发式分类）
- 自动核对分析：
  - 有系统权限但不在HR在职清单中的用户
  - 离职人员仍保有系统权限
  - 重复账号检测
- 结果以Markdown报告呈现，支持XLSX下载

## 架构

```
前端 (Next.js)  →  后端 (FastAPI + LangChain Agent)
  frontend/           src/
                        main.py          # FastAPI 服务
                        agents/agent.py  # Agent 构建
                        tools/
                          ingest_files.py    # 文件解析
                          classify_tables.py # 表结构分类
                          analyze_access.py  # 权限核对
                          frame_store.py     # 内存缓存
                      backend/
                        ingestion.py     # 文件加载
                        classifier.py    # 启发式分类器
                        matching.py      # 匹配分析
```

## 快速开始

### Docker 部署（推荐）

```bash
docker build -t lareview-agent .
docker run -p 8000:8000 --env-file .env lareview-agent
```

### 本地开发

```bash
cp .env.example .env    # 填入 OPENAI_API_KEY
pip install -r requirements.txt
cd frontend && npm install
```

### 2. 启动服务

```bash
# 后端 (端口 8000)
python -m src.main -m http -p 8000

# 前端 (端口 3000)
cd frontend && npm run dev
```

如果后端不在 `http://localhost:8000`，设置环境变量 `NEXT_PUBLIC_API_URL`。

### 3. 使用

1. 打开 `http://localhost:3000`
2. 上传系统账号清单和HR人员名单文件
3. 输入分析需求，智能体自动完成核对

## 测试

```bash
python -m pytest -q
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API密钥 | 必填 |
| `OPENAI_BASE_URL` | LLM API地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-4o` |
| `FRONTEND_ORIGINS` | CORS允许的前端地址 | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | 前端连接的后端地址 | `http://localhost:8000` |
