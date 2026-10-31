FROM node:24-bookworm-slim AS frontend
WORKDIR /source/client
COPY client/package.json client/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY client/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=ccse_platform.production_settings
WORKDIR /app
COPY requirements-ai.lock.txt requirements-production.lock.txt ./
RUN pip install --no-cache-dir -r requirements-production.lock.txt
COPY ccse-conference-platform/ ./ccse-conference-platform/
COPY data/ ./data/
COPY deploy/entrypoint.sh ./entrypoint.sh
COPY --from=frontend /source/ccse-conference-platform/conferences/static/workspace/ ./ccse-conference-platform/conferences/static/workspace/
RUN useradd --create-home workspace && chown -R workspace:workspace /app
USER workspace
WORKDIR /app/ccse-conference-platform
EXPOSE 8000
CMD ["sh","/app/entrypoint.sh"]
