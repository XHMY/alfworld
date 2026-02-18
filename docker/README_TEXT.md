# ALFWorld Docker Text-Only Setup

This directory contains Docker configurations for running ALFWorld text environments without GPU requirements. This is ideal for:
- Parallel environment execution
- Cloud deployments
- Development without GPU hardware
- Large-scale experimentation

## Quick Start

### 1. Build the Docker Image

```bash
# Build the lightweight text-only image
docker build -f Dockerfile.text -t alfworld-text:latest .
```

### 2. Download Data (First Time Only)

Before running environments, download the required data:

```bash
# Download to host machine
pip install alfworld
alfworld-download

# Or download inside container
docker run -v ~/.cache/alfworld:/data alfworld-text:latest \
  bash -c "pip install alfworld && alfworld-download"
```

### 3. Run a Single Container

```bash
# Interactive shell
docker run -it \
  -v ~/.cache/alfworld:/data:ro \
  -v $(pwd)/examples:/workspace/examples \
  alfworld-text:latest bash

# Inside container, run examples:
cd /workspace/examples
python simple_example.py
```

## Parallel Environments with Docker Compose

### Option 1: Pre-defined Parallel Services

```bash
# Start 4 parallel environments
docker-compose up -d

# Run commands in specific containers
docker-compose exec alfworld-env-1 python examples/simple_example.py
docker-compose exec alfworld-env-2 python examples/simple_example.py

# Stop all containers
docker-compose down
```

### Option 2: Dynamic Scaling

```bash
# Start N parallel environments dynamically
docker-compose up --scale alfworld-base=8 -d

# List running containers
docker-compose ps

# Run a command in all containers
for i in {1..8}; do
  docker-compose exec -T alfworld-base-$i python examples/simple_example.py &
done
wait
```

## Running Parallel Environments

The `examples/parallel_envs_example.py` script demonstrates multiprocessing within a single container:

```bash
# Run with default settings (4 environments, 5 episodes each)
docker run -v ~/.cache/alfworld:/data:ro \
  alfworld-text:latest \
  python examples/parallel_envs_example.py

# Custom configuration
docker run -v ~/.cache/alfworld:/data:ro \
  alfworld-text:latest \
  python examples/parallel_envs_example.py --num-envs 8 --episodes 10
```

## Environment Variables

- `ALFWORLD_DATA`: Path to data directory (default: `/data`)

## Volume Mounts

- `/data`: ALFWorld data directory (mount `~/.cache/alfworld`)
- `/workspace/examples`: Example scripts (optional)

## Comparison: Docker Approaches

| Approach | Best For | Pros | Cons |
|----------|----------|------|------|
| **Multiple Containers** | Distributed systems, cloud deployments | True isolation, easy scaling, fault tolerance | Higher resource overhead |
| **Single Container + Multiprocessing** | Local development, single machine | Lower overhead, simpler setup | Shared resources, single point of failure |
| **TextWorld Async Batching** | Training agents | Most efficient, built-in support | Less flexibility for custom parallelization |

## Recommendations

### For Parallelization:

1. **Local Development**: Use single container with multiprocessing (`parallel_envs_example.py`)
2. **Cloud/Cluster**: Use docker-compose with multiple containers for fault tolerance
3. **Training**: Use TextWorld's built-in batch processing (see `base_config.yaml`)

### For Production:

```yaml
# Custom docker-compose.yml for your use case
services:
  alfworld-worker:
    image: alfworld-text:latest
    deploy:
      replicas: 10  # Scale as needed
    volumes:
      - data:/data:ro
    command: python your_training_script.py
```

## Troubleshooting

### Data Not Found

Ensure data is downloaded and mounted:
```bash
# Check data directory
ls -la ~/.cache/alfworld/

# If empty, download data
alfworld-download
```

### Permission Issues

If you encounter permission issues, adjust the volume mount:
```bash
docker run -u $(id -u):$(id -g) ...
```

## Advanced: Kubernetes Deployment

For large-scale deployments, consider Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alfworld-workers
spec:
  replicas: 20
  template:
    spec:
      containers:
      - name: alfworld
        image: alfworld-text:latest
        volumeMounts:
        - name: data
          mountPath: /data
          readOnly: true
```

## Differences from Original Dockerfile

| Feature | Original Dockerfile | Dockerfile.text |
|---------|-------------------|-----------------|
| Base Image | NVIDIA CUDA 9.0 | Python 3.9 slim |
| GPU Required | ✅ Yes | ❌ No |
| Image Size | ~8GB | ~500MB |
| Use Case | THOR visual envs | Text-only envs |
| Python Version | 3.6 | 3.9 |
| Ubuntu Version | 16.04 | Debian (slim) |

## See Also

- [Main README](../README.md) - General ALFWorld documentation
- [Original Docker Setup](../README.md#docker-setup) - GPU-enabled setup for THOR environments
- [TextWorld Documentation](https://textworld.readthedocs.io/) - TextWorld environment details
