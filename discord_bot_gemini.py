import discord
import os
import aiohttp
import json
import asyncio
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

# Load .env khi chạy local
load_dotenv()

# ========== CẤU HÌNH ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
PORT = int(os.getenv("PORT", 8080))  # Render cung cấp biến PORT

# Các câu hỏi đặc biệt (hỗ trợ tiếng Việt & tiếng Anh)
SPECIAL_RESPONSES = {
    # Tiếng Việt
    "bạn tạo bởi ai": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn được tạo bởi ai": "Tôi Là AI Tạo Bởi Magic_Master",
    "ai tạo ra bạn": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn do ai tạo": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn có tác dụng gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "bạn làm được gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "chức năng của bạn": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "bạn dùng để làm gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "bạn là ai": "Tôi Là AI Tạo Bởi Magic_Master",

    # Tiếng Anh
    "who created you": "I am an AI created by Magic_Master",
    "who made you": "I am an AI created by Magic_Master",
    "who built you": "I am an AI created by Magic_Master",
    "what can you do": "I am here to answer your questions",
    "what is your purpose": "I am here to answer your questions",
    "what do you do": "I am here to answer your questions",
    "who are you": "I am an AI created by Magic_Master",
}

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


async def call_gemini(prompt: str) -> str:
    """Gọi API Gemini Flash để lấy phản hồi."""
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GEMINI_URL, headers=headers, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                return f"❌ Lỗi API (Status {resp.status}): {error_text}"

            data = await resp.json()

            try:
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "Không có phản hồi.")
                return "🤖 Không nhận được phản hồi từ Gemini."
            except Exception as e:
                return f"❌ Lỗi xử lý phản hồi: {str(e)}"


def check_special_question(text: str) -> str | None:
    """Kiểm tra câu hỏi đặc biệt (không phân biệt hoa thường)."""
    cleaned = text.lower().strip().rstrip("?.!,:;")
    return SPECIAL_RESPONSES.get(cleaned)


# ========== DISCORD EVENTS ==========

@bot.event
async def on_ready():
    print(f"✅ Bot đã online: {bot.user}")
    print(f"🤖 ID: {bot.user.id}")
    print(f"🔗 Đang hoạt động trên {len(bot.guilds)} server")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="Magic_Master's Commands | !help"
        )
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    bot_mentioned = bot.user.mentioned_in(message)
    is_reply = False
    if message.reference and message.reference.resolved:
        is_reply = message.reference.resolved.author == bot.user

    if bot_mentioned or is_reply:
        content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not content:
            await message.reply("👋 Xin chào! Bạn cần mình giúp gì? Hãy đặt câu hỏi nhé!")
            return

        special = check_special_question(content)
        if special:
            await message.reply(special)
            return

        async with message.channel.typing():
            response = await call_gemini(content)

        if len(response) > 2000:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            first = True
            for chunk in chunks:
                if first:
                    await message.reply(chunk)
                    first = False
                else:
                    await message.channel.send(chunk)
        else:
            await message.reply(response)


# ========== COMMANDS ==========

@bot.command(name="ask")
async def ask_command(ctx: commands.Context, *, question: str):
    """!ask <câu hỏi> - Hỏi Gemini Flash"""
    special = check_special_question(question)
    if special:
        await ctx.reply(special)
        return

    async with ctx.typing():
        response = await call_gemini(question)

    if len(response) > 2000:
        chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
        first = True
        for chunk in chunks:
            if first:
                await ctx.reply(chunk)
                first = False
            else:
                await ctx.send(chunk)
    else:
        await ctx.reply(response)


@bot.command(name="chat")
async def chat_command(ctx: commands.Context, *, message: str):
    """!chat <tin nhắn> - Chat với Gemini Flash"""
    await ask_command(ctx, question=message)


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    """!help - Hiển thị trợ giúp"""
    embed = discord.Embed(
        title="🤖 Magic_Master AI Bot - Trợ Giúp",
        description="Bot sử dụng Google Gemini Flash để trả lờ câu hỏi.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="💬 Tương tác",
        value="• **Mention bot** hoặc **Reply** tin nhắn của bot để chat\n"
              "• Bot tự động trả lờ khi được tag",
        inline=False
    )
    embed.add_field(
        name="⌨️ Lệnh",
        value="`!ask <câu hỏi>` - Hỏi Gemini Flash\n"
              "`!chat <tin nhắn>` - Chat với bot\n"
              "`!help` - Hiển thị trợ giúp này\n"
              "`!ping` - Kiểm tra độ trễ",
        inline=False
    )
    embed.add_field(
        name="❓ Câu hỏi đặc biệt",
        value="• *Bạn tạo bởi ai?* → Tôi Là AI Tạo Bởi Magic_Master\n"
              "• *Bạn có tác dụng gì?* → Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
        inline=False
    )
    embed.set_footer(text="Powered by Google Gemini Flash | Created by Magic_Master")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping_command(ctx: commands.Context):
    """!ping - Kiểm tra độ trễ"""
    latency = round(bot.latency * 1000)
    await ctx.reply(f"🏓 Pong! Độ trễ: **{latency}ms**")


# ========== HTTP SERVER (cho Render Web Service) ==========

async def health_check(request):
    """Endpoint kiểm tra trạng thái bot."""
    status = {
        "status": "online" if bot.is_ready() else "connecting",
        "bot_user": str(bot.user) if bot.user else None,
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "latency_ms": round(bot.latency * 1000, 2) if bot.is_ready() else None
    }
    return web.json_response(status)


async def start_http_server():
    """Khởi động HTTP server để Render không kill bot."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 HTTP server đang chạy tại port {PORT}")


# ========== MAIN ==========

async def main():
    # Kiểm tra biến môi trường
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN! Hãy set biến môi trường trên Render.")
        return
    if not GEMINI_API_KEY:
        print("❌ Thiếu GEMINI_API_KEY! Hãy set biến môi trường trên Render.")
        return

    # Chạy cả HTTP server và Discord bot song song
    await asyncio.gather(
        start_http_server(),
        bot.start(DISCORD_TOKEN)
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot đã dừng bởi ngườ dùng.")
    except Exception as e:
        print(f"\n❌ Lỗi nghiêm trọng: {e}")
        raise
