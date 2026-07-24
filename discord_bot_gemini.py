import discord
import os
import aiohttp
import json
from discord.ext import commands
from dotenv import load_dotenv

# Load biến môi trường từ file .env (chạy local)
# Trên Render bạn set biến môi trường trực tiếp
load_dotenv()

# ========== CẤU HÌNH ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Các câu hỏi đặc biệt (hỗ trợ tiếng Việt & tiếng Anh, không phân biệt hoa thường)
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

    # Tiếng Anh
    "who created you": "I am an AI created by Magic_Master",
    "who made you": "I am an AI created by Magic_Master",
    "who built you": "I am an AI created by Magic_Master",
    "what can you do": "I am here to answer your questions",
    "what is your purpose": "I am here to answer your questions",
    "what do you do": "I am here to answer your questions",
}

# ========== BOT SETUP ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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

            # Trích xuất text từ response
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
    """Kiểm tra câu hỏi đặc biệt (không phân biệt hoa thường, bỏ dấu câu thừa)."""
    cleaned = text.lower().strip().rstrip("?.!,:;")
    return SPECIAL_RESPONSES.get(cleaned)


@bot.event
async def on_ready():
    print(f"✅ Bot đã online với tên: {bot.user}")
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
    # Bỏ qua tin nhắn của chính bot
    if message.author == bot.user:
        return

    # Xử lý prefix commands trước
    await bot.process_commands(message)

    # Nếu bot được mention hoặc reply, trả lờ
    bot_mentioned = bot.user.mentioned_in(message)
    is_reply = message.reference and message.reference.resolved
    if is_reply and message.reference.resolved:
        is_reply = message.reference.resolved.author == bot.user

    if bot_mentioned or is_reply:
        # Lấy nội dung tin nhắn (bỏ mention)
        content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not content:
            await message.reply("👋 Xin chào! Bạn cần mình giúp gì? Hãy đặt câu hỏi nhé!")
            return

        # Kiểm tra câu hỏi đặc biệt
        special = check_special_question(content)
        if special:
            await message.reply(special)
            return

        # Gọi Gemini
        async with message.channel.typing():
            response = await call_gemini(content)

        # Discord giới hạn 2000 ký tự mỗi tin nhắn
        if len(response) > 2000:
            # Chia thành nhiều tin nhắn
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
              "`!help` - Hiển thị trợ giúp này",
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


# ========== CHẠY BOT ==========
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Thiếu DISCORD_TOKEN! Hãy set biến môi trường.")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ Thiếu GEMINI_API_KEY! Hãy set biến môi trường.")
        exit(1)

    bot.run(DISCORD_TOKEN)
