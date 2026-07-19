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

# Render cấp port qua biến môi trường, mặc định 10000
PORT = int(os.environ.get("PORT", 10000))

# ==================== KEEP ALIVE WEB SERVER ====================
async def handle(request):
    return web.Response(text="🤖 Bot is alive!")

app = web.Application()
app.router.add_get("/", handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server đang chạy trên port {PORT}")

# ==================== DISCORD BOT ====================
intents = discord.Intents.default()
intents.message_content = True

class PrometheusBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            owner_id=OWNER_ID
        )
        self.session = None
    
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        try:
            synced = await self.tree.sync()
            print(f"✅ Đã đồng bộ {len(synced)} slash command(s)")
        except Exception as e:
            print(f"❌ Lỗi đồng bộ: {e}")
    
    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = PrometheusBot()

@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Owner ID: {OWNER_ID}")

def is_owner(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

@app_commands.check(is_owner)
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
                error_msg = data.get("error", "Không rõ lỗi")
                await interaction.followup.send(f"❌ API báo lỗi: {error_msg}", ephemeral=True)
                return
            
            deobfuscated_code = data.get("deobfuscated_code", "")
            
            if not deobfuscated_code:
                await interaction.followup.send("❌ Không nhận được code từ API!", ephemeral=True)
                return
            
            output_filename = f"deobfuscated_{file.filename.replace('.lua', '_clean.lua')}"
            
            if len(deobfuscated_code) < 1900:
                await interaction.followup.send(
                    f"✅ **Deobfuscate thành công!**\n📁 `{file.filename}` | 📏 {len(deobfuscated_code)} ký tự\n"
                    f"```lua\n{deobfuscated_code}\n```"
                )
            else:
                file_obj = discord.File(io.BytesIO(deobfuscated_code.encode('utf-8')), filename=output_filename)
                await interaction.followup.send(
                    f"✅ **Deobfuscate thành công!**\n📁 `{file.filename}` | 📏 {len(deobfuscated_code)} ký tự",
                    file=file_obj
                )
    
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: `{str(e)}`", ephemeral=True)

@promdeobf.error
async def promdeobf_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("🚫 Chỉ owner mới dùng được lệnh này!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Lỗi: `{str(error)}`", ephemeral=True)

# ==================== CHẠY SONG SONG ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
