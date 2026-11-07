import os
import sqlite3
import time

import discord
from discord import app_commands

TOKEN = os.getenv("MTI0MDQ0NDA2NTkyNTgyNDU5Mg.GIK_9G.VySrzsYT7UVSbTi4dhKOjL5ExYUPvSxkp7-I6c") or "MTI0MDQ0NDA2NTkyNTgyNDU5Mg.GIK_9G.VySrzsYT7UVSbTi4dhKOjL5ExYUPvSxkp7-I6c"

# ---------- قاعدة البيانات ----------
db = sqlite3.connect("time.db")
db.execute(
    """CREATE TABLE IF NOT EXISTS users (
        guild_id INTEGER,
        user_id INTEGER,
        total INTEGER DEFAULT 0,
        clock_in INTEGER,
        PRIMARY KEY (guild_id, user_id)
    )"""
)
db.commit()


def get_user(guild_id, user_id):
    db.execute(
        "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
        (guild_id, user_id),
    )
    db.commit()
    return db.execute(
        "SELECT total, clock_in FROM users WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    ).fetchone()


def fmt(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    seconds = abs(int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h} ساعة، {m} دقيقة، {s} ثانية"


def live_total(guild_id, user_id) -> int:
    total, clock_in = get_user(guild_id, user_id)
    if clock_in:
        total += int(time.time()) - clock_in
    return total


# ---------- البوت ----------
class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(TimePanel())
        await self.tree.sync()


bot = Bot()
admin_only = app_commands.default_permissions(administrator=True)


async def do_clockin(interaction: discord.Interaction):
    gid, uid = interaction.guild_id, interaction.user.id
    _, clock_in = get_user(gid, uid)
    if clock_in:
        await interaction.response.send_message("⚠️ أنت مسجّل دخول أصلاً.", ephemeral=True)
        return
    db.execute(
        "UPDATE users SET clock_in=? WHERE guild_id=? AND user_id=?",
        (int(time.time()), gid, uid),
    )
    db.commit()
    await interaction.response.send_message(f"✅ {interaction.user.mention} سجّل دخول. بدأ حساب الوقت.")


async def do_clockout(interaction: discord.Interaction):
    gid, uid = interaction.guild_id, interaction.user.id
    total, clock_in = get_user(gid, uid)
    if not clock_in:
        await interaction.response.send_message("⚠️ أنت مش مسجّل دخول.", ephemeral=True)
        return
    session = int(time.time()) - clock_in
    total += session
    db.execute(
        "UPDATE users SET total=?, clock_in=NULL WHERE guild_id=? AND user_id=?",
        (total, gid, uid),
    )
    db.commit()
    await interaction.response.send_message(
        f"🔴 {interaction.user.mention} سجّل خروج.\n"
        f"مدة الجلسة: **{fmt(session)}**\n"
        f"المجموع: **{fmt(total)}**"
    )


class TimePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # أزرار دائمة

    @discord.ui.button(label="تسجيل دخول", style=discord.ButtonStyle.success,
                       emoji="🟢", custom_id="panel:clockin")
    async def in_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_clockin(interaction)

    @discord.ui.button(label="تسجيل خروج", style=discord.ButtonStyle.danger,
                       emoji="🔴", custom_id="panel:clockout")
    async def out_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_clockout(interaction)

    @discord.ui.button(label="وقتي", style=discord.ButtonStyle.secondary,
                       emoji="⏱️", custom_id="panel:mytime")
    async def time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = live_total(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(f"⏱️ مجموع وقتك: **{fmt(total)}**", ephemeral=True)


@bot.tree.command(name="panel", description="[أدمن] إرسال لوحة أزرار تسجيل الدخول والخروج")
@admin_only
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⏱️ نظام تسجيل الوقت",
        description="اضغط على الزر المناسب لتسجيل دخولك أو خروجك.",
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=TimePanel())
    await interaction.response.send_message("تم إرسال اللوحة ✅", ephemeral=True)


@bot.tree.command(name="clockin", description="تسجيل دخول وبدء حساب الوقت")
async def clockin(interaction: discord.Interaction):
    await do_clockin(interaction)


@bot.tree.command(name="clockout", description="تسجيل خروج وإيقاف حساب الوقت")
async def clockout(interaction: discord.Interaction):
    await do_clockout(interaction)


@bot.tree.command(name="mytime", description="شوف مجموع وقتك")
async def mytime(interaction: discord.Interaction):
    total = live_total(interaction.guild_id, interaction.user.id)
    await interaction.response.send_message(f"⏱️ مجموع وقتك: **{fmt(total)}**", ephemeral=True)


@bot.tree.command(name="leaderboard", description="أعلى 10 بالوقت")
async def leaderboard(interaction: discord.Interaction):
    rows = db.execute(
        "SELECT user_id FROM users WHERE guild_id=?", (interaction.guild_id,)
    ).fetchall()
    data = sorted(
        ((r[0], live_total(interaction.guild_id, r[0])) for r in rows),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    if not data:
        await interaction.response.send_message("ما في بيانات بعد.")
        return
    lines = [f"**{i}.** <@{uid}> — {fmt(t)}" for i, (uid, t) in enumerate(data, 1)]
    await interaction.response.send_message("🏆 **المتصدرين**\n" + "\n".join(lines))


# ---------- أوامر الأدمن ----------
@bot.tree.command(name="addtime", description="[أدمن] إضافة وقت لعضو")
@admin_only
@app_commands.describe(member="العضو", hours="ساعات", minutes="دقائق")
async def addtime(interaction: discord.Interaction, member: discord.Member,
                  hours: app_commands.Range[int, 0, 10000] = 0,
                  minutes: app_commands.Range[int, 0, 59] = 0):
    seconds = hours * 3600 + minutes * 60
    get_user(interaction.guild_id, member.id)
    db.execute(
        "UPDATE users SET total = total + ? WHERE guild_id=? AND user_id=?",
        (seconds, interaction.guild_id, member.id),
    )
    db.commit()
    await interaction.response.send_message(
        f"➕ تمت إضافة **{fmt(seconds)}** لـ {member.mention}.\n"
        f"المجموع الآن: **{fmt(live_total(interaction.guild_id, member.id))}**"
    )


@bot.tree.command(name="removetime", description="[أدمن] خصم وقت من عضو")
@admin_only
@app_commands.describe(member="العضو", hours="ساعات", minutes="دقائق")
async def removetime(interaction: discord.Interaction, member: discord.Member,
                     hours: app_commands.Range[int, 0, 10000] = 0,
                     minutes: app_commands.Range[int, 0, 59] = 0):
    seconds = hours * 3600 + minutes * 60
    get_user(interaction.guild_id, member.id)
    db.execute(
        "UPDATE users SET total = MAX(0, total - ?) WHERE guild_id=? AND user_id=?",
        (seconds, interaction.guild_id, member.id),
    )
    db.commit()
    await interaction.response.send_message(
        f"➖ تم خصم **{fmt(seconds)}** من {member.mention}.\n"
        f"المجموع الآن: **{fmt(live_total(interaction.guild_id, member.id))}**"
    )


@bot.tree.command(name="checktime", description="[أدمن] شوف وقت عضو")
@admin_only
async def checktime(interaction: discord.Interaction, member: discord.Member):
    total = live_total(interaction.guild_id, member.id)
    await interaction.response.send_message(
        f"⏱️ وقت {member.mention}: **{fmt(total)}**", ephemeral=True
    )


@bot.tree.command(name="resettime", description="[أدمن] تصفير وقت عضو")
@admin_only
async def resettime(interaction: discord.Interaction, member: discord.Member):
    get_user(interaction.guild_id, member.id)
    db.execute(
        "UPDATE users SET total=0, clock_in=NULL WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, member.id),
    )
    db.commit()
    await interaction.response.send_message(f"🔄 تم تصفير وقت {member.mention}.")


@bot.event
async def on_ready():
    print(f"شغّال كـ {bot.user}")


bot.run(TOKEN)
