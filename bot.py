import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import re
from datetime import datetime

# ==================== CẤU HÌNH ====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

API_URL = os.environ["API_URL"]
MSEC_API_URL = os.environ["MSEC_API_URL"]
WAD_API_URL = os.environ["WAD_API_URL"]

PORT = int(os.environ.get("PORT", 10000))
GUILD_ID = os.environ.get("GUILD_ID")

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
# Bảng chuyển ký tự Cyrillic/Greek trông giống Latin -> Latin thật
# FIX QUAN TRỌNG: 'В' (Cyrillic) trông giống chữ B -> map sang 'B' (bản trước bị map sang 'V'
# nên "By" thành "Vy", regex không bao giờ khớp). Bổ sung thêm 'ԁ' (U+0501) và các chữ "d" cyrillic.
HOMOGLYPH_MAP = str.maketrans({
    'а': 'a', 'А': 'A',   # а cyrillic
    'е': 'e', 'Е': 'E',   # е cyrillic
    'і': 'i', 'І': 'I',   # і cyrillic
    'ѕ': 's', 'Ѕ': 'S',   # ѕ cyrillic
    'о': 'o', 'О': 'O',   # о cyrillic
    'р': 'p', 'Р': 'P',   # р cyrillic
    'с': 'c', 'С': 'C',   # с cyrillic
    'у': 'y', 'У': 'Y',   # у cyrillic
    'х': 'x', 'Х': 'X',   # х cyrillic
    'κ': 'k', 'ϰ': 'k',   # κ/ϰ greek -> k
    'Ь': 'b', 'ь': 'b',   # Ь/ь cyrillic -> b
    'В': 'B', 'в': 'b',   # В/в cyrillic -> B/b (TRÔNG GIỐNG B, không phải V)
    'Ԁ': 'd', 'ԁ': 'd', 'Ԃ': 'd', 'ԃ': 'd',  # các chữ "d" cyrillic
    'һ': 'h', 'ј': 'j', 'ǥ': 'g', 'ϲ': 'c', 'Ϲ': 'C',
    'Ο': 'O', 'ο': 'o',
})

# Các ký tự ẩn / zero-width có thể chèn vào watermark
INVISIBLE_CHARS = ('\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad')

# Danh sách câu watermark (đã chuẩn hóa: thường, 1 khoảng trắng, không ký tự giả)
# Mọi biến thể chữ giả đều chuẩn hóa về đúng câu này -> so khớp NGUYÊN DÒNG
WATERMARK_SENTENCES = {
    "this file was deobfuscated by leakd",
}

def normalize_for_match(text: str) -> str:
    """Chuẩn hóa: đổi ký tự giả -> Latin, xóa ký tự ẩn, gom khoảng trắng, viết thường."""
    norm = text.translate(HOMOGLYPH_MAP)
    for ch in INVISIBLE_CHARS:
        norm = norm.replace(ch, '')
    return re.sub(r'\s+', ' ', norm).strip().lower()

def is_watermark_line(line: str) -> bool:
    """Chỉ trả True nếu CẢ DÒNG là watermark. Dòng bình thường -> False (không xóa)."""
    s = line.strip()
    if not s.startswith('--'):          # không phải comment -> không phải watermark dạng này
        return False
    content = re.sub(r'^-+', '', s[2:]).strip()   # bỏ "--" (hoặc "---") ở đầu
    return normalize_for_match(content) in WATERMARK_SENTENCES

def remove_watermarks(code: str) -> str:
    lines = code.splitlines()
    cleaned = []
    removed_count = 0
    leak_url = "discord.gg/qteAQmfJmP"

    for i, line in enumerate(lines):
        stripped = line.strip()
        removed = False

        # 1. URL leak cũ
        if leak_url in line:
            removed = True

        # 2. URL leakd.vercel.app (mới)
        elif re.search(r'leakd\.vercel\.app', line, re.IGNORECASE):
            removed = True

        # 3. Câu "This File Was Deobfuscated By LeakD" - LOGIC MỚI:
        #    so khớp NGUYÊN DÒNG (đúng thì xóa, sai/không phải comment thì giữ)
        elif is_watermark_line(line):
            removed = True

        # 4. Regex cũ: discord.gg/... kèm từ khóa obfu/leak
        elif re.search(r'discord\.gg/\w+', line, re.IGNORECASE) and (
            'obfu' in line.lower() or 'leak' in line.lower()
        ):
            removed = True

        if removed:
            removed_count += 1
            print(f"🗑️ Đã xóa dòng {i+1}: {stripped[:80]}...")
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

# ==================== HÀM TẠO EMBED ====================
def create_result_embed(obfuscator_name: str, clean_code: str, is_obfuscation: bool = False) -> discord.Embed:
    size_bytes = len(clean_code.encode('utf-8'))
    size_kb = size_bytes / 1024
    
    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")
    
    if is_obfuscation:
        title = "<:verify:1534952434890182707> **Obfuscation successful**"
        obf_icon = "<:wad:1534952520345194658>"
    else:
        title = "<:verify:1534952434890182707> **Deobfuscation successful!**"
        obf_icon = "<:Code:1534952344414847077>"
    
    embed = discord.Embed(
        description=f"{title}\n\n"
                    f"{obf_icon} **Obfuscator:** {obfuscator_name}\n"
                    f"<:Code:1534952344414847077> **Size:** `{size_kb:.2f} KB`",
        color=discord.Color.purple()
    )
    
    embed.set_footer(text=f"MagicDumper • {date_str} | Hôm nay lúc {time_str}")
    
    return embed

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

# ==================== KIỂM TRA QUYỀN ====================
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
@app_commands.describe(file="File .lua Or .txt Need Deobfuscate")
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
            
            embed = create_result_embed("Prometheus", clean_code, is_obfuscation=False)
            
            await interaction.followup.send(embed=embed, file=file_obj)
    
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        await interaction.followup.send(f"❌ Lỗi: `{e}`", ephemeral=True)

@promdeobf.error
async def promdeobf_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "🚫 You are not authorized to use it.",
            ephemeral=True
        )
    else:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Lỗi: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Lỗi: `{error}`", ephemeral=True)
# ==================== /wadobf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(
    name="wadobf",
    description="Obfuscated Lua Script Using WeAreDevs API"
)
@app_commands.describe(file="File .lua Or .txt Need Obfuscate")
async def wadobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    if not file.filename.lower().endswith(('.lua', '.txt')):
        await interaction.followup.send(
            "⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!",
            ephemeral=True
        )
        return

    if file.size > 5 * 1024 * 1024:
        await interaction.followup.send(
            "⚠️ File quá lớn! Giới hạn 5MB.",
            ephemeral=True
        )
        return

    try:
        file_bytes = await file.read()

        try:
            script_content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            script_content = file_bytes.decode("latin-1")

        
        payload = {
            "script": script_content
        }

        async with bot.session.post(
            WAD_API_URL,
            json=payload
        ) as response:

            response_text = await response.text()

            if response.status != 200:
                await interaction.followup.send(
                    f"❌ WAD API lỗi HTTP `{response.status}`\n"
                    f"```text\n{response_text[:1000]}\n```",
                    ephemeral=True
                )
                return

            try:
                data = await response.json()
            except Exception:
                print("❌ WAD API trả về dữ liệu không phải JSON")

                await interaction.followup.send(
                    "❌ WAD API trả về response không hợp lệ.",
                    ephemeral=True
                )
                return

            if not data.get("success", False):
                error_msg = data.get(
                    "error",
                    "Không rõ lỗi"
                )

                await interaction.followup.send(
                    f"❌ WAD API báo lỗi: `{error_msg}`",
                    ephemeral=True
                )
                return

            raw_obf = data.get("obfuscated", "")

            if not raw_obf:
                await interaction.followup.send(
                    "❌ Không nhận được code từ WAD API!",
                    ephemeral=True
                )
                return

            clean_code = clean_wad_header(raw_obf)

            output_name = file.filename

            if output_name.lower().endswith(".lua"):
                output_name = output_name[:-4] + "_obf.lua"
            elif output_name.lower().endswith(".txt"):
                output_name = output_name[:-4] + "_obf.lua"
            else:
                output_name += "_obf.lua"

            file_obj = discord.File(
                io.BytesIO(clean_code.encode("utf-8")),
                filename=output_name
            )

            embed = create_result_embed(
                "WeAreDev",
                clean_code,
                is_obfuscation=True
            )

            await interaction.followup.send(
                embed=embed,
                file=file_obj
            )

    except aiohttp.ClientError as e:
        print(f"❌ WAD HTTP Client Error: {e}")

        await interaction.followup.send(
            f"❌ Không kết nối được WAD API:\n`{e}`",
            ephemeral=True
        )

    except Exception as e:
        print(f"❌ Lỗi wadobf: {e}")

        await interaction.followup.send(
            f"❌ Lỗi: `{e}`",
            ephemeral=True
    )
# ==================== /msecdeobf ====================
@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="msecdeobf", description="Deobfuscate Moonsec v3 Lua Script File")
@app_commands.describe(file="File Only .lua Or .txt File Need Deobfuscate")
async def msecdeobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)
    
    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Only Work file `.lua` Or `.txt`!", ephemeral=True)
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
            "🚫 You are not authorized to use it.",
            ephemeral=True
        )
    else:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌  Error : `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error : `{error}`", ephemeral=True)

# ==================== MAIN ====================
async def main():
    await start_web_server()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
