FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY endpoint_manifest.json .
COPY madeuptasks_mcp_meta/ madeuptasks_mcp_meta/

ENV MADEUPTASKS_API_URL=http://madeuptasks-api:8090/api/v1
ENV MADEUPTASKS_API_TOKEN=""

ENTRYPOINT ["python", "-m", "madeuptasks_mcp_meta"]
