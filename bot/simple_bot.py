import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

ADMIN_ROLE_NAME = "Admin"  # must match role name in your server

bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(ctx: commands.Context) -> bool:
    if ctx.author.guild_permissions.administrator:
        return True
    return any(r.name == ADMIN_ROLE_NAME for r in ctx.author.roles)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
@commands.check(is_admin)
@commands.guild_only()
async def purge(ctx, amount: int):
    if amount < 1 or amount > 200:
        await ctx.send("Amount must be between 1 and 200.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {len(deleted) - 1} messages.", delete_after=5)

@bot.command()
@commands.check(is_admin)
@commands.guild_only()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ Kicked {member.mention}. Reason: {reason}")

@bot.command()
@commands.check(is_admin)
@commands.guild_only()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason, delete_message_days=0)
    await ctx.send(f"✅ Banned {member.mention}. Reason: {reason}")

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set.")
bot.run(token)
