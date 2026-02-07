FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY server/requirements.txt ./server/
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy server code only
COPY server/ ./server/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
