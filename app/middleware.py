import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

from app.errors import error_response
from app.logging_config import request_id_var

logger = logging.getLogger("app.requests")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("необработанная ошибка")
                response = error_response(request, 500, "Внутренняя ошибка сервера")

            elapsed = (time.perf_counter() - start) * 1000
            if response.status_code >= 500:
                level = logging.ERROR
            elif response.status_code >= 400:
                level = logging.WARNING
            else:
                level = logging.INFO
            if not request.url.path.startswith("/static"):
                logger.log(
                    level,
                    "%s %s -> %s (%.0f мс)",
                    request.method,
                    request.url.path,
                    response.status_code,
                    elapsed,
                )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
