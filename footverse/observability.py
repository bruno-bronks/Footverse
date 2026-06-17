"""Observability leve do Footverse — Fase 1.

Três componentes, zero novas dependências obrigatórias:

1. `_JSONFormatter` + `setup_logging()` — logs estruturados em JSON para
   stdout, prontos para ingestão por qualquer agregador (CloudWatch, Datadog,
   Elastic, etc.).

2. `RequestLogMiddleware` — middleware Starlette que registra método, path,
   status HTTP e latência de cada request. O SLA da Fase 1 é < 500 ms para
   ações do motor determinístico; este middleware é o lugar para monitorá-lo.

3. `AgentLogger` — LangChain `BaseCallbackHandler` que registra quais tools
   o agente chamou durante uma invocação. Disponível apenas se `langchain-core`
   estiver instalado (extra `[agents]`). Caso contrário, `AgentLogger = None`
   e o advisor simplesmente omite o callback.

Integração com LangSmith (zero código extra):
  `langsmith` já está instalado como dependência transitiva do LangChain.
  Basta definir as variáveis de ambiente para ativar o tracing visual dos
  grafos LangGraph em <https://smith.langchain.com>:

      LANGCHAIN_TRACING_V2=true
      LANGCHAIN_API_KEY=ls-ant-...
      LANGCHAIN_PROJECT=footverse
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("footverse")

# ── 1. JSON formatter ─────────────────────────────────────────────────────────

_LOG_RESERVED = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs",
    "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
})


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        for k, v in vars(record).items():
            if k not in _LOG_RESERVED and not k.startswith("_"):
                d[k] = v
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Configura o logger `footverse` com saída JSON para stdout."""
    root = logging.getLogger("footverse")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JSONFormatter())
        root.addHandler(handler)


# ── 2. Middleware HTTP ────────────────────────────────────────────────────────

class RequestLogMiddleware(BaseHTTPMiddleware):
    """Loga método, path, status e latência de cada request HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": ms,
                },
            )
            return response
        except Exception as exc:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.error(
                "http_error",
                extra={"method": request.method, "path": request.url.path, "ms": ms},
                exc_info=exc,
            )
            raise


# ── 3. LangChain callback para agentes ───────────────────────────────────────

try:
    from langchain_core.callbacks import BaseCallbackHandler

    class AgentLogger(BaseCallbackHandler):
        """Registra quais tools o agente chamou durante uma invocação.

        Usado no `config={"callbacks": [...]}` do `graph.invoke()`.
        A latência total é medida externamente no `Advisor._run`.
        """

        def __init__(self, agente: str, club_id: str) -> None:
            self.agente = agente
            self.club_id = club_id
            self.tools_called: list[str] = []

        def on_tool_start(
            self, serialized: dict, input_str: str, **kwargs: Any
        ) -> None:
            name = serialized.get("name", "?")
            self.tools_called.append(name)
            logger.debug(
                "agent_tool_call",
                extra={
                    "agente": self.agente,
                    "club_id": self.club_id,
                    "tool": name,
                },
            )

        def on_tool_error(
            self, error: BaseException, **kwargs: Any
        ) -> None:
            logger.warning(
                "agent_tool_error",
                extra={
                    "agente": self.agente,
                    "club_id": self.club_id,
                    "error": str(error),
                },
            )

except ImportError:  # [agents] não instalado
    AgentLogger = None  # type: ignore[assignment, misc]
