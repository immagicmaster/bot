import discord
import os
import aiohttp
import json
import asyncio
import time
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ========== CẤU HÌNH ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 8080))

# Danh sách model theo thứ tự ưu tiên (model đầu tiên hết quota → thử model sau)
GEMINI_MODELS = [
    "gemini-1.5-flash",      # 15 RPM, 1,500 RPD - quota cao nhất free tier
    "gemini-2.0-flash",      # 15 RPM, 1,500 RPD
    "gemini-2.5-flash",      # 10 RPM, 250 RPD
]

# Rate limit: mỗi user chỉ được gọi API 1 lần / 5 giây
RATE_LIMIT_SECONDS = 5
user_cooldown = {}  # {user_id: last_request_timestamp}

# Các câu hỏi đặc biệt
SPECIAL_RESPONSES = {
    "bạn tạo bởi ai": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn được tạo bởi ai": "Tôi Là AI Tạo Bởi Magic_Master",
    "ai tạo ra bạn": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn do ai tạo": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn là ai": "Tôi Là AI Tạo Bởi Magic_Master",
    "bạn có tác dụng gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "bạn làm được gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "chức năng của bạn": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "bạn dùng để làm gì": "Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
    "who created you": "I am an AI created by Magic_Master",
    "who made you": "I am an AI created by Magic_Master",
    "who built you": "I am an AI created by Magic_Master",
    "who are you": "I am an AI created by Magic_Master",
    "what can you do": "I am here to answer your questions",
    "what is your purpose": "I am here to answer your questions",
    "what do you do": "I am here to answer your questions",
}

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def check_rate_limit(user_id: int) -> tuple[bool, int]:
    """Kiểm tra rate limit. Trả về (có_thể_gọi, giây_còn_lại)."""
    now = time.time()
    last = user_cooldown.get(user_id, 0)
    elapsed = now - last
    if elapsed < RATE_LIMIT_SECONDS:
        return False, int(RATE_LIMIT_SECONDS - elapsed)
    user_cooldown[user_id] = now
    return True, 0


async def call_gemini(prompt: str) -> tuple[str, bool]:
    """
    Gọi API Gemini với fallback model.
    Trả về: (phản_hồi, có_thành_công)
    """
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    last_error = ""

    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                    if resp.status == 429:
                        error_data = await resp.json()
                        # Thử lấy thờ gian retry
                        retry_delay = "không xác định"
                        try:
                            for detail in error_data.get("error", {}).get("details", []):
                                if detail.get("@type", "").endswith("RetryInfo"):
                                    retry_delay = detail.get("retryDelay", "không xác định")
                        except:
                            pass
                        last_error = f"Model {model} hết quota (thử lại sau {retry_delay})."
                        continue  # Thử model tiếp theo

                    if resp.status != 200:
                        text = await resp.text()
                        last_error = f"Model {model} lỗi {resp.status}: {text[:200]}"
                        continue

                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "Không có phản hồi."), True
                    return "🤖 Không nhận được phản hồi.", True

        except asyncio.TimeoutError:
            last_error = f"Model {model} timeout."
            continue
        except Exception as e:
            last_error = f"Model {model} lỗi: {str(e)}"
            continue

    # Tất cả model đều fail
    return f"⏳ Tất cả model đều hết quota hoặc lỗi.\n💡 Nguyên nhân: API key free tier chỉ cho phép ~10-15 request/phút và ~250-1500 request/ngày.\n🔧 Cách fix:\n1. Đợi 1 phút rồi thử lại\n2. Tạo API key MỚI trên Google AI Studio\n3. Hoặc nâng cấp lên paid tier\n\nChi tiết lỗi: {last_error}", False


def check_special_question(text: str) -> str | None:
    cleaned = text.lower().strip().rstrip("?.!,:;")
    return SPECIAL_RESPONSES.get(cleaned)


# ========== DISCORD EVENTS ==========

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user}")
    print(f"🤖 ID: {bot.user.id}")
    print(f"🔗 Servers: {len(bot.guilds)}")
    print(f"⚡ Rate limit: {RATE_LIMIT_SECONDS}s/user")
    print(f"🧠 Models: {', '.join(GEMINI_MODELS)}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Magic_Master | !help"
        )
    )


async def send_long_message(destination, text: str, reply_to=None):
    """Gửi tin nhắn dài, tự động chia chunk nếu >2000 ký tự."""
    if len(text) <= 2000:
        if reply_to:
            return await reply_to.reply(text)
        return await destination.send(text)

    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
    first_msg = None
    for i, chunk in enumerate(chunks):
        if i == 0 and reply_to:
            first_msg = await reply_to.reply(chunk)
        else:
            first_msg = await destination.send(chunk)
    return first_msg


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
            await message.reply("👋 Xin chào! Bạn cần mình giúp gì?")
            return

        # Kiểm tra rate limit
        can_call, wait_sec = check_rate_limit(message.author.id)
        if not can_call:
            await message.reply(f"⏳ Bạn gọi quá nhanh! Vui lòng đợi **{wait_sec} giây** rồi thử lại.")
            return

        # Câu hỏi đặc biệt
        special = check_special_question(content)
        if special:
            await message.reply(special)
            return

        # Gọi Gemini
        async with message.channel.typing():
            response, success = await call_gemini(content)

        await send_long_message(message.channel, response, reply_to=message)


# ========== COMMANDS ==========

@bot.command(name="ask")
async def ask_command(ctx: commands.Context, *, question: str):
    can_call, wait_sec = check_rate_limit(ctx.author.id)
    if not can_call:
        await ctx.reply(f"⏳ Bạn gọi quá nhanh! Đợi **{wait_sec} giây** rồi thử lại.")
        return

    special = check_special_question(question)
    if special:
        await ctx.reply(special)
        return

    async with ctx.typing():
        response, success = await call_gemini(question)

    await send_long_message(ctx.channel, response, reply_to=ctx.message)


@bot.command(name="chat")
async def chat_command(ctx: commands.Context, *, message: str):
    await ask_command(ctx, question=message)


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 Magic_Master AI Bot",
        description="Bot dùng Google Gemini (Free Tier).",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="💬 Tương tác",
        value="• **Mention** hoặc **Reply** bot để chat\n• Bot tự động trả lờ khi được tag",
        inline=False
    )
    embed.add_field(
        name="⌨️ Lệnh",
        value="`!ask <câu hỏi>` - Hỏi Gemini\n"
              "`!chat <tin nhắn>` - Chat\n"
              "`!ping` - Kiểm tra độ trễ",
        inline=False
    )
    embed.add_field(
        name="⚡ Giới hạn",
        value=f"• Mỗi user: **{RATE_LIMIT_SECONDS} giây** giữa 2 lần hỏi\n"
              "• Free tier: ~10-15 request/phút, ~250-1500 request/ngày",
        inline=False
    )
    embed.add_field(
        name="❓ Câu hỏi đặc biệt",
        value="• *Bạn tạo bởi ai?* → Tôi Là AI Tạo Bởi Magic_Master\n"
              "• *Bạn có tác dụng gì?* → Tôi Có Tác Dụng Giải Đáp Câu Hỏi Bạn",
        inline=False
    )
    embed.set_footer(text="Powered by Gemini | Created by Magic_Master")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping_command(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"🏓 Pong! **{latency}ms**")


# ========== HTTP SERVER ==========

async def health_check(request):
    status = {
        "status": "online" if bot.is_ready() else "connecting",
        "bot": str(bot.user) if bot.user else None,
        "servers": len(bot.guilds),
        "models": GEMINI_MODELS,
        "rate_limit": f"{RATE_LIMIT_SECONDS}s/user"
    }
    return web.json_response(status)


async def start_http_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 HTTP server: port {PORT}")


# ========== MAIN ==========

async def main():
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN!")
        return
    if not GEMINI_API_KEY:
        print("❌ Thiếu GEMINI_API_KEY!")
        return

    await asyncio.gather(
        start_http_server(),
        bot.start(DISCORD_TOKEN)
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot dừng.")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        raise
