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


async def _start_healthcheck_server():
    port = os.environ.get("PORT")
    if not port:
        return None

    async def handle_client(reader, writer):
        try:
            await reader.read(1024)
            body = b"ok"
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "0.0.0.0", int(port))
    return server


async def main():
    _validate_required_config()

    plugins = dict(root="mfinder/plugins")
    app = Client(
        name="mfinder",
        api_id=int(APP_ID),
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins,
    )

    health_server = await _start_healthcheck_server()

    async with app:
        me = await app.get_me()
        print(
            f"{me.first_name} - @{me.username} - Pyrogram v{__version__} (Layer {layer}) - Started..."
        )
        await idle()
        print(f"{me.first_name} - @{me.username} - Stopped !!!")

    if health_server:
        health_server.close()
        await health_server.wait_closed()


uvloop.run(main())
