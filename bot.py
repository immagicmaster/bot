import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re
import subprocess
import shutil
import tempfile

# ==================== THƯ VIỆN LUA/LUAU ====================
# Thử import lupa (Python Lua bindings)
try:
    import lupa
    from lupa import LuaRuntime
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    print("⚠️ Thư viện 'lupa' chưa được cài đặt. Một số tính năng Lua có thể bị hạn chế.")

# Kiểm tra lune CLI có sẵn không
LUNE_AVAILABLE = shutil.which("lune") is not None
if LUNE_AVAILABLE:
    print("✅ Lune CLI đã sẵn sàng")
else:
    print("⚠️ Lune CLI không tìm thấy trong PATH. Vui lòng cài đặt: cargo install lune")

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

# ⭐ API URL ẨN TRÊN RENDER (biến môi trường)
API_URL = os.environ["API_URL"]
MSEC_API_URL = os.environ["MSEC_API_URL"]
WAD_API_URL = os.environ["WAD_API_URL"]

PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

# ⭐ ROLE ID ĐƯỢC PHÉP SỬ DỤNG LỆNH
ALLOWED_ROLE_ID = 1528772521753837781

# ⭐ ĐƯỜNG DẪN MFire.luau
MFIRE_PATH = "/Env/MFire.luau"

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
    bot.tree.add_command(logger_cmd)
    
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
    print(f"📁 MFire path: {MFIRE_PATH}")
    print(f"🔧 Lune available: {LUNE_AVAILABLE}")
    print(f"🔧 Lupa available: {LUPA_AVAILABLE}")

# ⭐ HÀM KIỂM TRA QUYỀN
def is_owner_or_allowed_role(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        if any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
            return True
    return False

def is_owner_only(interaction: discord.Interaction) -> bool:
    return interaction.user.id == OWNER_ID

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

# ==================== /logger (OWNER ONLY) ====================
@app_commands.check(is_owner_only)
@app_commands.command(name="logger", description="[OWNER ONLY] Thực thi MFire.luau với file đính kèm")
@app_commands.describe(
    file="File .lua hoặc .txt để xử lý bằng MFire",
    args="Tham số bổ sung truyền vào (tùy chọn)"
)
async def logger_cmd(interaction: discord.Interaction, file: discord.Attachment, args: str = ""):
    await interaction.response.defer(thinking=True)
    
    # Kiểm tra file
    if not file.filename.endswith(('.lua', '.txt', '.luau')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua`, `.luau` hoặc `.txt`!", ephemeral=True)
        return
    
    if file.size > 5 * 1024 * 1024:
        await interaction.followup.send("⚠️ File quá lớn! Giới hạn 5MB.", ephemeral=True)
        return
    
    # Kiểm tra MFire.luau tồn tại
    if not os.path.exists(MFIRE_PATH):
        await interaction.followup.send(
            f"❌ Không tìm thấy `{MFIRE_PATH}` trên server!\n"
            f"📁 Vui lòng đảm bảo file MFire.luau đã được đặt đúng đường dẫn.",
            ephemeral=True
        )
        return
    
    try:
        # Đọc file người dùng gửi
        user_file_bytes = await file.read()
        try:
            user_code = user_file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            user_code = user_file_bytes.decode('latin-1')
        
        # Tạo thư mục tạm để xử lý
        with tempfile.TemporaryDirectory() as tmpdir:
            # Lưu file người dùng vào thư mục tạm
            user_file_path = os.path.join(tmpdir, file.filename)
            with open(user_file_path, 'w', encoding='utf-8') as f:
                f.write(user_code)
            
            # Đọc source MFire.luau
            with open(MFIRE_PATH, 'r', encoding='utf-8') as f:
                mfire_source = f.read()
            
            # Copy MFire.luau vào thư mục tạm để xử lý (tránh ghi đè file gốc)
            mfire_tmp_path = os.path.join(tmpdir, "MFire.luau")
            with open(mfire_tmp_path, 'w', encoding='utf-8') as f:
                f.write(mfire_source)
            
            result_code = ""
            execution_method = ""
            
            # ==================== ƯU TIÊN 1: LUNE CLI ====================
            if LUNE_AVAILABLE:
                execution_method = "lune"
                
                # Chuẩn bị command: lune run MFire.luau [args] [user_file]
                cmd = ["lune", "run", mfire_tmp_path]
                
                # Thêm args nếu có
                if args.strip():
                    cmd.extend(args.strip().split())
                
                # Truyền đường dẫn file người dùng như tham số cuối
                cmd.append(user_file_path)
                
                # Thiết lập environment để MFire có thể truy cập đường dẫn file
                env = os.environ.copy()
                env["INPUT_FILE"] = user_file_path
                env["OUTPUT_DIR"] = tmpdir
                
                # Chạy lune
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                    env=env
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
                
                if process.returncode != 0:
                    err_msg = stderr.decode('utf-8', errors='replace')[:1500]
                    await interaction.followup.send(
                        f"❌ Lune thực thi thất bại (exit code {process.returncode}):\n```\n{err_msg}\n```",
                        ephemeral=True
                    )
                    return
                
                # Lấy output
                result_output = stdout.decode('utf-8', errors='replace')
                
                # Kiểm tra xem MFire có tạo file output không
                output_file = os.path.join(tmpdir, "output.lua")
                if os.path.exists(output_file):
                    with open(output_file, 'r', encoding='utf-8') as f:
                        result_code = f.read()
                else:
                    # Nếu không có file output, dùng stdout làm kết quả
                    result_code = result_output
            
            # ==================== FALLBACK 2: LUPA (Python Lua) ====================
            elif LUPA_AVAILABLE:
                execution_method = "lupa"
                
                lua = LuaRuntime(unpack_returned_tuples=True)
                
                # Thiết lập globals để script có thể truy cập file người dùng
                lua.globals().INPUT_FILE = user_file_path
                lua.globals().INPUT_CODE = user_code
                lua.globals().OUTPUT_DIR = tmpdir
                
                # Thực thi MFire source
                result = lua.execute(mfire_source)
                
                # Kiểm tra output file
                output_file = os.path.join(tmpdir, "output.lua")
                if os.path.exists(output_file):
                    with open(output_file, 'r', encoding='utf-8') as f:
                        result_code = f.read()
                elif result and isinstance(result, str):
                    result_code = result
                else:
                    result_code = str(result) if result else ""
            
            # ==================== FALLBACK 3: KHÔNG CÓ THƯ VIỆN ====================
            else:
                await interaction.followup.send(
                    "❌ Không có runtime Lua/Luau nào khả dụng!\n"
                    "📦 Vui lòng cài đặt một trong các thư viện sau:\n"
                    "• `lune` (CLI): `cargo install lune`\n"
                    "• `lupa` (Python): `pip install lupa`",
                    ephemeral=True
                )
                return
            
            # Kiểm tra kết quả
            if not result_code or not result_code.strip():
                await interaction.followup.send(
                    "⚠️ Thực thi thành công nhưng không có output!\n"
                    f"🔧 Phương thức: `{execution_method}`",
                    ephemeral=True
                )
                return
            
            # Tạo tên file output
            base_name = file.filename.rsplit('.', 1)[0]
            output_name = f"{base_name}_logged.lua"
            
            # Tạo file Discord
            file_obj = discord.File(
                io.BytesIO(result_code.encode('utf-8')),
                filename=output_name
            )
            
            # Gửi kết quả
            embed = discord.Embed(
                title="✅ Logger Executed",
                color=0x00ff00
            )
            embed.add_field(name="📁 Input", value=f"`{file.filename}`", inline=True)
            embed.add_field(name="📤 Output", value=f"`{output_name}`", inline=True)
            embed.add_field(name="🔧 Engine", value=f"`{execution_method}`", inline=True)
            embed.add_field(name="📜 MFire", value=f"`{MFIRE_PATH}`", inline=False)
            
            if args.strip():
                embed.add_field(name="⚙️ Args", value=f"`{args}`", inline=False)
            
            await interaction.followup.send(embed=embed, file=file_obj)
            
    except asyncio.TimeoutError:
        await interaction.followup.send("⏱️ Thực thi quá thời gian (timeout 60s)!", ephemeral=True)
    except Exception as e:
        print(f"❌ Lỗi logger: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@logger_cmd.error
async def logger_cmd_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "🚫 Lệnh này chỉ dành cho **Owner**!",
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
