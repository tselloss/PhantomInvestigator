# Build context is the repo root (see docker-compose.yml) so this stage can
# reach ../ui for the React operator console.
FROM node:20-slim AS ui-build
WORKDIR /ui
COPY ui/package*.json ./
RUN npm install
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ .
COPY --from=ui-build /ui/dist ./static/ui
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
