FROM python:3.11-slim

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY api/ api/
COPY pipelines/ pipelines/
COPY memory/ memory/
COPY cyber_planner.py health_coach.py persona.md yuanbao_cyber_minghan_kg.json ./

# 运行时数据目录（挂载卷）
RUN mkdir -p /app/decision_logs /app/memory/episodic

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
