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

# 评测集里问到 HPA、Prometheus 指标、kind 载镜像，语料不覆盖这几篇的话，
# 那几条用例在检索层就没有答案——失败反映的是语料缺口，不是模型能力。
# 缺文件不算错：上游改了路径就跳过，评测会如实标成未命中。
for pair in \
  "concepts/workloads/autoscaling/horizontal-pod-autoscale:05-hpa" \
  "concepts/cluster-administration/system-metrics:06-metrics" \
  "concepts/cluster-administration/logging:07-logging"
do
  src=${pair%%:*}; dst=${pair##*:}
  if [ -f "content/zh-cn/docs/$src.md" ]; then
    cp "content/zh-cn/docs/$src.md" "$OLDPWD/$DEST/$dst.md"
  else
    echo "skip (not found): $src"
  fi
done

cd "$OLDPWD"
python -m agent.rag 2>/dev/null || python -c "from agent.rag import build; from pathlib import Path; build(Path('$DEST'))"
echo "docs ready: $(ls -1 $DEST | wc -l) files"
