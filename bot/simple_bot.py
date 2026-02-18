import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

ADMIN_ROLE_NAME = "Admin"

bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(ctx):
    if ctx.author.guild_permissions.administrator:
        return True
    return any(role.name == ADMIN_ROLE_NAME for role in ctx.author.roles)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
@commands.check(is_admin)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {len(deleted)-1} messages.", delete_after=5)

@bot.command()
@commands.check(is_admin)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member}")

@bot.command()
@commands.check(is_admin)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"Banned {member}")

token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(token)
