# PodBay Docker Setup

This document explains how to run PodBay using Docker and Docker Compose.

## 🐳 Quick Start

### Development Mode
```bash
# Build and run both frontend and backend
docker-compose up --build

# Run in background
docker-compose up -d --build
```

### Production Mode
```bash
# Build and run with production settings
docker-compose -f docker-compose.prod.yml up --build

# Run in background
docker-compose -f docker-compose.prod.yml up -d --build
```

## 📋 Services

### Backend Service (`podbay-backend`)
- **Port**: 8000
- **Technology**: FastAPI + Python 3.12
- **Features**: 
  - Kubernetes API integration
  - Real-time monitoring
  - CORS enabled for frontend
  - Health checks

### Frontend Service (`podbay-frontend`)
- **Port**: 3000
- **Technology**: HTML/CSS/JavaScript + Python HTTP Server (dev) or Nginx (prod)
- **Features**:
  - Modern responsive UI
  - Real-time data updates
  - Multiple monitoring panels

## 🔧 Configuration

### Environment Variables

#### Backend
- `PYTHONPATH=/app` - Python path configuration
- `DEBUG=false` - Debug mode (production)
- `DEBUG=true` - Debug mode (development)

#### Frontend
- `PORT=3000` - Frontend port

### Volume Mounts

#### Required
- `~/.kube:/home/appuser/.kube:ro` - Kubernetes configuration (read-only)

#### Development (Optional)
- `./backend:/app` - Backend source code for hot reload
- `./frontend:/app` - Frontend source code for hot reload

## 🚀 Usage

### Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### Health Checks
- **Backend**: http://localhost:8000/health
- **Frontend**: http://localhost:3000/health

## 🛠️ Development

### Hot Reload Development
```bash
# Start with source code mounted for hot reload
docker-compose up --build

# Backend will auto-reload on code changes
# Frontend will serve static files with live updates
```

### Individual Services
```bash
# Run only backend
docker-compose up podbay-backend

# Run only frontend
docker-compose up podbay-frontend
```

### Logs
```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs podbay-backend
docker-compose logs podbay-frontend

# Follow logs in real-time
docker-compose logs -f
```

## 🏗️ Building

### Build Individual Services
```bash
# Build backend
docker build -f backend/Dockerfile -t podbay-backend .

# Build frontend (simple)
docker build -f frontend/Dockerfile -t podbay-frontend .

# Build frontend (production with Nginx)
docker build -f frontend/Dockerfile.nginx -t podbay-frontend-nginx .
```

### Build All Services
```bash
# Development build
docker-compose build

# Production build
docker-compose -f docker-compose.prod.yml build
```

## 🔍 Troubleshooting

### Common Issues

1. **Kubernetes Connection Issues**
   ```bash
   # Ensure kubeconfig is accessible
   ls -la ~/.kube/config
   
   # Check if kubectl works
   kubectl get nodes
   ```

2. **Port Conflicts**
   ```bash
   # Check if ports are in use
   netstat -tulpn | grep :8000
   netstat -tulpn | grep :3000
   
   # Stop conflicting services or change ports in docker-compose.yml
   ```

3. **Permission Issues**
   ```bash
   # Fix kubeconfig permissions
   chmod 600 ~/.kube/config
   ```

### Debugging

1. **Check Container Status**
   ```bash
   docker-compose ps
   ```

2. **Inspect Container Logs**
   ```bash
   docker-compose logs podbay-backend
   docker-compose logs podbay-frontend
   ```

3. **Access Container Shell**
   ```bash
   # Backend container
   docker-compose exec podbay-backend /bin/bash
   
   # Frontend container
   docker-compose exec podbay-frontend /bin/sh
   ```

## 📦 Production Deployment

### Using Production Compose
```bash
# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Scale services (if needed)
docker-compose -f docker-compose.prod.yml up -d --scale podbay-backend=2
```

### Environment-Specific Configuration
Create `.env` files for different environments:

```bash
# .env.production
DEBUG=false
LOG_LEVEL=INFO

# .env.development
DEBUG=true
LOG_LEVEL=DEBUG
```

## 🔒 Security Considerations

1. **Non-root Users**: Both containers run as non-root users
2. **Read-only Volumes**: Kubernetes config is mounted read-only
3. **Security Headers**: Production frontend includes security headers
4. **Health Checks**: Both services have health check endpoints

## 📊 Monitoring

### Health Check Endpoints
- Backend: `GET /health`
- Frontend: `GET /health` (production) or `GET /` (development)

### Metrics
- Backend provides detailed Kubernetes metrics
- Frontend displays real-time monitoring data
- Both services support Docker health checks

## 🧹 Cleanup

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop production services
docker-compose -f docker-compose.prod.yml down
```

### Remove Images
```bash
# Remove all PodBay images
docker rmi podbay-backend podbay-frontend

# Remove all unused images
docker image prune -a
```
