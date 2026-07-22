import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
API_URL = "https://leakd.up.railway.app/prometheus"
WAD_API_URL = "https://wearedevs.net/api/obfuscate"
PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

# ⭐ ROLE ID ĐƯỢC PHÉP SỬ DỤNG LỆNH
ALLOWED_ROLE_ID = 1528772521753837781

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

# ==================== XÓA WATERMARK PROMETHEUS ====================
def remove_watermarks(code: str) -> str:
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

# ==================== XÓA HEADER WAD ====================
def clean_wad_header(code: str) -> str:
    """
    Xóa URL trong header comment của WeAreDevs Obfuscator.
    --[[ v1.0.0 https://wearedevs.net/obfuscator ]] → --[[ v1.0.0 ]]
    """
    cleaned = re.sub(
        r'(--\[\[.*?)\s+https?://[^\]]+(\s*\]\])',
        r'\1\2',
        code,
        count=1
    )
    return cleaned

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, owner_id=OWNER_ID)

@bot.event
async def setup_hook():
    bot.session = aiohttp.ClientSession()
    bot.tree.add_command(promdeobf)
    bot.tree.add_command(wadobf)
    
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

# ⭐ HÀM KIỂM TRA QUYỀN
def is_owner_or_allowed_role(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        if any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
            return True
    return False

# ==================== /promdeobf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="promdeobf", description="Deobfuscate Prometheus Lua Script File")
@app_commands.describe(file="File .lua Hoặc .txt cần Deobfuscate")
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
        await interaction.response.send_message(
            "🚫 Bạn không có quyền sử dụng lệnh này! Chỉ Owner hoặc người có role <@&1528772521753837781> mới được dùng.",
            ephemeral=True
        )
    else:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Lỗi: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Lỗi: `{error}`", ephemeral=True)

# ==================== /wadobf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="wadobf", description="Obfuscate Lua script bằng WeAreDevs API")
@app_commands.describe(file="File .lua hoặc .txt cần Obfuscate")
async def wadobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)
    
    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return
    
    if file.size > 5 * 1024 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn 5MB.", ephemeral=True)
        return
    
    try:
        # Đọc nội dung file dạng text
        file_bytes = await file.read()
        try:
            script_content = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            script_content = file_bytes.decode('latin-1')
        
        # Gửi đến WeAreDevs API
        form_data = aiohttp.FormData()
        form_data.add_field('script', script_content)
        
        async with bot.session.post(WAD_API_URL, data=form_data) as response:
            if response.status != 200:
                text = await response.text()
                print(f"❌ WAD API {response.status}: {text[:300]}")
                await interaction.followup.send(f"❌ WAD API lỗi HTTP {response.status}", ephemeral=True)
                return
            
            data = await response.json()
            
            if not data.get("success", False):
                await interaction.followup.send(f"❌ WAD API báo lỗi: {data.get('error', 'Không rõ')}", ephemeral=True)
                return
            
            raw_obf = data.get("obfuscated", "")
            if not raw_obf:
                await interaction.followup.send("❌ Không nhận được code từ WAD API!", ephemeral=True)
                return
            
            # ⭐ XÓA URL TRONG HEADER: --[[ v1.0.0 https://wearedevs.net/obfuscator ]] → --[[ v1.0.0 ]]
            clean_code = clean_wad_header(raw_obf)
            
            # Tên file output
            output_name = file.filename.replace('.lua', '_obf.lua')
            if not output_name.endswith('.lua'):
                output_name += '.lua'
            
            file_obj = discord.File(
                io.BytesIO(clean_code.encode('utf-8')),
                filename=output_name
            )
            
            await interaction.followup.send(
                f"✅ Obfuscated Success\n📝 `{output_name}`",
                file=file_obj
            )
    
    except Exception as e:
        print(f"❌ Lỗi wadobf: {e}")
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@wadobf.error
async def wadobf_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "🚫 Bạn không có quyền sử dụng lệnh này! Chỉ Owner hoặc người có role <@&1528772521753837781> mới được dùng.",
            ephemeral=True
        )
    else:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Lỗi: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Lỗi: `{error}`", ephemeral=True)

# ==================== CHẠY ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
