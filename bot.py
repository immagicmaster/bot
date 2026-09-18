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
HOMOGLYPH_MAP = str.maketrans({
    'а': 'a', 'А': 'A',
    'е': 'e', 'Е': 'E',
    'і': 'i', 'І': 'I',
    'ѕ': 's', 'Ѕ': 'S',
    'о': 'o', 'О': 'O',
    'р': 'p', 'Р': 'P',
    'с': 'c', 'С': 'C',
    'у': 'y', 'У': 'Y',
    'х': 'x', 'Х': 'X',
    'κ': 'k', 'ϰ': 'k',
    'Ь': 'b', 'ь': 'b',
    'В': 'B', 'в': 'b',
    'Ԁ': 'd', 'ԁ': 'd', 'Ԃ': 'd', 'ԃ': 'd',
    'һ': 'h', 'ј': 'j', 'ǥ': 'g', 'ϲ': 'c', 'Ϲ': 'C',
    'Ο': 'O', 'ο': 'o',
    'Ԝ': 'W', 'ԝ': 'w',   # Ԝ/ԝ cyrillic trông giống W
})

# Các ký tự ẩn / zero-width có thể chèn vào watermark
INVISIBLE_CHARS = ('\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad')

# Watermark thay thế (Title_M)
TITLE_M = "--[[\n    This File Deobfuscate By ImMagic_Masterbot\n]]"

# Các câu watermark DÒNG ĐƠN (đã chuẩn hóa: thường, 1 khoảng trắng, không ký tự giả)
WATERMARK_SENTENCES = {
    "this file was deobfuscated by leakd",
    "this file was deobfuscated by leakd",   # khớp "---@source Тһіѕ Fіlе Ԝaѕ Dеоbfuѕсatеԁ Ву LеaκD"
}

# Các câu watermark nằm trong block --[[ ... ]] (đã chuẩn hóa)
# "Ѕourсе Сoԁе Dеоbfusсаtеԁ Ву LеаκD" -> normalize -> "source code deobfuscated by leakd"
WATERMARK_BLOCK_SENTENCES = {
    "source code deobfuscated by leakd",
}

# Regex bắt block comment --[[ ... ]] (nhiều dòng)
BLOCK_WATERMARK_RE = re.compile(r'--\[\[.*?\]\]', re.DOTALL)

def normalize_for_match(text: str) -> str:
    """Chuẩn hóa: đổi ký tự giả -> Latin, xóa ký tự ẩn, gom khoảng trắng, viết thường."""
    norm = text.translate(HOMOGLYPH_MAP)
    for ch in INVISIBLE_CHARS:
        norm = norm.replace(ch, '')
    return re.sub(r'\s+', ' ', norm).strip().lower()

def is_watermark_line(line: str) -> bool:
    """Chỉ trả True nếu CẢ DÒNG là watermark dòng đơn."""
    s = line.strip()
    if not s.startswith('--'):
        return False
    content = re.sub(r'^-+', '', s[2:]).strip()      # bỏ "--" / "---"
    content = re.sub(r'^@\w+\s+', '', content)        # bỏ "@source " / "@Source "...
    return normalize_for_match(content) in WATERMARK_SENTENCES

def replace_block_watermarks(code: str) -> tuple:
    """
    Tìm các block --[[ ... ]] chứa watermark LeakD (dùng chữ Cyrillic/Greek giả)
    và URL leakd.vercel.app -> thay toàn bộ block bằng TITLE_M.
    Trả về (code_mới, số_block_đã_thay).
    """
    replaced_count = 0

    def _replacer(match):
        nonlocal replaced_count
        block = match.group(0)
        norm = normalize_for_match(block)

        # Phải chứa URL leakd.vercel.app VÀ ít nhất 1 câu watermark trong block
        if "leakd.vercel.app" in norm and any(s in norm for s in WATERMARK_BLOCK_SENTENCES):
            replaced_count += 1
            print(f"🔄 Đã thay block watermark bằng Title_M (block #{replaced_count})")
            return TITLE_M

        return block  # không phải watermark -> giữ nguyên

    new_code = BLOCK_WATERMARK_RE.sub(_replacer, code)
    return new_code, replaced_count

def remove_watermarks(code: str) -> str:
    # BƯỚC 1 — block --[[ ... ]] chứa watermark -> thay bằng Title_M
    code, block_replaced = replace_block_watermarks(code)

    # BƯỚC 2 — xử lý từng dòng
    lines = code.splitlines()
    cleaned = []
    removed_count = 0
    leak_url = "discord.gg/qteAQmfJmP"

    # Nếu block ở Bước 1 đã thay Title_M rồi thì không chèn thêm nữa
    title_inserted = block_replaced > 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        replaced_title = False
        removed = False

        # 1. URL leak cũ
        if leak_url in line:
            removed = True

        # 2. URL leakd.vercel.app
        elif re.search(r'leakd\.vercel\.app', line, re.IGNORECASE):
            removed = True

        # 3. Câu watermark dòng đơn -> THAY bằng Title_M (chỉ chèn 1 lần duy nhất)
        elif is_watermark_line(line):
            removed = True
            replaced_title = True
            if not title_inserted:
                cleaned.append(TITLE_M)
                title_inserted = True
                print(f"🔄 Đã thay watermark dòng {i+1} bằng Title_M")

        # 4. discord.gg/... kèm từ khóa obfu/leak
        elif re.search(r'discord\.gg/\w+', line, re.IGNORECASE) and (
            'obfu' in line.lower() or 'leak' in line.lower()
        ):
            removed = True

        if removed:
            removed_count += 1
            if not replaced_title:
                print(f"🗑️ Đã xóa dòng {i+1}: {stripped[:80]}...")
            continue

        cleaned.append(line)

    print(f"📊 Đã thay {block_replaced} block + Title_M, xóa {removed_count} dòng watermark")
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

            # remove_watermarks tự động thay block + dòng watermark bằng Title_M
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
                error_msg = data.get("error", "Không rõ lỗi")
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

            await interaction.followup.send(embed=embed, file=file_obj)

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

            # remove_watermarks tự động thay block + dòng watermark bằng Title_M
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
