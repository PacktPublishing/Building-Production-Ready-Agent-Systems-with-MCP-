FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MADEUPTASKS_API_URL=http://host.docker.internal:8090/api/v1
ENV MADEUPTASKS_API_TOKEN=""

CMD ["python", "-m", "madeuptasks_mcp_logical"]
