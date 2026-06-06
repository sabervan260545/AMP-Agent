FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Configure pip to use Alibaba mirror ONLY (Tsinghua has hash mismatch issues)
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
RUN pip config set global.trusted-host mirrors.aliyun.com

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --timeout 600
# Force downgrade httpx to fix openai compatibility
RUN pip install --no-cache-dir httpx==0.24.1 --force-reinstall
# Force downgrade numpy to fix chromadb compatibility
RUN pip install --no-cache-dir 'numpy<2.0' pandas --force-reinstall

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]
