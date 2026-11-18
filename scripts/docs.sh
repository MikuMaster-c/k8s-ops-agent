#!/usr/bin/env bash
# 把 kubernetes/website 的中文文档抽少量进 docs/，再建索引。
# 只取 Pod 生命周期与排障两节：语料要覆盖评测集问到的概念，
# 又不能大到让"检索质量"变成"语料质量"的副产品。
set -euo pipefail

DEST=${1:-docs}
mkdir -p "$DEST"

if [ ! -d /tmp/k8s-website ]; then
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/kubernetes/website.git /tmp/k8s-website
fi
cd /tmp/k8s-website
git sparse-checkout set content/zh-cn/docs

cp content/zh-cn/docs/concepts/workloads/pods/pod-lifecycle.md "$OLDPWD/$DEST/01-pod-lifecycle.md"
cp content/zh-cn/docs/tasks/debug/debug-application/debug-pods.md "$OLDPWD/$DEST/02-debug-pods.md"
cp content/zh-cn/docs/tasks/debug/debug-application/debug-running-pod.md "$OLDPWD/$DEST/03-debug-running-pod.md"
cp content/zh-cn/docs/concepts/configuration/manage-resources-containers.md "$OLDPWD/$DEST/04-resources.md"

cd "$OLDPWD"
python -m agent.rag 2>/dev/null || python -c "from agent.rag import build; from pathlib import Path; build(Path('$DEST'))"
echo "docs ready: $(ls -1 $DEST | wc -l) files"
