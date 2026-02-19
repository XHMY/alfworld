# ALFWorld Text-Only Docker Setup

This directory contains a lightweight Docker configuration for running ALFWorld text environments without GPU requirements.

## Quick Start

### 1. Build the Docker Image

```bash
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

### 3. Run the Container

**Interactive shell:**
```bash
docker run -it \
  -v ~/.cache/alfworld:/data:ro \
  alfworld-text:latest bash
```

**Run a Python script:**
```bash
docker run -v ~/.cache/alfworld:/data:ro \
  alfworld-text:latest python examples/simple_example.py
```

**With a local script:**
```bash
docker run -v ~/.cache/alfworld:/data:ro \
  -v $(pwd):/workspace \
  -w /workspace \
  alfworld-text:latest python your_script.py
```

## Environment Variables

- `ALFWORLD_DATA`: Path to data directory (default: `/data`)

## Volume Mounts

- `/data`: ALFWorld data directory (mount `~/.cache/alfworld` as read-only)
- `/workspace`: Optional working directory for your scripts

## Parallelization

For running multiple environments in parallel, use TextWorld's built-in async batching:

```python
from alfworld.agents.environment import get_environment
import alfworld.agents.modules.generic as generic

config = generic.load_config()
env = get_environment(config['env']['type'])(config, train_eval='train')

# Process multiple games in parallel within a single environment
env = env.init_env(batch_size=8)  # Run 8 games simultaneously
```

This is more efficient than running multiple Docker containers.

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

If you encounter permission issues:
```bash
docker run -u $(id -u):$(id -g) -v ~/.cache/alfworld:/data:ro ...
```

## Comparison with Original Dockerfile

| Feature | Original Dockerfile | Dockerfile.text |
|---------|-------------------|-----------------|
| Base Image | NVIDIA CUDA 9.0 | Python 3.9 slim |
| GPU Required | ✅ Yes | ❌ No |
| Image Size | ~8GB | ~500MB |
| Use Case | THOR visual envs | Text-only envs |
| Python Version | 3.6 | 3.9 |

## See Also

- [Main README](../README.md) - General ALFWorld documentation
- [Original Docker Setup](../README.md#docker-setup) - GPU-enabled setup for THOR environments
- [TextWorld Documentation](https://textworld.readthedocs.io/) - TextWorld environment details
