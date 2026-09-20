import os
import io
import asyncio
import random
import string

import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web


TOKEN = os.environ["TOKEN"]
GUILD_ID = os.environ["GUILD_ID"]

MAX_FILE_SIZE = 1 * 1024 * 1024


intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


B91_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~\""
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
    real_idx = random.randint(
        1,
        50
    )

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


@bot.tree.command(
    name="obfmf",
    description="Bảo vệ file Lua/TXT bằng MFObfuscator"
)
@app_commands.describe(
    file="File .lua hoặc .txt, tối đa 1 MB",
    method="Chọn phương pháp bảo vệ"
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
            "❌ File phải có đuôi `.lua` hoặc `.txt`."
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

        label, builder = BUILDERS[
            method.value
        ]

        output = await asyncio.to_thread(
            builder,
            data
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Không thể xử lý file: "
            f"`{type(e).__name__}: {e}`"
        )
        return

    buffer = io.BytesIO(
        output.encode("utf-8")
    )

    await interaction.followup.send(
        content=(
            f"✅ **MFObfuscator**\n"
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


async def health(request):
    return web.Response(
        text="MFObfuscator Discord Bot: ONLINE"
    )


async def start_web_server():
    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    runner = web.AppRunner(app)

    await runner.setup()

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    print(
        f"🌐 HTTP server listening on {port}"
    )

    return runner


@bot.event
async def on_ready():

    print(
        f"✅ Bot online: {bot.user}"
    )

    try:

        if GUILD_ID:

            guild = discord.Object(
                id=GUILD_ID
            )

            bot.tree.copy_global_to(
                guild=guild
            )

            synced = await bot.tree.sync(
                guild=guild
            )

            print(
                f"✅ Synced {len(synced)} "
                f"slash command(s) "
                f"to guild {GUILD_ID}"
            )

        else:

            synced = await bot.tree.sync()

            print(
                f"✅ Synced {len(synced)} "
                f"global slash command(s)"
            )

    except Exception as e:

        print(
            f"❌ Slash command sync failed: "
            f"{type(e).__name__}: {e}"
        )


async def main():

    runner = await start_web_server()

    try:
        await bot.start(TOKEN)

    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())