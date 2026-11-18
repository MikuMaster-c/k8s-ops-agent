"""两个入口：诊断和清单生成。没有中间件、没有重试、没有鉴权——它们不是目标。"""
from fastapi import FastAPI
from pydantic import BaseModel

from agent.graph import run
from agent.manifest import generate

app = FastAPI(title="agent-ops")


class Ask(BaseModel):
    question: str
    pod: str = ""


class Want(BaseModel):
    requirement: str


@app.post("/diagnose")
def diagnose(body: Ask):
    out = run(body.question, body.pod)
    return {"diagnosis": out.get("diagnosis"), "bad_citations": out.get("problems")}


@app.post("/manifest")
def manifest(body: Want):
    return generate(body.requirement)
