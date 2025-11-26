FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the apm_monitor package
COPY apm_monitor/ ./apm_monitor/

# Copy the entry point scripts
COPY apm-error-monitor.py .

# Make scripts executable
RUN chmod +x apm-error-monitor.py

# Run the monitoring script
CMD ["python", "apm-error-monitor.py"]

