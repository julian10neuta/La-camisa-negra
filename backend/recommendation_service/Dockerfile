FROM python:3.13-slim
WORKDIR /app

COPY shared/ ./shared/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY recommendation_service/ ./recommendation_service/

ENV PYTHONPATH=/app

CMD ["uvicorn", "recommendation_service.main:app", "--host", "0.0.0.0", "--port", "8004", "--reload"]
