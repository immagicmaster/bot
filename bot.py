import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
API_URL = "https://leakd.up.railway.app/prometheus"
PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

# ==================== WEB SERVER (cho Render) ====================
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

# ==================== HÀM XÓA WATERMARK ====================
def remove_watermark(code: str) -> str:
    """
    Tìm và xóa dòng watermark của Leak3
    """
    watermark = "ӡeobfuѕсateԅ by Lеakӡ | discord.gg/qteAQmfJmP"
    lines = code.splitlines()
    cleaned = []
    
    for line in lines:
        # Bỏ qua dòng chứa watermark (kể cả có khoảng trắng đầu dòng)
        if watermark in line:
            continue
        cleaned.append(line)
    
    # Xóa dòng trống thừa ở đầu/cuối
    result = "\n".join(cleaned)
    return result.strip()

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, owner_id=OWNER_ID)

@bot.event
async def setup_hook():
    bot.session = aiohttp.ClientSession()
    
    # Đăng ký slash command
    bot.tree.add_command(promdeobf)
    
    # Sync lệnh
    if GUILD_ID:
        guild_obj = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"✅ Đã sync {len(synced)} lệnh vào server ID {GUILD_ID}")
    else:
        synced = await bot.tree.sync()
        print(f"✅ Đã sync {len(synced)} lệnh GLOBAL (có thể mất 1-60 phút)")

@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Owner ID: {OWNER_ID}")

# ==================== SLASH COMMAND: /promdeobf ====================
@app_commands.check(lambda i: i.user.id == OWNER_ID)
@app_commands.command(name="promdeobf", description="Deobfuscate Prometheus Lua script")
@app_commands.describe(file="File Lua script cần deobfuscate")
async def promdeobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)
    
    # Kiểm tra file
    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return
    
    if file.size > 5 * 1024 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn 5MB.", ephemeral=True)
        return
    
    try:
        # Đọc file từ Discord
        file_bytes = await file.read()
        
        # Gửi đến API
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
            
            # Lấy code từ API
            raw_code = data.get("deobfuscated_code", "")
            if not raw_code:
                await interaction.followup.send("❌ Không nhận được code từ API!", ephemeral=True)
                return
            
            # ⭐ XÓA WATERMARK
            clean_code = remove_watermark(raw_code)
            
            # Nếu sau khi xóa watermark mà rỗng
            if not clean_code:
                await interaction.followup.send("❌ File rỗng sau khi xử lý!", ephemeral=True)
                return
            
            # Chuẩn bị tên file output
            output_name = file.filename.replace('.lua', '_clean.lua')
            if not output_name.endswith('.lua'):
                output_name += '.lua'
            
            # Gửi kết quả
            if len(clean_code) < 1900:
                # Gửi trực tiếp trong chat
                await interaction.followup.send(
                    f"✅ **Deobfuscate Thành Công**\n"
                    f"📁 `{file.filename}` → `{output_name}`\n"
                )
            else:
                # Gửi dưới dạng file
                file_obj = discord.File(
                    io.BytesIO(clean_code.encode('utf-8')),
                    filename=output_name
                )
                await interaction.followup.send(
                    f"✅ **Deobfuscate Success**\n"
                    f"📁 `{file.filename}` → `{output_name}`\n"
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

# ==================== CHẠY ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
