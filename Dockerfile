FROM python:3.12-slim

LABEL authors="qwasd"

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 11111

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11111"]
