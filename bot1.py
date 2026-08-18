import os
import asyncio
import tempfile
import traceback
from pathlib import Path

import discord
from discord.ext import commands


BASE_DIR = Path(__file__).resolve().parent

ENV_DIR = BASE_DIR / "Env"
ASPEACT_FILE = ENV_DIR / "Aspeact.luau"
LUNE_FILE = BASE_DIR / ".lune" / "bin" / "lune"

MAX_FILE_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {".lua", ".txt"}

TOKEN = os.getenv("DISCORD_TOKEN")


print("=" * 60)
print("Starting Discord Bot")
print("=" * 60)


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is missing"
    )


if not ASPEACT_FILE.exists():
    raise FileNotFoundError(
        f"Missing file: {ASPEACT_FILE}"
    )


if not LUNE_FILE.exists():
    raise FileNotFoundError(
        f"Missing Lune executable: {LUNE_FILE}"
    )


if not os.access(LUNE_FILE, os.X_OK):
    try:
        os.chmod(LUNE_FILE, 0o755)
    except Exception as error:
        raise RuntimeError(
            f"Lune is not executable: {error}"
        )


print(f"Python: {os.sys.version}")
print(f"Bot file: {BASE_DIR}")
print(f"Aspeact: {ASPEACT_FILE}")
print(f"Lune: {LUNE_FILE}")
print("Token: configured")
print("=" * 60)


intents = discord.Intents.default()

intents.message_content = True

bot = commands.Bot(
    command_prefix=".",
    intents=intents
)


async def run_aspeact(input_file: Path):
    print(
        f"Running Lune with: {input_file}"
    )

    process = await asyncio.create_subprocess_exec(
        str(LUNE_FILE),
        "run",
        str(ASPEACT_FILE),
        str(input_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    stdout_text = stdout.decode(
        "utf-8",
        errors="replace"
    )

    stderr_text = stderr.decode(
        "utf-8",
        errors="replace"
    )

    return (
        process.returncode,
        stdout_text,
        stderr_text
    )


async def execute_attachment(
    ctx,
    attachment
):
    filename = Path(
        attachment.filename
    )

    extension = filename.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        await ctx.send(
            "❌ Chỉ cho phép `.lua` hoặc `.txt`."
        )
        return

    if attachment.size > MAX_FILE_SIZE:
        await ctx.send(
            "❌ File vượt quá giới hạn 1 MB."
        )
        return

    temp_path = None

    try:
        data = await attachment.read()

        if len(data) > MAX_FILE_SIZE:
            await ctx.send(
                "❌ File vượt quá giới hạn 1 MB."
            )
            return

        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False
        ) as temp:
            temp_path = Path(temp.name)
            temp.write(data)

        await ctx.send(
            f"⏳ Executing `{attachment.filename}`..."
        )

        returncode, stdout, stderr = (
            await run_aspeact(temp_path)
        )

        if returncode == 0:
            result = stdout.strip()

            if not result:
                result = (
                    "Aspeact.luau executed successfully."
                )

            if len(result) > 1900:
                result = result[:1900] + "\n..."

            await ctx.send(
                f"```text\n{result}\n```"
            )

        else:
            result = stderr.strip()

            if not result:
                result = stdout.strip()

            if not result:
                result = "Unknown Lune error."

            if len(result) > 1900:
                result = result[:1900] + "\n..."

            await ctx.send(
                f"❌ Lune Error "
                f"(Exit Code {returncode})\n"
                f"```text\n{result}\n```"
            )

    except Exception as error:
        print(
            "Attachment execution error:"
        )

        traceback.print_exc()

        error_text = str(error)

        if len(error_text) > 1900:
            error_text = (
                error_text[:1900] + "\n..."
            )

        await ctx.send(
            f"❌ Error:\n"
            f"```text\n{error_text}\n```"
        )

    finally:
        if temp_path is not None:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass


@bot.event
async def on_ready():
    print("=" * 60)
    print("BOT LOGIN SUCCESS")
    print(f"Username: {bot.user}")
    print(f"User ID: {bot.user.id}")
    print(
        f"Guilds: {len(bot.guilds)}"
    )
    print("=" * 60)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)


@bot.command(name="l")
async def lune_command(ctx):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Upload `.lua` hoặc `.txt` "
            "cùng với `.l`."
        )
        return

    await execute_attachment(
        ctx,
        ctx.message.attachments[0]
    )


@bot.command(name="dump")
async def dump_command(ctx):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Upload `.lua` hoặc `.txt` "
            "cùng với `.dump`."
        )
        return

    await execute_attachment(
        ctx,
        ctx.message.attachments[0]
    )


@bot.event
async def on_command_error(
    ctx,
    error
):
    print(
        f"Command error: {repr(error)}"
    )

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    await ctx.send(
        f"❌ Command error:\n"
        f"```text\n{str(error)[:1800]}\n```"
    )


async def start_bot():
    try:
        print("========================================")
        print("STARTING BOT")
        print("========================================")

        await bot.start(TOKEN)

    except BaseException as error:
        print("========================================")
        print("BOT CRASHED")
        print("========================================")
        print("ERROR TYPE:", type(error).__name__)
        print("ERROR:", repr(error))

        import traceback
        traceback.print_exc()

        print("========================================")

        raise


if __name__ == "__main__":
    try:
        asyncio.run(start_bot())

    except BaseException as error:
        print("========================================")
        print("FATAL ERROR")
        print("========================================")
        print("TYPE:", type(error).__name__)
        print("ERROR:", repr(error))

        import traceback
        traceback.print_exc()

        print("========================================")

        raise