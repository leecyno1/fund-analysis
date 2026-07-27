# 向量数据库设置指南

## 概述

本系统使用 Qdrant 作为向量数据库，用于研报的语义检索功能。

## 安装依赖

```bash
pip install qdrant-client sentence-transformers
```

## 启动 Qdrant 服务器

### 方式 1: Docker (推荐)

```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```

### 方式 2: Docker Compose

创建 `docker-compose.yml`:

```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
```

启动:
```bash
docker-compose up -d
```

### 方式 3: 本地安装

参考官方文档: https://qdrant.tech/documentation/quick-start/

## 配置

在 `.env` 文件中配置:

```bash
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

## 验证安装

运行测试脚本:

```bash
python test_vector_db.py
```

成功输出示例:
```
============================================================
测试向量数据库集成
============================================================

1. 连接向量数据库...
✓ 连接成功

2. 获取集合信息...
✓ 集合名称: research_reports
✓ 向量数量: 0
✓ 点数量: 0
✓ 状态: green

3. 添加测试研报...
✓ 添加成功，ID: xxx-xxx-xxx

4. 测试语义搜索...
✓ 查询: 价值投资风格的基金经理
✓ 找到 1 条相似结果:
  1. 测试研报 - 某某基金经理调研 (相似度: 0.856)
     经理: 张三

5. 清理测试数据...
✓ 清理完成

============================================================
✓ 所有测试通过！向量数据库集成正常工作
============================================================
```

## API 使用

### 添加研报

```python
from services.vector_db_service import get_vector_db

vector_db = get_vector_db()
vector_db.add_report(
    report_id="report_001",
    title="某某基金经理调研",
    content="该基金经理专注于价值投资...",
    metadata={
        "manager_name": "张三",
        "company": "华夏基金",
        "date": "2026-04-25"
    }
)
```

### 语义搜索

```python
results = vector_db.search_similar(
    query="价值投资风格的基金经理",
    top_k=5,
    filter_dict={"manager_name": "张三"}
)

for result in results:
    print(f"{result['title']} - 相似度: {result['similarity']}")
```

### 批量添加

```python
reports = [
    {
        "id": "report_001",
        "title": "研报1",
        "content": "内容1",
        "metadata": {"manager_name": "张三"}
    },
    {
        "id": "report_002",
        "title": "研报2",
        "content": "内容2",
        "metadata": {"manager_name": "李四"}
    }
]

vector_db.batch_add_reports(reports)
```

## HTTP API 端点

### 搜索相似研报

```bash
POST /api/research-reports/search/similar
Content-Type: application/json

{
  "content": "价值投资风格的基金经理",
  "top_k": 5,
  "manager_name": "张三"
}
```

### 批量导入研报

```bash
POST /api/research-reports/batch-import
Content-Type: multipart/form-data

files: [file1.pdf, file2.docx, file3.txt]
```

## 故障排查

### 1. 连接失败 (502 Bad Gateway)

**原因**: Qdrant 服务器未启动

**解决**: 
```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 2. 模型下载慢

**原因**: HuggingFace 下载速度慢

**解决**: 设置镜像或使用本地模型
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 3. 内存不足

**原因**: 向量模型占用内存较大

**解决**: 使用更小的模型
```python
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## 性能优化

### 1. 批量操作

使用 `batch_add_reports()` 而不是循环调用 `add_report()`

### 2. 索引优化

Qdrant 会自动创建 HNSW 索引，无需手动配置

### 3. 缓存

系统已实现查询结果缓存，重复查询会直接返回缓存结果

## 数据备份

Qdrant 数据存储在 `./qdrant_storage` 目录，定期备份该目录即可。

```bash
tar -czf qdrant_backup_$(date +%Y%m%d).tar.gz qdrant_storage/
```

## 更多信息

- Qdrant 官方文档: https://qdrant.tech/documentation/
- Sentence Transformers: https://www.sbert.net/
