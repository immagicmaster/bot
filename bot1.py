import os
import asyncio
import tempfile
from pathlib import Path

import discord
from discord.ext import commands


BASE_DIR = Path(__file__).resolve().parent
ENV_DIR = BASE_DIR / "Env"
ASPEACT = ENV_DIR / "Aspeact.luau"

MAX_FILE_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {".lua", ".txt"}

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")

if not ASPEACT.is_file():
    raise FileNotFoundError(f"Missing {ASPEACT}")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=".",
    intents=intents
)


async def run_aspeact(input_file: Path):
    LUNE_PATH = BASE_DIR / ".lune" / "bin" / "lune"

if not LUNE_PATH.exists():
    raise FileNotFoundError(
        f"Lune executable not found: {LUNE_PATH}"
    )
    process = await asyncio.create_subprocess_exec(
    str(LUNE_PATH),
    "run",
    str(ASPEACT),
    str(input_file),
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    return (
        process.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace")
    )


async def process_attachment(ctx, attachment: discord.Attachment):
    filename = Path(attachment.filename)

    if filename.suffix.lower() not in ALLOWED_EXTENSIONS:
        await ctx.send("❌ Chỉ chấp nhận file `.lua` hoặc `.txt`.")
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.send("❌ File vượt quá giới hạn 1 MB.")
        return

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=filename.suffix.lower(),
            delete=False
        ) as temp:
            temp_path = Path(temp.name)

        data = await attachment.read()

        if len(data) > MAX_FILE_SIZE:
            await ctx.send("❌ File vượt quá giới hạn 1 MB.")
            return

        temp_path.write_bytes(data)

        await ctx.send(
            f"⏳ Đang thực thi `{attachment.filename}` bằng Lune..."
        )

        returncode, stdout, stderr = await run_aspeact(temp_path)

        output = stdout.strip()
        error = stderr.strip()

        if returncode == 0:
            if not output:
                output = "Aspeact.luau executed successfully."

            if len(output) > 1900:
                output = output[:1900] + "\n..."

            await ctx.send(
                f"```text\n{output}\n```"
            )
        else:
            result = error or output or "Unknown Lune error."

            if len(result) > 1900:
                result = result[:1900] + "\n..."

            await ctx.send(
                f"❌ Lune exited with code `{returncode}`\n"
                f"```text\n{result}\n```"
            )

    except discord.HTTPException:
        pass

    except Exception as exc:
        message = str(exc)

        if len(message) > 1900:
            message = message[:1900] + "\n..."

        await ctx.send(
            f"❌ Error:\n```text\n{message}\n```"
        )

    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Lune script: {ASPEACT}")


@bot.command(name="l")
async def lune_command(ctx):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Hãy upload một file `.lua` hoặc `.txt` cùng với `.l`."
        )
        return

    attachment = ctx.message.attachments[0]

    await process_attachment(ctx, attachment)


@bot.command(name="dump")
async def dump_command(ctx):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Hãy upload một file `.lua` hoặc `.txt` cùng với `.dump`."
        )
        return

    attachment = ctx.message.attachments[0]

    await process_attachment(ctx, attachment)


bot.run(TOKEN)