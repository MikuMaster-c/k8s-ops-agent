#!/usr/bin/env bash
# 在 PowerShell 里用：bash scripts/build.sh
# 之所以要 kind load 而不是 push：kind 的节点是容器，本地没有镜像仓库。
set -euo pipefail

CLUSTER=${CLUSTER:-agent-ops}
IMAGE=agent-ops:0.1.0

kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --config cluster/kind-config.yaml
docker build -t "$IMAGE" .
kind load docker-image "$IMAGE" --name "$CLUSTER"
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deploy/agent-ops --timeout=120s
kubectl get pods -o wide
