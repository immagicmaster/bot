import os
import asyncio
import tempfile
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


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")


if not ASPEACT_FILE.is_file():
    raise FileNotFoundError(
        f"Không tìm thấy file: {ASPEACT_FILE}"
    )


if not LUNE_FILE.is_file():
    raise FileNotFoundError(
        f"Không tìm thấy Lune: {LUNE_FILE}"
    )


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=".",
    intents=intents
)


async def run_aspeact(input_file: Path):
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
    ctx: commands.Context,
    attachment: discord.Attachment
):
    filename = Path(attachment.filename)

    extension = filename.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        await ctx.send(
            "❌ Chỉ cho phép file `.lua` hoặc `.txt`."
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
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(data)

        await ctx.send(
            f"⏳ Đang thực thi `{attachment.filename}`..."
        )

        returncode, stdout, stderr = await run_aspeact(
            temp_path
        )

        if returncode == 0:
            result = stdout.strip()

            if not result:
                result = "Aspeact.luau executed successfully."

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
                result = "Lune returned an unknown error."

            if len(result) > 1900:
                result = result[:1900] + "\n..."

            await ctx.send(
                f"❌ Lune Error - Exit Code `{returncode}`\n"
                f"```text\n{result}\n```"
            )

    except asyncio.TimeoutError:
        await ctx.send(
            "❌ Thực thi quá thời gian cho phép."
        )

    except Exception as error:
        error_text = str(error)

        if len(error_text) > 1900:
            error_text = error_text[:1900] + "\n..."

        await ctx.send(
            f"❌ Python Error:\n"
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
    print("=" * 50)
    print("Discord Bot Started")
    print(f"Bot: {bot.user}")
    print(f"Aspeact: {ASPEACT_FILE}")
    print(f"Lune: {LUNE_FILE}")
    print("=" * 50)


@bot.command(name="l")
async def lune_command(ctx: commands.Context):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Cách dùng:\n"
            "`.l` + file `.lua` hoặc `.txt`\n"
            "Giới hạn: 1 MB"
        )
        return

    attachment = ctx.message.attachments[0]

    await execute_attachment(
        ctx,
        attachment
    )


@bot.command(name="dump")
async def dump_command(ctx: commands.Context):
    if not ctx.message.attachments:
        await ctx.send(
            "❌ Cách dùng:\n"
            "`.dump` + file `.lua` hoặc `.txt`\n"
            "Giới hạn: 1 MB"
        )
        return

    attachment = ctx.message.attachments[0]

    await execute_attachment(
        ctx,
        attachment
    )


@bot.event
async def on_command_error(
    ctx: commands.Context,
    error
):
    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):
        await ctx.send(
            "❌ Thiếu tham số."
        )
        return

    if isinstance(
        error,
        commands.CheckFailure
    ):
        await ctx.send(
            "❌ Bạn không có quyền sử dụng command này."
        )
        return

    print(
        f"Command error: {error}"
    )


if __name__ == "__main__":
    bot.run(TOKEN)