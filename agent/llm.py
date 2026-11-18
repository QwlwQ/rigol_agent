"""Provider boundary: standard HTTP only; no provider SDK leaks."""
import json
import os
import time
import httpx
from pydantic import ValidationError
from models.planning import AgentError, Proposal

class LLMClient:
    def __init__(self, *, model=None, base_url=None, api_key=None, timeout=30,
                 retries=2, structured_output="json_object", transport=None):
        self.model = model or os.getenv("RIGOL_MODEL")
        key = api_key or os.getenv("RIGOL_API_KEY")
        if not key or not self.model:
            raise AgentError("请配置 RIGOL_API_KEY 和 RIGOL_MODEL。")
        if structured_output not in {"json_object", "json_schema"}:
            raise AgentError("未知 structured_output 配置")
        self.format = structured_output
        self.retries = max(0, min(int(retries), 5))
        self.client = httpx.Client(base_url=(base_url or os.getenv("RIGOL_BASE_URL", "https://api.openai.com/v1")).rstrip("/")+"/",
            headers={"Authorization": "Bearer "+key}, timeout=timeout, transport=transport)

    def propose(self, messages):
        fmt = {"type": self.format}
        if self.format == "json_schema":
            fmt["json_schema"] = {"name": "task_proposal", "schema": Proposal.model_json_schema(), "strict": False}
        for attempt in range(self.retries + 1):
            try:
                response = self.client.post("chat/completions", json={"model": self.model,
                    "messages": messages, "response_format": fmt})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.retries:
                        time.sleep(min(2 ** attempt, 4))
                        continue
                response.raise_for_status()
                choice = response.json()["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise AgentError("模型输出被截断或未完成，请缩小任务后重试。")
                message = choice["message"]
                if message.get("refusal"):
                    raise AgentError("模型拒绝了该请求。")
                return Proposal.model_validate_json(message["content"])
            except httpx.TransportError:
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 4))
                    continue
                raise AgentError("模型连接失败或超时，请检查网络和 API 地址。") from None
            except httpx.HTTPStatusError as exc:
                raise AgentError(f"模型 API 返回 HTTP {exc.response.status_code}；请检查配置。") from None
            except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                if isinstance(exc, AgentError):
                    raise
                raise AgentError("模型返回了无效结构；未创建任务。") from None
        raise AgentError("模型重试次数已耗尽。")

    def close(self):
        self.client.close()
