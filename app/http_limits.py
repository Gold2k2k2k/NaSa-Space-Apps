"""Bound request bodies before JSON/form processing and keep failures readable."""
from __future__ import annotations

import json

from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.datasets import MAX_CSV_BYTES


class BodyLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        upload = scope["path"] == "/api/upload-csv"
        limit = MAX_CSV_BYTES + 65536 if upload else 256 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
        if length > limit:
            return await JSONResponse({"detail": "Request body exceeds the supported size"}, status_code=413)(scope, receive, send)
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, "Request body exceeds the supported size")
            return message
        if upload:
            return await self.app(scope, bounded_receive, send)
        chunks = []
        try:
            while True:
                message = await bounded_receive()
                if message["type"] == "http.disconnect":
                    return
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
        except HTTPException:
            return await JSONResponse({"detail": "Request body exceeds the supported size"}, status_code=413)(scope, receive, send)
        contents = b"".join(chunks)
        try:
            json.loads(contents)
        except RecursionError:
            return await JSONResponse({"detail": "JSON nesting is too deep"}, status_code=422)(scope, receive, send)
        except (ValueError, UnicodeError):
            pass  # FastAPI returns its normal JSON validation error.
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": contents, "more_body": False}
            return await receive()
        return await self.app(scope, replay, send)
