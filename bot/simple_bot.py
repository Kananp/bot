cat > simple_bot.py << 'PY'
import os
import discord
from discord import app_commands
from discord.ext import commands

ADMIN_ROLE_NAME = "Admin"
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return any(r.name == ADMIN_ROLE_NAME for r in getattr(interaction.user, "roles", []))

def require_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return is_admin(interaction)
    return app_commands.check(predicate)

@bot.event
async def on_ready():
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {GUILD_ID}: {[c.name for c in synced]}", flush=True)
    else:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} global commands: {[c.name for c in synced]}", flush=True)

    print(f"✅ Logged in as {bot.user}", flush=True)

@bot.tree.command(name="ping", description="Test the bot is alive.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)

@bot.tree.command(name="role_create", description="Create a role (admin only).")
@require_admin()
@app_commands.describe(name="Role name")
async def role_create(interaction: discord.Interaction, name: str):
    try:
        role = await interaction.guild.create_role(name=name, reason=f"Created by {interaction.user}")
        await interaction.response.send_message(f"✅ Created role: **{role.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Need **Manage Roles** permission.", ephemeral=True)

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set.")
bot.run(token)
PY
