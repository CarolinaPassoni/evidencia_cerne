FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000 EVIDENCIA_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY iniciar.py ./iniciar.py
RUN mkdir -p /app/data/uploads /app/data/documents
EXPOSE 8000
CMD ["python","iniciar.py"]
