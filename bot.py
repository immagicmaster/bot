import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re
import time

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

# ⭐ API URL ẨN TRÊN RENDER (biến môi trường)
API_URL = os.environ["API_URL"]
MSEC_API_URL = os.environ["MSEC_API_URL"]
WAD_API_URL = os.environ["WAD_API_URL"]

# ⭐ MOONVEIL API
MOONVEIL_API_KEY = os.environ["MOONVEIL_API_KEY"]
MOONVEIL_API_URL = os.environ.get("MOONVEIL_API_URL", "https://moonveil.cc/api/obfuscate")

PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

# ⭐ ROLE ID ĐƯỢC PHÉP SỬ DỤNG LỆNH
ALLOWED_ROLE_ID = 1528772521753837781

# ==================== COOLDOWN MOONVEIL ====================
moonveil_cooldowns = {}  # {user_id: timestamp}
MOONVEIL_COOLDOWN_SEC = 30

# ==================== TÙY CHỌN OBFUSCATION MOONVEIL ====================
MOONVEIL_OBF_OPTIONS = {
    "cffDecomposeExpr": True,
    "cffEnable": True,
    "cffHoistLocals": True,
    "cffWrapBlocks": True,
    "mangleEnable": False,
    "mangleGlobals": False,
    "mangleNamedIndex": False,
    "mangleNumbers": True,
    "mangleSelfCalls": True,
    "mangleStrings": True,
    "prettify": True,
    "removeCompoundAssign": True,
    "removeIfExpr": True,
    "vmEnable": True,
    "vmWrapScript": True
}

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
    bot.tree.add_command(msecdeobf)
    bot.tree.add_command(moonveil)
    
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
        file_bytes = await file.read()
        try:
            script_content = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            script_content = file_bytes.decode('latin-1')
        
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
            
            clean_code = clean_wad_header(raw_obf)
            
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

# ==================== /msecdeobf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="msecdeobf", description="Deobfuscate Moonsec v3 Lua Script File")
@app_commands.describe(file="File .lua Hoặc .txt cần Deobfuscate")
async def msecdeobf(interaction: discord.Interaction, file: discord.Attachment):
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
        
        async with bot.session.post(MSEC_API_URL, data=form_data) as response:
            if response.status != 200:
                await interaction.followup.send(f"❌ API lỗi HTTP {response.status}", ephemeral=True)
                return
            
            data = await response.json()
            
            if not data.get("success", False):
                error_msg = data.get("error", "Không rõ lỗi")
                await interaction.followup.send(f"❌ API báo lỗi: {error_msg}", ephemeral=True)
                return
            
            raw_code = data.get("deobfuscated_code", "")
            if not raw_code:
                await interaction.followup.send("❌ Không nhận được code từ API!", ephemeral=True)
                return
            
            # ⭐ XÓA WATERMARK GIỐNG PROMDEOBF
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
        print(f"❌ Lỗi msecdeobf: {e}")
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@msecdeobf.error
async def msecdeobf_error(interaction: discord.Interaction, error):
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

# ==================== /moonveil ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="moonveil", description="Obfuscate Lua script bằng Moonveil API")
@app_commands.describe(file="File .lua hoặc .txt cần Obfuscate")
async def moonveil(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)
    
    user_id = interaction.user.id
    now = time.time()

    # --- Kiểm tra cooldown ---
    if user_id in moonveil_cooldowns:
        elapsed = now - moonveil_cooldowns[user_id]
        if elapsed < MOONVEIL_COOLDOWN_SEC:
            remain = int(MOONVEIL_COOLDOWN_SEC - elapsed)
            await interaction.followup.send(
                f"⏳ Bạn đang trong thời gian chờ. Vui lòng đợi **{remain}s** nữa.",
                ephemeral=True
            )
            return

    # --- Kiểm tra file ---
    if not file.filename.lower().endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return

    # Giới hạn 8MB
    if file.size > 8 * 1024 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn **8MB**.", ephemeral=True)
        return

    try:
        # --- Đọc nội dung file ---
        raw = await file.read()
        try:
            script = raw.decode("utf-8")
        except UnicodeDecodeError:
            await interaction.followup.send("❌ Không đọc được file. Vui lòng đảm bảo file là **UTF-8 text**.", ephemeral=True)
            return

        if not script.strip():
            await interaction.followup.send("❌ File rỗng.", ephemeral=True)
            return

        # --- Chuẩn bị payload ---
        payload = {
            "options": MOONVEIL_OBF_OPTIONS,
            "script": script
        }
        headers = {
            "Authorization": f"Bearer {MOONVEIL_API_KEY}",
            "Content-Type": "application/json"
        }

        # --- Gọi API ---
        async with bot.session.post(
            MOONVEIL_API_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:

            if resp.status != 200:
                err_body = await resp.text()
                err_snip = err_body[:1500] if len(err_body) > 1500 else err_body
                await interaction.followup.send(
                    f"❌ API trả về lỗi **`{resp.status}`**:\n```\n{err_snip}\n```",
                    ephemeral=True
                )
                return

            obfuscated = await resp.text()

        if not obfuscated or not obfuscated.strip():
            await interaction.followup.send("❌ API trả về kết quả rỗng.", ephemeral=True)
            return

        # --- Gửi file kết quả ---
        buffer = io.BytesIO(obfuscated.encode("utf-8"))
        out_name = f"obfuscated_{file.filename}"

        # Cập nhật cooldown
        moonveil_cooldowns[user_id] = time.time()

        await interaction.followup.send(
            f"✅ Obfuscate thành công `{file.filename}`!",
            file=discord.File(buffer, filename=out_name)
        )

    except aiohttp.ClientError as e:
        await interaction.followup.send(f"❌ Lỗi kết nối đến API: `{e}`", ephemeral=True)
    except Exception as e:
        print(f"❌ Lỗi moonveil: {e}")
        await interaction.followup.send(f"❌ Lỗi không xác định: `{e}`", ephemeral=True)

@moonveil.error
async def moonveil_error(interaction: discord.Interaction, error):
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
