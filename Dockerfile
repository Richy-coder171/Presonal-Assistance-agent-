FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -m compileall assistant_agent tests -q

EXPOSE 8765

CMD ["sh", "-c", "python -m assistant_agent.init_db && uvicorn assistant_agent.server:create_app_from_env --factory --host 0.0.0.0 --port ${APP_PORT:-8765}"]
