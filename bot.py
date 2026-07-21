import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re
from duckduckgo_search import DDGS
import google.generativeai as genai

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
API_URL = "https://leakd.up.railway.app/prometheus"
PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

# Cấu hình Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("LỖI: Chưa cấu hình 'GEMINI_API_KEY' trong Biến Môi Trường (Environment Variables)!")

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# ==================== WEB SERVER ====================
async def handle(request):
    return web.Response(text="🤖 Bot is alive!")

app = web.Application()
app.router.add_get("/", handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server chạy trên port {PORT}")

# ==================== XÓA WATERMARK ====================
def remove_watermarks(code: str) -> str:
    """
    Xóa TẤT CẢ dòng chứa watermark của Leak3.
    Dùng URL cố định để bắt chính xác, không phụ thuộc Unicode homoglyphs.
    """
    lines = code.splitlines()
    cleaned = []
    removed_count = 0
    
    leak_url = "discord.gg/qteAQmfJmP"
    
    for i, line in enumerate(lines):
        if leak_url in line:
            removed_count += 1
            print(f"🗑️ Đã xóa dòng {i+1}: {line.strip()[:80]}...")
            continue
        
        if re.search(r'discord\.gg/\w+', line, re.IGNORECASE) and (
            'obfu' in line.lower() or 'leak' in line.lower()
        ):
            removed_count += 1
            print(f"🗑️ Đã xóa dòng {i+1} (regex): {line.strip()[:80]}...")
            continue
            
        cleaned.append(line)
    
    print(f"📊 Đã xóa {removed_count} dòng watermark")
    return "\n".join(cleaned).strip()

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, owner_id=OWNER_ID)

@bot.event
async def setup_hook():
    bot.session = aiohttp.ClientSession()
    bot.tree.add_command(promdeobf)
    bot.tree.add_command(ai_command)
    
    if GUILD_ID:
        guild_obj = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"✅ Đã sync {len(synced)} lệnh vào server ID {GUILD_ID}")
    else:
        synced = await bot.tree.sync()
        print(f"✅ Đã sync {len(synced)} lệnh GLOBAL")

@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Owner ID: {OWNER_ID}")

# ==================== /promdeobf ====================
@app_commands.check(lambda i: i.user.id == OWNER_ID)
@app_commands.command(name="promdeobf", description="Deobfuscate Prometheus Lua script")
@app_commands.describe(file="File Lua script cần deobfuscate")
async def promdeobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)
    
    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return
    
    if file.size > 5 * 1024 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn 5MB.", ephemeral=True)
        return
    
    try:
        file_bytes = await file.read()
        
        form_data = aiohttp.FormData()
        form_data.add_field('file', file_bytes, filename=file.filename, content_type='application/octet-stream')
        
        async with bot.session.post(API_URL, data=form_data) as response:
            if response.status != 200:
                await interaction.followup.send(f"❌ API lỗi HTTP {response.status}", ephemeral=True)
                return
            
            data = await response.json()
            
            if not data.get("success", False):
                await interaction.followup.send(f"❌ API báo lỗi: {data.get('error', 'Không rõ')}", ephemeral=True)
                return
            
            raw_code = data.get("deobfuscated_code", "")
            if not raw_code:
                await interaction.followup.send("❌ Không nhận được code từ API!", ephemeral=True)
                return
            
            clean_code = remove_watermarks(raw_code)
            if not clean_code:
                await interaction.followup.send("❌ File rỗng sau khi xử lý!", ephemeral=True)
                return
            
            output_name = file.filename.replace('.lua', '_deobf.lua')
            if not output_name.endswith('.lua'):
                output_name += '.lua'
            
            file_obj = discord.File(
                io.BytesIO(clean_code.encode('utf-8')),
                filename=output_name
            )
            
            await interaction.followup.send(
                f"✅ Deobfuscated Success\n📝 `{output_name}`",
                file=file_obj
            )
    
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@promdeobf.error
async def promdeobf_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("🚫 Chỉ owner mới dùng được lệnh này!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Lỗi: `{error}`", ephemeral=True)

# ==================== /ai ====================
@app_commands.command(name="ai", description="Hỏi AI bất kỳ câu hỏi nào (Tự động tìm kiếm Internet)")
@app_commands.describe(cau_hoi="Nhập câu hỏi bạn muốn tìm kiếm")
async def ai_command(interaction: discord.Interaction, cau_hoi: str):
    
    # 1. Kiểm tra câu hỏi đặc biệt
    clean_q = cau_hoi.strip().lower()
    special_queries = [
        "bạn được tạo bởi ai", "ban duoc tao boi ai", 
        "ai tạo ra bạn", "ai tao ra ban",
        "who created you", "who made you"
    ]
    if any(q in clean_q for q in special_queries):
        await interaction.response.send_message("Tôi là AI được tạo bởi code python")
        return

    # 2. Hoãn phản hồi (Defer) để tránh timeout 3s
    await interaction.response.defer()

    try:
        # 3. Tìm kiếm trên Web
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(cau_hoi, max_results=3):
                results.append(r)

        if not results:
            await interaction.followup.send("Không tìm thấy thông tin phù hợp trên Internet.")
            return

        search_context = ""
        sources_list = []
        for idx, item in enumerate(results, 1):
            search_context += f"Nguồn {idx}: {item['title']}\nNội dung: {item['body']}\n\n"
            sources_list.append(f"{idx}. [{item['title']}]({item['href']})")

        # 4. AI xử lý
        prompt = f"""
        Bạn là một trợ lý AI thông minh.
        Dưới đây là thông tin tìm kiếm được từ Internet cho câu hỏi của người dùng.

        YÊU CẦU BẮT BUỘC:
        1. Đọc dữ liệu tìm kiếm bên dưới và trả lời câu hỏi một cách chính xác, ngắn gọn.
        2. CHỈ TRẢ LỜI BẰNG TIẾNG VIỆT HOẶC TIẾNG ANH (Tùy theo ngôn ngữ mà người dùng đặt câu hỏi).

        Câu hỏi của người dùng: {cau_hoi}

        Dữ liệu tìm kiếm từ Internet:
        {search_context}
        """

        response = ai_model.generate_content(prompt)
        ai_reply = response.text

        # 5. Đóng gói kết quả
        sources_formatted = "\n".join(sources_list)
        final_response = f"**❓ Câu hỏi:** {cau_hoi}\n\n**🤖 Trả lời:**\n{ai_reply}\n\n**📌 Nguồn tham khảo:**\n{sources_formatted}"

        if len(final_response) > 2000:
            final_response = final_response[:1900] + "\n\n*(Nội dung quá dài nên đã bị cắt bớt)*"

        await interaction.followup.send(final_response)

    except Exception as e:
        await interaction.followup.send(f"❌ Có lỗi xảy ra khi xử lý câu hỏi: {e}")

# ==================== CHẠY ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
