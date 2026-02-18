cat > simple_bot.py << 'PY'
import os
import json
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

# ======================
# Configuration
# ======================
ADMIN_ROLE_NAME = "Admin"       # users with this role can use commands (admins also allowed)
TASKS_FILE = "tasks.json"
GUILD_ID = int(os.getenv("GUILD_ID", "0"))  # set as env var for fast guild sync

# ======================
# Bot Setup
# ======================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_admin_interaction(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return any(r.name == ADMIN_ROLE_NAME for r in getattr(interaction.user, "roles", []))

def require_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return is_admin_interaction(interaction)
    return app_commands.check(predicate)

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} commands to guild {GUILD_ID}", flush=True)
            print("✅ Commands:", ", ".join([c.name for c in synced]), flush=True)
        else:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} global commands (may take time to appear)", flush=True)
            print("✅ Commands:", ", ".join([c.name for c in synced]), flush=True)

        print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})", flush=True)
    except Exception as e:
        print(f"❌ Sync failed: {e!r}", flush=True)

# ======================
# Moderation (Admin)
# ======================

@bot.tree.command(name="purge", description="Delete messages in this channel (admin only).")
@require_admin()
@app_commands.describe(amount="Number of messages to delete (1-200).")
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 200:
        await interaction.response.send_message("Amount must be 1–200.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)

@bot.tree.command(name="lock", description="Lock this channel (admin only).")
@require_admin()
async def lock(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔒 Channel locked.", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock this channel (admin only).")
@require_admin()
async def unlock(interaction: discord.Interaction):
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel unlocked.", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a member (admin only).")
@require_admin()
@app_commands.describe(member="Member to kick", reason="Reason (optional)")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ Kicked {member.mention}. Reason: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I lack permission (role hierarchy / perms).", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member (admin only).")
@require_admin()
@app_commands.describe(member="Member to ban", reason="Reason (optional)")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason, delete_message_days=0)
        await interaction.response.send_message(f"✅ Banned {member.mention}. Reason: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I lack permission (role hierarchy / perms).", ephemeral=True)

# ======================
# Tasks (Role-based)
# ======================

@bot.tree.command(name="task_assign", description="Assign a task to a role (admin only).")
@require_admin()
@app_commands.describe(role="Role to assign to", task="Task description", due="Due date YYYY-MM-DD")
async def task_assign(interaction: discord.Interaction, role: discord.Role, task: str, due: str):
    try:
        datetime.strptime(due, "%Y-%m-%d")
    except ValueError:
        await interaction.response.send_message("❌ Due must be YYYY-MM-DD.", ephemeral=True)
        return

    tasks = load_tasks()
    next_id = (max([t.get("id", 0) for t in tasks]) + 1) if tasks else 1
    tasks.append({
        "id": next_id,
        "role_id": role.id,
        "task": task,
        "due": due,
        "completed": False,
        "created_by": interaction.user.id
    })
    save_tasks(tasks)

    await interaction.response.send_message(
        f"📌 Task assigned to **{role.name}**\n**ID:** {next_id}\n**Task:** {task}\n**Due:** {due}",
        ephemeral=True
    )

@bot.tree.command(name="task_list", description="List active tasks (admin only).")
@require_admin()
async def task_list(interaction: discord.Interaction):
    tasks = [t for t in load_tasks() if not t.get("completed")]
    if not tasks:
        await interaction.response.send_message("No active tasks.", ephemeral=True)
        return

    lines = [f"#{t['id']} <@&{t['role_id']}> — {t['task']} (Due {t['due']})" for t in tasks]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.tree.command(name="task_complete", description="Mark a task complete (admin only).")
@require_admin()
@app_commands.describe(task_id="Task ID number from /task_list")
async def task_complete(interaction: discord.Interaction, task_id: int):
    tasks = load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            t["completed"] = True
            t["completed_by"] = interaction.user.id
            t["completed_at"] = datetime.utcnow().isoformat()
            save_tasks(tasks)
            await interaction.response.send_message(f"✅ Task #{task_id} marked complete.", ephemeral=True)
            return
    await interaction.response.send_message("❌ Task ID not found.", ephemeral=True)

# ======================
# Categories & Channels (Admin)
# ======================

@bot.tree.command(name="category_create", description="Create a category (admin only).")
@require_admin()
@app_commands.describe(name="Category name")
async def category_create(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        cat = await interaction.guild.create_category(name=name, reason=f"Created by {interaction.user}")
        await interaction.followup.send(f"✅ Created category: **{cat.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

@bot.tree.command(name="channel_create_text", description="Create a text channel (admin only).")
@require_admin()
@app_commands.describe(name="Channel name", category="Category (optional)")
async def channel_create_text(interaction: discord.Interaction, name: str, category: discord.CategoryChannel | None = None):
    await interaction.response.defer(ephemeral=True)
    try:
        ch = await interaction.guild.create_text_channel(name=name, category=category, reason=f"Created by {interaction.user}")
        await interaction.followup.send(f"✅ Created text channel: {ch.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

@bot.tree.command(name="channel_create_voice", description="Create a voice channel (admin only).")
@require_admin()
@app_commands.describe(name="Channel name", category="Category (optional)")
async def channel_create_voice(interaction: discord.Interaction, name: str, category: discord.CategoryChannel | None = None):
    await interaction.response.defer(ephemeral=True)
    try:
        ch = await interaction.guild.create_voice_channel(name=name, category=category, reason=f"Created by {interaction.user}")
        await interaction.followup.send(f"✅ Created voice channel: **{ch.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

@bot.tree.command(name="channel_delete", description="Delete a channel (admin only).")
@require_admin()
@app_commands.describe(channel="Channel to delete", reason="Reason (optional)")
async def channel_delete(interaction: discord.Interaction, channel: discord.abc.GuildChannel, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        name = channel.name
        await channel.delete(reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(f"✅ Deleted channel: **{name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

@bot.tree.command(name="channel_rename", description="Rename a channel (admin only).")
@require_admin()
@app_commands.describe(channel="Channel to rename", new_name="New name")
async def channel_rename(interaction: discord.Interaction, channel: discord.abc.GuildChannel, new_name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        old = channel.name
        await channel.edit(name=new_name, reason=f"Renamed by {interaction.user}")
        await interaction.followup.send(f"✅ Renamed **{old}** → **{new_name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

@bot.tree.command(name="channel_move", description="Move a channel to a category (admin only).")
@require_admin()
@app_commands.describe(channel="Channel to move", category="Destination category")
async def channel_move(interaction: discord.Interaction, channel: discord.abc.GuildChannel, category: discord.CategoryChannel):
    await interaction.response.defer(ephemeral=True)
    try:
        await channel.edit(category=category, reason=f"Moved by {interaction.user}")
        await interaction.followup.send(f"✅ Moved **{channel.name}** to **{category.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Channels** permission.", ephemeral=True)

# ======================
# Roles (Admin)
# ======================

@bot.tree.command(name="role_create", description="Create a role (admin only).")
@require_admin()
@app_commands.describe(name="Role name", color_hex="Optional hex like #ff0000", hoist="Show separately", mentionable="Allow @mentions")
async def role_create(interaction: discord.Interaction, name: str, color_hex: str = "", hoist: bool = False, mentionable: bool = False):
    await interaction.response.defer(ephemeral=True)

    color = discord.Color.default()
    if color_hex:
        try:
            hx = color_hex.strip().lstrip("#")
            color = discord.Color(int(hx, 16))
        except ValueError:
            await interaction.followup.send("❌ Invalid hex color. Example: `#ff0000`", ephemeral=True)
            return

    try:
        role = await interaction.guild.create_role(
            name=name, color=color, hoist=hoist, mentionable=mentionable,
            reason=f"Created by {interaction.user}"
        )
        await interaction.followup.send(f"✅ Created role: **{role.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Roles** permission.", ephemeral=True)

@bot.tree.command(name="role_delete", description="Delete a role (admin only).")
@require_admin()
@app_commands.describe(role="Role to delete", reason="Reason (optional)")
async def role_delete(interaction: discord.Interaction, role: discord.Role, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        name = role.name
        await role.delete(reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(f"✅ Deleted role: **{name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Need **Manage Roles** permission.", ephemeral=True)

@bot.tree.command(name="role_add_member", description="Add a role to a member (admin only).")
@require_admin()
@app_commands.describe(member="Member", role="Role to add", reason="Reason (optional)")
async def role_add_member(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        await member.add_roles(role, reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(f"✅ Added **{role.name}** to {member.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ I lack permission (role hierarchy / Manage Roles).", ephemeral=True)

@bot.tree.command(name="role_remove_member", description="Remove a role from a member (admin only).")
@require_admin()
@app_commands.describe(member="Member", role="Role to remove", reason="Reason (optional)")
async def role_remove_member(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        await member.remove_roles(role, reason=f"{reason} (by {interaction.user})")
        await interaction.followup.send(f"✅ Removed **{role.name}** from {member.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ I lack permission (role hierarchy / Manage Roles).", ephemeral=True)

# ======================
# Rules broadcast (Admin)
# ======================

@bot.tree.command(name="rules_post", description="Post rules to one channel or all text channels (admin only).")
@require_admin()
@app_commands.describe(message="Rules text", channel="Optional single channel", include_locked="Include channels where @everyone can't send")
async def rules_post(
    interaction: discord.Interaction,
    message: str,
    channel: discord.TextChannel | None = None,
    include_locked: bool = False
):
    await interaction.response.defer(ephemeral=True)

    targets = [channel] if channel else list(interaction.guild.text_channels)

    posted = 0
    skipped_or_failed = 0

    for ch in targets:
        perms = ch.permissions_for(interaction.guild.me)
        if not (perms.view_channel and perms.send_messages):
            skipped_or_failed += 1
            continue

        if not include_locked:
            everyone_perms = ch.permissions_for(interaction.guild.default_role)
            if everyone_perms.send_messages is False:
                continue

        try:
            await ch.send(message)
            posted += 1
        except discord.Forbidden:
            skipped_or_failed += 1

    await interaction.followup.send(f"✅ Posted rules to {posted} channel(s). Skipped/failed: {skipped_or_failed}.", ephemeral=True)

# ======================
# Run
# ======================
token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set.")
bot.run(token)
PY
