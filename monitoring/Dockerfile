FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the monitoring script
COPY apm-error-monitor.py .

# Make script executable
RUN chmod +x apm-error-monitor.py

# Run the script
CMD ["python", "apm-error-monitor.py"]

