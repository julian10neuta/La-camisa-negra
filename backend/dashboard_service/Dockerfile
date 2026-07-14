FROM python:3.13-slim
WORKDIR /app

COPY shared/ ./shared/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard_service/ ./dashboard_service/

ENV PYTHONPATH=/app

CMD ["uvicorn", "dashboard_service.main:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]
