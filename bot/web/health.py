from __future__ import annotations

from aiohttp import web


class HealthServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.ready = False
        self.app = web.Application()
        self.app.add_routes(
            [
                web.get("/", self.root),
                web.get("/health", self.health),
                web.get("/ready", self.readiness),
            ]
        )
        self.runner: web.AppRunner | None = None

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def root(self, _: web.Request) -> web.Response:
        return web.json_response({"service": "Persian Shop Bot", "status": "running"})

    async def health(self, _: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def readiness(self, _: web.Request) -> web.Response:
        status = 200 if self.ready else 503
        return web.json_response({"ready": self.ready}, status=status)
