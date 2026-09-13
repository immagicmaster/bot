import os
import io
import asyncio
import random
import string

import discord
from discord import app_commands
from discord.ext import commands

TOKEN   = os.environ["TOKEN"]
GUILD_ID = 0  # điền ID server để sync lệnh ngay, 0 = global (có thể chờ ~1 giờ)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# =====================================================================
#  BASE91 (EncryptString)
# =====================================================================
B91_ALPHABET = ('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                '0123456789!#$%&()*+,./:;<=>?@[]^_`{|}~"')

def b91_encode(data: bytes) -> str:
    b, n, out = 0, 0, []
    for byte in data:
        b |= byte << n
        n += 8
        if n > 13:
            v = b & 8191
            if v > 88:
                b >>= 13; n -= 13
            else:
                v = b & 16383
                b >>= 14; n -= 14
            out.append(B91_ALPHABET[v % 91])
            out.append(B91_ALPHABET[v // 91])
    if n:
        out.append(B91_ALPHABET[b % 91])
        if n > 7 or b > 90:
            out.append(B91_ALPHABET[b // 91])
    return ''.join(out)

def build_encrypt_string(data: bytes) -> str:
    v1 = lua_str(b91_encode(data))
    v2 = ",".join(lua_str(c) for c in B91_ALPHABET)
    return f'''--[[ This File Was Protected By MFObfuscator EncryptString ]]
return(function(...)
    local v1={v1}
    local v2={{{v2}}}
    local v3=function(s,A)
        local decode={{}} for i=1,#A do decode[A[i]]=i-1 end
        local b,n,out,v=0,0,{{}},-1
        for i=1,#s do
            local d=decode[s:sub(i,i)]
            if d then
                if v<0 then v=d
                else
                    v=v+d*91
                    b=b+v*2^n
                    if v%8192>88 then n=n+13 else n=n+14 end
                    while n>7 do
                        out[#out+1]=string.char(b%256)
                        b=math.floor(b/256)
                        n=n-8
                    end
                    v=-1
                end
            end
        end
        if v>=0 then out[#out+1]=string.char((b+v*2^n)%256) end
        return table.concat(out)
    end
    local ls=loadstring or load
    return ls(v3(v1,v2))(...)
end)(...)'''

# =====================================================================
#  LZ77 (Compress)
# =====================================================================
def lz_tokens(data: bytes, window=4096, min_len=3, max_len=18):
    n = len(data)
    pos_map, tokens, i = {}, [], 0
    while i < n:
        best_len, best_dist = 0, 0
        if i + min_len <= n:
            for j in pos_map.get(data[i:i+min_len], ()):
                if i - j > window:
                    continue
                l = min_len
                while l < max_len and i + l < n and data[j+l] == data[i+l]:
                    l += 1
                if l > best_len:
                    best_len, best_dist = l, i - j
                    if l == max_len:
                        break
        if best_len >= min_len:
            tokens.append((1, best_dist, best_len))
            for p in range(i, min(i + best_len, n - 2)):
                pos_map.setdefault(data[p:p+3], []).append(p)
            i += best_len
        else:
            tokens.append((0, data[i]))
            if i + 3 <= n:
                pos_map.setdefault(data[i:i+3], []).append(i)
            i += 1
        for lst in pos_map.values():
            if len(lst) > 128:
                del lst[:-128]
    return tokens

def build_compress(data: bytes) -> str:
    flat = []
    for t in lz_tokens(data):
        flat.extend(t)
    v1 = ",".join(map(str, flat))
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
                for k=0,len-1 do out[#out+1]=out[pos+k] end
                i=i+3
            end
        end
        return table.concat(out)
    end
    local ls=loadstring or load
    return ls(v3(v1,v2))(...)
end)(...)'''

# =====================================================================
#  XOR 50 KEYS + phép tính detect key
# =====================================================================
KEY_CHARS = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>/?"

def gen_expr(target: int, depth=0) -> str:
    if depth >= 4 or target < 50:
        return f"{target:05d}"
    m = random.randint(7, 97)
    q, r = divmod(target, m)
    return f"({gen_expr(q, depth+1)}*{gen_expr(m, depth+1)}+{gen_expr(r, depth+1)})"

def build_xor(data: bytes) -> str:
    real_idx = random.randint(1, 50)
    base   = random.randint(100000, 999999)
    target = base + ((real_idx - 1) - base) % 50   # target % 50 + 1 == real_idx
    expr   = gen_expr(target)
    assert eval(expr) == target                     # an toàn: biểu thức do ta tự sinh

    key = "".join(random.choices(KEY_CHARS, k=random.randint(10, 16)))
    kb  = key.encode()
    enc = [b ^ kb[i % len(kb)] for i, b in enumerate(data)]

    keys = [key if i + 1 == real_idx else
            "".join(random.choices(KEY_CHARS, k=random.randint(10, 16)))
            for i in range(50)]

    v1 = ",".join([lua_str(expr)] + [str(x) for x in enc])
    v2 = ",".join(lua_str(k) for k in keys)
    return f'''--[[ This File Was Protected By MFObfuscator XOR ]]
return(function(...)
    local v1={{{v1}}}
    local v2={{{v2}}}
    local v3=function(d,keys)
        local v=(loadstring or load)("return "..d[1])()
        local key=keys[v%50+1]
        local kb={{}} for i=1,#key do kb[i]=key:sub(i,i):byte() end
        local kl=#kb
        local function bxor(a,b)
            local r,m=0,1
            while a>0 or b>0 do
                if a%2~=b%2 then r=r+m end
                a=math.floor(a/2) b=math.floor(b/2) m=m*2
            end
            return r
        end
        local out={{}}
        for i=2,#d do
            out[#out+1]=string.char(bxor(d[i],kb[(i-2)%kl+1]))
        end
        return table.concat(out)
    end
    local ls=loadstring or load
    return ls(v3(v1,v2))(...)
end)(...)'''

# =====================================================================
#  TIỆN ÍCH
# =====================================================================
def lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

BUILDERS = {
    "encryptstring": ("EncryptString", build_encrypt_string),
    "compress":      ("Compress",      build_compress),
    "xor":           ("XOR",           build_xor),
}

# =====================================================================
#  LỆNH SLASH /obf
# =====================================================================
@bot.tree.command(name="obf", description="Obfuscate file .lua/.txt")
@app_commands.describe(
    file="File .lua hoặc .txt cần bảo vệ",
    method="Chọn đúng 1 phương pháp: EncryptString | Compress | XOR",
)
@app_commands.choices(method=[
    app_commands.Choice(name="EncryptString", value="encryptstring"),
    app_commands.Choice(name="Compress",      value="compress"),
    app_commands.Choice(name="XOR",           value="xor"),
])
async def obf(interaction: discord.Interaction,
              file: discord.Attachment,
              method: app_commands.Choice[str]):
    await interaction.response.defer()

    if not file.filename.lower().endswith((".lua", ".txt")):
        return await interaction.followup.send("❌ Chỉ hỗ trợ file `.lua` hoặc `.txt`")
    if getattr(file, "size", 0) > 5 * 1024 * 1024:
        return await interaction.followup.send("❌ File quá lớn (tối đa 5MB)")

    data = await file.read()
    label, builder = BUILDERS[method.value]

    try:
        output = builder(data)
    except Exception as e:
        return await interaction.followup.send(f"❌ Lỗi khi obfuscate: `{e}`")

    buf = io.BytesIO(output.encode("utf-8"))
    await interaction.followup.send(
        content=f"✅ Đã bảo vệ bằng **{label}** · `{file.filename}` → `obfuscated.lua`",
        file=discord.File(buf, filename="obfuscated.lua"),
    )

@bot.event
async def on_ready():
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
    print(f"✅ Đăng nhập thành công: {bot.user}")

async def main():
    await start_web_server()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
