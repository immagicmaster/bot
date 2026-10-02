import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import io
import asyncio
import random
import string
import re
from datetime import datetime

DISCORD_TOKEN = (os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN", "").strip())
if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN or TOKEN environment variable")

OWNER_ID = int(os.environ.get("OWNER_ID"))

API_URL = os.environ.get("API_URL")
MSEC_API_URL = os.environ.get("MSEC_API_URL")
WAD_API_URL = os.environ.get("WAD_API_URL")

PORT = int(os.environ.get("PORT", "10000"))
GUILD_ID = os.environ.get("GUILD_ID").strip()

ALLOWED_ROLE_ID = 1528772521753837781
MAX_FILE_SIZE = 1 * 1024 * 1024


async def handle(request):
    return web.Response(text="🤖 Bot is alive!")


app = web.Application()
app.router.add_get("/", handle)
app.router.add_get("/health", handle)


async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner


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
    'Ԝ': 'W', 'ԝ': 'w',
})

INVISIBLE_CHARS = ('\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad')

TITLE_M = "--[[\n    This File Deobfuscate By ImMagic_Masterbot\n]]"

BLOCK_WATERMARK_RE = re.compile(r'--\[\[.*?\]\]', re.DOTALL)

WATERMARK_KEYWORD = "leakd"

LEAK_URLS = (
    "discord.gg/qteaqmfjmp",
    "discord.gg/awghnh7z7t",
    "https://leakd.vercel.app",
)


def normalize_for_match(text: str) -> str:
    norm = text.translate(HOMOGLYPH_MAP)
    for ch in INVISIBLE_CHARS:
        norm = norm.replace(ch, '')
    return re.sub(r'\s+', ' ', norm).strip().lower()


def is_watermark_line(line: str) -> bool:
    norm = normalize_for_match(line)
    if WATERMARK_KEYWORD in norm:
        return True
    return any(url in norm for url in LEAK_URLS)


def replace_block_watermarks(code: str) -> tuple:
    replaced_count = 0

    def _replacer(match):
        nonlocal replaced_count
        block = match.group(0)
        norm = normalize_for_match(block)

        if WATERMARK_KEYWORD in norm or any(url in norm for url in LEAK_URLS):
            replaced_count += 1
            return TITLE_M

        return block

    new_code = BLOCK_WATERMARK_RE.sub(_replacer, code)
    return new_code, replaced_count


def remove_watermarks(code: str) -> str:
    code, block_replaced = replace_block_watermarks(code)

    lines = code.splitlines()
    cleaned = []
    removed_count = 0
    title_inserted = block_replaced > 0

    for i, line in enumerate(lines):
        if is_watermark_line(line):
            removed_count += 1
            if not title_inserted:
                cleaned.append(TITLE_M)
                title_inserted = True
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def clean_wad_header(code: str) -> str:
    cleaned = re.sub(
        r'(--\[\[.*?)\s+https?://[^\]]+(\s*\]\])',
        r'\1\2',
        code,
        count=1
    )
    return cleaned


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


B91_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "!#$%&()*+,./:;<=>?@[]^_`{|}~\""
)


def lua_str(s: str) -> str:
    return (
        '"'
        + s.replace("\\", "\\\\").replace('"', '\\"')
        + '"'
    )


def b91_encode(data: bytes) -> str:
    b = 0
    n = 0
    out = []

    for byte in data:
        b |= byte << n
        n += 8

        if n > 13:
            v = b & 8191

            if v > 88:
                b >>= 13
                n -= 13
            else:
                v = b & 16383
                b >>= 14
                n -= 14

            out.append(B91_ALPHABET[v % 91])
            out.append(B91_ALPHABET[v // 91])

    if n:
        out.append(B91_ALPHABET[b % 91])

        if n > 7 or b > 90:
            out.append(B91_ALPHABET[b // 91])

    return "".join(out)


def build_encrypt_string(data: bytes) -> str:
    v1 = lua_str(b91_encode(data))

    v2 = ",".join(
        lua_str(c)
        for c in B91_ALPHABET
    )

    return f'''--[[ This File Was Protected By MFObfuscator EncryptString ]]
return(function(...)
    local v1={v1}
    local v2={{{v2}}}

    local v3=function(s,A)
        local decode={{}}

        for i=1,#A do
            decode[A[i]]=i-1
        end

        local b,n,out,v=0,0,{{}},-1

        for i=1,#s do
            local d=decode[s:sub(i,i)]

            if d then
                if v<0 then
                    v=d
                else
                    v=v+d*91
                    b=b+v*2^n

                    if v%8192>88 then
                        n=n+13
                    else
                        n=n+14
                    end

                    while n>7 do
                        out[#out+1]=string.char(b%256)
                        b=math.floor(b/256)
                        n=n-8
                    end

                    v=-1
                end
            end
        end

        if v>=0 then
            out[#out+1]=string.char(
                (b+v*2^n)%256
            )
        end

        return table.concat(out)
    end

    local ls=loadstring or load
    return ls(v3(v1,v2))(...)
end)(...)'''


def lz_tokens(
    data: bytes,
    window=4096,
    min_len=3,
    max_len=18
):
    n = len(data)
    pos_map = {}
    tokens = []
    i = 0

    while i < n:
        best_len = 0
        best_dist = 0

        if i + min_len <= n:
            candidates = pos_map.get(
                data[i:i + min_len],
                ()
            )

            for j in candidates:
                if i - j > window:
                    continue

                length = min_len

                while (
                    length < max_len
                    and i + length < n
                    and j + length < n
                    and data[j + length] == data[i + length]
                ):
                    length += 1

                if length > best_len:
                    best_len = length
                    best_dist = i - j

                    if length == max_len:
                        break

        if best_len >= min_len:
            tokens.append(
                (
                    1,
                    best_dist,
                    best_len
                )
            )

            end = min(
                i + best_len,
                n - 2
            )

            for p in range(i, end):
                pos_map.setdefault(
                    data[p:p + 3],
                    []
                ).append(p)

            i += best_len

        else:
            tokens.append(
                (
                    0,
                    data[i]
                )
            )

            if i + 3 <= n:
                pos_map.setdefault(
                    data[i:i + 3],
                    []
                ).append(i)

            i += 1

        for key in list(pos_map):
            if len(pos_map[key]) > 128:
                del pos_map[key][:-128]

    return tokens


def build_compress(data: bytes) -> str:
    flat = []

    for token in lz_tokens(data):
        flat.extend(token)

    v1 = ",".join(
        map(str, flat)
    )

    return f'''--[[ This File Was Protected By MFObfuscator Compress ]]
return(function(...)
    local v1={{{v1}}}
    local v2={{4096,18}}

    local v3=function(t,cfg)
        local out={{}}
        local i=1

        while i<=#t do
            if t[i]==0 then
                out[#out+1]=string.char(t[i+1])
                i=i+2
            else
                local dist,len=t[i+1],t[i+2]
                local pos=#out-dist+1

                for k=0,len-1 do
                    out[#out+1]=out[pos+k]
                end

                i=i+3
            end
        end

        return table.concat(out)
    end

    local ls=loadstring or load
    return ls(v3(v1,v2))(...)
end)(...)'''


KEY_CHARS = (
    string.ascii_letters
    + string.digits
    + "!@#$%^&*()-_=+[]{};:,.<>/?"
)


def gen_expr(
    target: int,
    depth=0
) -> str:

    if depth >= 4 or target < 50:
        return f"{target:05d}"

    m = random.randint(7, 97)

    q, r = divmod(
        target,
        m
    )

    return (
        f"({gen_expr(q, depth + 1)}*"
        f"{gen_expr(m, depth + 1)}+"
        f"{gen_expr(r, depth + 1)})"
    )


def build_xor(data: bytes) -> str:
    real_idx = random.randint(1, 50)

    base = random.randint(
        100000,
        999999
    )

    target = (
        base
        + ((real_idx - 1) - base) % 50
    )

    expr = gen_expr(target)

    key = "".join(
        random.choices(
            KEY_CHARS,
            k=random.randint(10, 16)
        )
    )

    key_bytes = key.encode()

    encrypted = [
        byte ^ key_bytes[i % len(key_bytes)]
        for i, byte in enumerate(data)
    ]

    keys = []

    for i in range(50):
        if i + 1 == real_idx:
            keys.append(key)
        else:
            keys.append(
                "".join(
                    random.choices(
                        KEY_CHARS,
                        k=random.randint(10, 16)
                    )
                )
            )

    v1 = ",".join(
        [lua_str(expr)]
        + [str(x) for x in encrypted]
    )

    v2 = ",".join(
        lua_str(k)
        for k in keys
    )

    return f'''--[[ This File Was Protected By MFObfuscator XOR ]]
return(function(...)
    local v1={{{v1}}}
    local v2={{{v2}}}

    local v3=function(d,keys)
        local v=(loadstring or load)("return "..d[1])()

        local key=keys[v%50+1]

        local kb={{}}

        for i=1,#key do
            kb[i]=key:sub(i,i):byte()
        end

        local kl=#kb

        local function bxor(a,b)
            local r,m=0,1

            while a>0 or b>0 do
                if a%2~=b%2 then
                    r=r+m
                end

                a=math.floor(a/2)
                b=math.floor(b/2)
                m=m*2
            end

            return r
        end

        local out={{}}

        for i=2,#d do
            out[#out+1]=string.char(
                bxor(
                    d[i],
                    kb[(i-2)%kl+1]
                )
            )
        end

        return table.concat(out)
    end

    local ls=loadstring or load

    return ls(v3(v1,v2))(...)
end)(...)'''


BUILDERS = {
    "xor": (
        "XOR",
        build_xor
    ),
    "encryptstring": (
        "EncryptString",
        build_encrypt_string
    ),
    "compress": (
        "Compress",
        build_compress
    )
}


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    owner_id=OWNER_ID if OWNER_ID else None
)


def is_owner_or_allowed_role(interaction: discord.Interaction) -> bool:
    if OWNER_ID and interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        if any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
            return True
    return False


@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="promdeobf", description="Deobfuscate Prometheus Lua Script File")
@app_commands.describe(file="File .lua Or .txt Need Deobfuscate")
async def promdeobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Chỉ chấp nhận file `.lua` hoặc `.txt`!", ephemeral=True)
        return

    if file.size > 3 * 1024 * 1024:
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


@wadobf.error
async def wadobf_error(interaction: discord.Interaction, error):
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


@app_commands.check(is_owner_or_allowed_role)
@app_commands.command(name="msecdeobf", description="Deobfuscate Moonsec v3 Lua Script File")
@app_commands.describe(file="File Only .lua Or .txt File Need Deobfuscate")
async def msecdeobf(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(thinking=True)

    if not file.filename.endswith(('.lua', '.txt')):
        await interaction.followup.send("⚠️ Only Work file `.lua` Or `.txt`!", ephemeral=True)
        return

    if file.size > 3 * 1024 * 1024:
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


@app_commands.command(
    name="obfmf",
    description="Select the file you want to obfuscate."
)
@app_commands.describe(
    file="File .lua or .txt, max 1 MB",
    method="Select Method Obfuscation"
)
@app_commands.choices(
    method=[
        app_commands.Choice(
            name="XOR",
            value="xor"
        ),
        app_commands.Choice(
            name="EncryptString",
            value="encryptstring"
        ),
        app_commands.Choice(
            name="Compress",
            value="compress"
        )
    ]
)
async def obfmf(
    interaction: discord.Interaction,
    file: discord.Attachment,
    method: app_commands.Choice[str]
):
    await interaction.response.defer()

    filename = file.filename.lower()

    if not filename.endswith(
        (".lua", ".txt")
    ):
        await interaction.followup.send(
            "❌ File phải có đuôi `.lua` hoặc `.txt."
        )
        return

    if file.size > MAX_FILE_SIZE:
        await interaction.followup.send(
            "❌ File vượt quá giới hạn **1 MB**."
        )
        return

    try:
        data = await file.read()

        if len(data) > MAX_FILE_SIZE:
            await interaction.followup.send(
                "❌ File vượt quá giới hạn **1 MB**."
            )
            return

        if method.value not in BUILDERS:
            await interaction.followup.send(
                "❌ Method không hợp lệ."
            )
            return

        label, builder = BUILDERS[
            method.value
        ]

        output = await asyncio.to_thread(
            builder,
            data
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Không thể xử lý file:\n"
            f"`{type(e).__name__}: {e}`"
        )
        return

    try:
        buffer = io.BytesIO(
            output.encode("utf-8")
        )

        await interaction.followup.send(
            content=(
                f"✅ **MFobfuscator**\n"
                f"📄 File: `{file.filename}`\n"
                f"🔐 Method: **{label}**\n"
                f"📦 Input: `{len(data):,} bytes`\n"
                f"📤 Output: `obfuscated.lua`"
            ),
            file=discord.File(
                buffer,
                filename="obfuscated.lua"
            )
        )

    except discord.HTTPException as e:
        await interaction.followup.send(
            f"❌ Discord upload failed:\n"
            f"`HTTP {e.status}: {e}`"
        )


@bot.event
async def setup_hook():
    bot.session = aiohttp.ClientSession()

    bot.tree.add_command(promdeobf)
    bot.tree.add_command(wadobf)
    bot.tree.add_command(msecdeobf)
    bot.tree.add_command(obfmf)

    if GUILD_ID:
        try:
            guild_id = int(GUILD_ID)
        except ValueError:
            print("❌ GUILD_ID must be a valid integer.")
            return

        guild_obj = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild_obj)

        try:
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"✅ Đã sync {len(synced)} lệnh vào server ID {guild_id}")
        except discord.HTTPException as e:
            print(f"❌ Guild command sync failed: HTTP {e.status} - {e}")
        except Exception as e:
            print(f"❌ Guild command sync failed: {type(e).__name__}: {e}")
    else:
        try:
            synced = await bot.tree.sync()
            print(f"✅ Đã sync {len(synced)} lệnh GLOBAL")
        except discord.HTTPException as e:
            print(f"❌ Global command sync failed: HTTP {e.status} - {e}")


@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Owner ID: {OWNER_ID}")


@bot.event
async def on_disconnect():
    print("⚠️ Discord connection disconnected.")


@bot.event
async def on_resumed():
    print("🔄 Discord connection resumed.")


async def main():
    runner = await start_web_server()

    try:
        print("🚀 Starting Discord bot...")
        await bot.start(DISCORD_TOKEN)
    finally:
        print("🛑 Shutting down web server...")
        try:
            await bot.session.close()
        except Exception:
            pass
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
    except Exception as e:
        print(f"💀 Fatal error: {type(e).__name__}: {e}")
