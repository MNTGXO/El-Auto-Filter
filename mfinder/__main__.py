import os
import asyncio
import uvloop
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
from mfinder import APP_ID, API_HASH, BOT_TOKEN

uvloop.install()


def _validate_required_config():
    missing = []
    if not str(APP_ID).strip():
        missing.append("APP_ID")
    if not str(API_HASH).strip():
        missing.append("API_HASH")
    if not str(BOT_TOKEN).strip():
        missing.append("BOT_TOKEN")

    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variable(s): {missing_vars}. "
            "Set these values in your deployment environment and restart the service."
        )


async def _start_healthcheck_server(status):
    port = os.environ.get("PORT")
    if not port:
        return None

    async def handle_client(reader, writer):
        try:
            await reader.read(1024)
            body_text = status.get("message", "ok")
            body = body_text.encode("utf-8")
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("utf-8")
                + b"Connection: close\r\n\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "0.0.0.0", int(port))
    return server


async def _run_bot(status):
    _validate_required_config()

    plugins = dict(root="mfinder/plugins")
    app = Client(
        name="mfinder",
        api_id=int(APP_ID),
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins,
    )

    async with app:
        me = await app.get_me()
        status["message"] = "ok"
        print(
            f"{me.first_name} - @{me.username} - Pyrogram v{__version__} (Layer {layer}) - Started..."
        )
        await idle()
        print(f"{me.first_name} - @{me.username} - Stopped !!!")


async def main():
    status = {"message": "starting"}
    health_server = await _start_healthcheck_server(status)

    try:
        await _run_bot(status)
    except Exception as exc:
        status["message"] = f"bot_start_failed: {exc}"
        print(status["message"])

        if health_server:
            while True:
                await asyncio.sleep(3600)
        raise
    finally:
        if health_server:
            health_server.close()
            await health_server.wait_closed()


uvloop.run(main())
