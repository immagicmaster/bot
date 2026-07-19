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

# GUILD_ID: ID server Discord của bạn (để sync lệnh ngay lập tức)
# Nếu để trống, lệnh sẽ hiện sau 1-60 phút
GUILD_ID = os.environ.get("GUILD_ID")

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
    print(f"🌐 Web server chạy trên port {PORT}")

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True  # BẮT BUỘC cho prefix command

bot = commands.Bot(command_prefix=".", intents=intents, owner_id=OWNER_ID)
bot.session = None

@bot.event
async def setup_hook():
    bot.session = aiohttp.ClientSession()
    
    # Sync slash command — CÁCH NHANH: sync theo guild
    if GUILD_ID:
        guild_obj = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"✅ Đã sync {len(synced)} lệnh vào server ID {GUILD_ID} (hiện ngay)")
    else:
        synced = await bot.tree.sync()
        print(f"✅ Đã sync {len(synced)} lệnh GLOBAL (có thể mất 1-60 phút để hiện)")

@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Owner: {OWNER_ID}")

# ==================== LỆNH 1: .prom (PREFIX) ====================
@bot.command(name="prom")
@commands.is_owner()
async def prom_prefix(ctx: commands.Context):
    """
    Dùng: .prom (và đính kèm file .lua)
    """
    if not ctx.message.attachments:
        await ctx.send("⚠️ Vui lòng đính kèm file `.lua` hoặc `.txt`!", delete_after=10)
        return
    
    attachment = ctx.message.attachments[0]
    
    if not attachment.filename.endswith(('.lua', '.txt')):
        await ctx.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", delete_after=10)
        return
    
    if attachment.size > 5 * 1024 * 1024:
        await ctx.send("⚠️ File quá lớn! Giới hạn 5MB.", delete_after=10)
        return
    
    async with ctx.typing():
        try:
            file_bytes = await attachment.read()
            form_data = aiohttp.FormData()
            form_data.add_field('file', file_bytes, filename=attachment.filename, content_type='application/octet-stream')
            
            async with bot.session.post(API_URL, data=form_data) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ API lỗi HTTP {resp.status}")
                    return
                
                data = await resp.json()
                
                if not data.get("success", False):
                    await ctx.send(f"❌ API báo lỗi: {data.get('error', 'Không rõ')}")
                    return
                
                code = data.get("deobfuscated_code", "")
                if not code:
                    await ctx.send("❌ Không nhận được code từ API!")
                    return
                
                if len(code) < 1900:
                    await ctx.send(
                        f"✅ **Deobfuscate thành công!**\n"
                        f"📁 `{attachment.filename}` | 📏 {len(code)} ký tự\n"
                        f"```lua\n{code}\n```"
                    )
                else:
                    file_obj = discord.File(
                        io.BytesIO(code.encode('utf-8')), 
                        filename=f"deobfuscated_{attachment.filename.replace('.lua', '_clean.lua')}"
                    )
                    await ctx.send(
                        f"✅ **Deobfuscate thành công!**\n📁 `{attachment.filename}` | 📏 {len(code)} ký tự",
                        file=file_obj
                    )
        except Exception as e:
            await ctx.send(f"❌ Lỗi: `{e}`")

@prom_prefix.error
async def prom_prefix_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("🚫 Chỉ owner mới dùng được lệnh này!", delete_after=10)
    else:
        await ctx.send(f"❌ Lỗi: `{error}`", delete_after=10)

# ==================== LỆNH 2: /promdeobf (SLASH) ====================
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
            
            code = data.get("deobfuscated_code", "")
            if not code:
                await interaction.followup.send("❌ Không nhận được code từ API!", ephemeral=True)
                return
            
            if len(code) < 1900:
                await interaction.followup.send(
                    f"✅ **Deobfuscate thành công!**\n"
                    f"📁 `{file.filename}` | 📏 {len(code)} ký tự\n"
                    f"```lua\n{code}\n```"
                )
            else:
                file_obj = discord.File(
                    io.BytesIO(code.encode('utf-8')), 
                    filename=f"deobfuscated_{file.filename.replace('.lua', '_clean.lua')}"
                )
                await interaction.followup.send(
                    f"✅ **Deobfuscate thành công!**\n📁 `{file.filename}` | 📏 {len(code)} ký tự",
                    file=file_obj
                )
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

# Đăng ký slash command
bot.tree.add_command(promdeobf)

# ==================== CHẠY ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
