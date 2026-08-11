import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re
import zlib
import random
import string

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

API_URL = os.environ["API_URL"]
MSEC_API_URL = os.environ["MSEC_API_URL"]
WAD_API_URL = os.environ["WAD_API_URL"]

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

# ==================== OBF HELPERS ====================
def rand_obf_name(length: int = 16) -> str:
    """Tạo tên biến ngẫu nhiên khó đọc."""
    chars = string.ascii_letters + string.digits
    return '_' + ''.join(random.choice(chars) for _ in range(length))

def b32hex_encode(data: bytes) -> str:
    """Encode bytes sang base32hex (RFC 4648) không padding."""
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUV'
    bits = ''.join(format(b, '08b') for b in data)
    # Pad bits to multiple of 5
    while len(bits) % 5 != 0:
        bits += '0'
    result = ''
    for i in range(0, len(bits), 5):
        chunk = bits[i:i+5]
        val = int(chunk, 2)
        result += alphabet[val]
    return result

def generate_obfuscated_lua(source_code: str, vm: bool) -> str:
    """Tạo code Lua đã obfuscate: zlib -> b32hex -> loader Lua."""
    if not source_code:
        raise ValueError("Source code is empty")

    # 1. Nén zlib level 9
    compressed = zlib.compress(source_code.encode('utf-8'), level=9)
    # 2. Encode base32hex
    encoded = b32hex_encode(compressed)

    # 3. Tạo tên biến obfuscate
    names = {k: rand_obf_name() for k in [
        'enc', 'dec', 'zl', 'arg', 'tbl', 'i', 'c', 'b', 'r', 'o', 'n', 'j', 'k', 'm'
    ]}

    # 4. Hàm giải mã base32hex trong Lua (compact, obfuscated tên biến)
    decoder_lua = '''function({arg})
local {tbl}="0123456789ABCDEFGHIJKLMNOPQRSTUV"
local {r}={{ }}
for {i}=1,#{arg} do
local {c}={arg}:sub({i},{i})
if {c}~=" " and {c}~="\\n" and {c}~="\\r" and {c}~="=" then
for {j}=1,32 do
if {tbl}:sub({j},{j})=={c} then {r}[#{r}+1]={j}-1 break end
end
end
end
local {o}={{ }}
local {n}=math.floor(#{r}*5/8)
for {i}=1,#{r},8 do
local {b}=0
for {k}=0,7 do
{b}={b}*32+({r}[{i}+{k}] or 0)
end
local {m}={{math.floor({b}/4294967296)%256,math.floor({b}/16777216)%256,math.floor({b}/65536)%256,math.floor({b}/256)%256,{b}%256}}
for {k}=1,5 do
if #{o}<{n} then {o}[#{o}+1]=string.char({m}[{k}]) end
end
end
return table.concat({o})
end'''.format(**names)

    # 5. Hàm giải nén zlib trong Lua
    zlib_lua = 'function(c) return zlib.decompress(c) end'

    # 6. Biến chứa encoded string & decoder
    enc_var = names['enc']
    dec_var = names['dec']
    zl_var  = names['zl']

    header = '-- This File Was Protected By MFire Basic\n'

    if vm:
        # VM = True: return(function(...) local v1={...} local v2={...} end){...}
        body = f'''{header}return (function(...)
    local {enc_var}={{"{encoded}"}}
    local {dec_var}={{{decoder_lua}}}
    local {zl_var}={{{zlib_lua}}}
    loadstring({zl_var}[1]({dec_var}[1]({enc_var}[1])))()
end){{...}}'''
    else:
        # VM = False: local v1={...} local v2={...}
        body = f'''{header}local {enc_var}={{"{encoded}"}}
local {dec_var}={{{decoder_lua}}}
local {zl_var}={{{zlib_lua}}}
loadstring({zl_var}[1]({dec_var}[1]({enc_var}[1])))()'''

    return body

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
    bot.tree.add_command(obf) 
    
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

# ==================== /obf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="obf", description="Obfuscate Lua script với zlib + base32hex + VM option")
@app_commands.describe(
    file="File .lua hoặc .txt cần Obfuscate",
    vm="Bật VM wrapper (True/False), mặc định False"
)
async def obf(interaction: discord.Interaction, file: discord.Attachment, vm: bool = False):
    await interaction.response.defer(thinking=True)
    
    # Chỉ nhận .lua hoặc .txt
    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return
    
    # Giới hạn 500KB
    if file.size > 500 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn 500KB.", ephemeral=True)
        return
    
    try:
        file_bytes = await file.read()
        try:
            script_content = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            script_content = file_bytes.decode('latin-1')
        
        # Tạo code obfuscated
        obfuscated_code = generate_obfuscated_lua(script_content, vm)
        
        # Tạo file obfuscated.lua.txt
        file_obj = discord.File(
            io.BytesIO(obfuscated_code.encode('utf-8')),
            filename="obfuscated.lua.txt"
        )
        
        await interaction.followup.send(file=file_obj)
    
    except Exception as e:
        print(f"❌ Lỗi obf: {e}")
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@obf.error
async def obf_error(interaction: discord.Interaction, error):
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
            
            embed = create_result_embed("MoonSec", clean_code, is_obfuscation=False)
            
            await interaction.followup.send(embed=embed, file=file_obj)
    
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

# ==================== CHẠY ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

