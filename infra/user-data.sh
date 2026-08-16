#!/bin/bash
set -euxo pipefail

# Install NVIDIA drivers and container toolkit
apt-get update
apt-get install -y nvidia-driver-535 nvidia-container-toolkit

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Configure NVIDIA Container Runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Pull and run vLLM
docker run -d \
  --gpus all \
  --name vllm \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.9

# Signal ready
echo "vLLM instance ready" > /tmp/ready.txt
