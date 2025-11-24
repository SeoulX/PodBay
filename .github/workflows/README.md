# GitHub Actions Workflows

## Docker Build and Push

The `docker-build-push.yml` workflow automatically builds and pushes Docker images when you push a version tag.

### How to Use

1. **Create a version tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **The workflow will:**
   - Build the Docker image
   - Tag it with the version (e.g., `v1.0.0`, `1.0.0`, `1.0`, `1`, `latest`)
   - Push to GitHub Container Registry (ghcr.io)
   - Optionally push to Docker Hub if credentials are configured

### Image Locations

- **GitHub Container Registry:** `ghcr.io/<your-username>/<repo-name>:<tag>`
- **Docker Hub (optional):** `<dockerhub-username>/<image-name>:<tag>`

### Configuration

#### GitHub Container Registry
- Works automatically with `GITHUB_TOKEN`
- No additional setup needed

#### Docker Hub (Optional)
To also push to Docker Hub, add these secrets in your GitHub repository:
1. Go to Settings → Secrets and variables → Actions
2. Add:
   - `DOCKERHUB_USERNAME`: Your Docker Hub username
   - `DOCKERHUB_TOKEN`: Your Docker Hub access token

### Version Tagging

The workflow supports semantic versioning tags:
- `v1.0.0` → Creates tags: `1.0.0`, `1.0`, `1`, `latest`
- `v2.3.4` → Creates tags: `2.3.4`, `2.3`, `2`

### Example

```bash
# Tag and push
git tag v1.0.0
git push origin v1.0.0

# Pull the image
docker pull ghcr.io/your-username/pod-bay:1.0.0
docker pull ghcr.io/your-username/pod-bay:latest
```

