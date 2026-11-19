"""Redis：缓存 describe 结果。

为什么缓存 describe 而不缓存诊断结果：
诊断结论依赖时间点，缓存它会让第二次问同一个 Pod 拿到过期结论；
而 describe 在 30 秒内的漂移极小，且规则和模型要读同一份。

降级策略只有一条：Redis 不可用就直接直连 kubectl，不让缓存成为故障点。
"""
import json
import os

import redis

_client = None


def client():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_timeout=0.3,     # 缓存失败不能拖慢诊断
        )
    return _client


def get_text(key: str, ttl: int = 30) -> str | None:
    return client().get(f"describe:{key}")


def put_text(key: str, text: str, ttl: int = 30) -> None:
    client().setex(f"describe:{key}", ttl, text)


def cached_describe(pod: str, namespace: str, fetch) -> str:
    """fetch 是被缓存的取数函数；缓存层不认识 kubectl。

    Redis 挂掉时直接走 fetch：缓存是加速手段，不能变成诊断链路的前提。
    这里只包 try/except 不加重试——重试解决不了 Redis 没起来，只会拖慢故障响应。
    """
    key = f"{namespace}/{pod}"
    try:
        hit = get_text(key)
        if hit is not None:
            return hit
    except Exception:
        return fetch(pod, namespace)
    text = fetch(pod, namespace)
    try:
        put_text(key, text)
    except Exception:
        pass  # 写不进去不影响这次结果
    return text
