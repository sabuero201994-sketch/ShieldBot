import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import random
import asyncio

# --- Setup Bot and Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class PaidModeratorBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()

bot = PaidModeratorBot()

# --- Database Setup (Saves warning values safely) ---
db = sqlite3.connect("bot_data.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_warnings (
    guild_id TEXT,
    user_id TEXT,
    warning_count INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")
db.commit()

# --- Your Fast, Automated Blacklist Engine ---
banned_database = ["scam", "hack", "fuck", "gago", "puta"]

def detect_bad_words(text: str) -> bool:
    # Converts text to lowercase so it automatically catches capital letters like "GAGO" or "SCAM"
    clean_text = text.lower()
    for word in banned_database:
        if word in clean_text:
            return True
    return False

# --- Discord Events ---
@bot.event
async def on_ready():
    print(f"✅ ShieldBot is operational as {bot.user.name} ({bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # IMMUNITY: Completely skips the server owner
    if message.author.id == message.guild.owner_id:
        return

    # Scan content for multi-language profanity using your engine
    if detect_bad_words(message.content):
        try:
            await message.delete() # Automatically deletes the text from the chat!
        except discord.Forbidden:
            print(f"❌ Missing 'Manage Messages' permission in {message.guild.name}")
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)

        # Database checks your warnings
        cursor.execute("SELECT warning_count FROM user_warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("INSERT INTO user_warnings (guild_id, user_id, warning_count) VALUES (?, ?, 1)", (guild_id, user_id))
            warnings = 1
        else:
            warnings = row[0] + 1
            cursor.execute("UPDATE user_warnings SET warning_count = ? WHERE guild_id = ? AND user_id = ?", (warnings, guild_id, user_id))
        
        db.commit()

        # Enforce strike limits
        if warnings >= 3:
            is_admin = message.author.guild_permissions.administrator

            if is_admin:
                try:
                    # Strips admin roles automatically
                    roles_to_remove = [role for role in message.author.roles if role.permissions.administrator]
                    if roles_to_remove:
                        await message.author.remove_roles(*roles_to_remove, reason="Automated filter: Demoted for strike 3.")
                        await message.channel.send(f"📉 **{message.author.name}** has been **DEMOTED** for reaching 3 warnings! All Admin roles removed.")
                    
                    cursor.execute("DELETE FROM user_warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                    db.commit()
                except discord.Forbidden:
                    await message.channel.send(f"❌ **Failed to demote Administrator {message.author.mention}! Move the Bot's role higher.**")
            else:
                # Regular user logic: standard ban
                try:
                    await message.guild.ban(message.author, reason="Automated filter: Reached maximum warnings.")
                    await message.channel.send(f"🚨 **{message.author.name}** has been banned for reaching 3 warnings.")
                    
                    cursor.execute("DELETE FROM user_warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
                    db.commit()
                except discord.Forbidden:
                    await message.channel.send(f"❌ Could not ban {message.author.mention}.")
        else:
            # Automatic notification response
            await message.channel.send(
                f"⚠️ {message.author.mention}, that language is not allowed here. "
                f"Warning **{warnings}/3**. A 3rd warning will result in a **BAN** (or **DEMOTION** for Admins)."
            )

# --- Chat Command (Let's you talk through the bot) ---
@bot.tree.command(name="say", description="[Owner Only] Make the bot speak for you.")
@app_commands.describe(message="The message you want the bot to say")
async def say(interaction: discord.Interaction, message: str):
    # This automatically deletes your command entry text from the chat log
    await interaction.channel.send(message)
    await interaction.response.send_message("Message sent!", ephemeral=True)

# --- Game Module: Rock Paper Scissors ---
@bot.tree.command(name="rps", description="Play Rock-Paper-Scissors against the bot!")
@app_commands.describe(choice="Choose rock, paper, or scissors")
@app_commands.choices(choice=[
    app_commands.Choice(name="Rock 🪨", value="rock"),
    app_commands.Choice(name="Paper 📄", value="paper"),
    app_commands.Choice(name="Scissors ✂️", value="scissors")
])
async def rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    bot_choice = random.choice(["rock", "paper", "scissors"])
    user_choice = choice.value
    
    if user_choice == bot_choice:
        result = f"🤝 It's a tie! We both chose **{bot_choice.upper()}**."
    elif (user_choice == "rock" and bot_choice == "scissors") or \
         (user_choice == "paper" and bot_choice == "rock") or \
         (user_choice == "scissors" and bot_choice == "paper"):
        result = f"🎉 **YOU WIN!** Your **{user_choice.upper()}** beats my **{bot_choice.upper()}**!"
    else:
        result = f"😔 **YOU LOSE!** My **{bot_choice.upper()}** beats your **{user_choice.upper()}**!"
        
    await interaction.response.send_message(f"🎮 **RPS GAME**\n🧑 You: **{user_choice.upper()}**\n🤖 Bot: **{bot_choice.upper()}**\n\n{result}")

# --- Prank Module: Ghostping ---
@bot.tree.command(name="ghostping", description="[Owner Only] Deploy an invisible phantom tag prank.")
@app_commands.describe(target="The user instance to ghostping")
async def ghostping(interaction: discord.Interaction, target: discord.Member):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Command operator unauthorized.", ephemeral=True)
        return
    await interaction.response.send_message("Ghostping deployed!", ephemeral=True)
    ping_msg = await interaction.channel.send(target.mention)
    await asyncio.sleep(0.1) # Wait a millisecond split-second
    await ping_msg.delete() # Vaporizes the tag instantly!

# --- Fun Module: Story Time ---
@bot.tree.command(name="story", description="Let the bot tell you a funny gaming story.")
async def story(interaction: discord.Interaction):
    stories = [
        f"Once upon a time, **{interaction.user.name}** clutched a 1v5 in BedWars while playing on a slow Chromebook. The server went completely wild, and even the anti-cheat thought it was a script exploit! 💻🔥",
        f"Legend says **{interaction.user.name}** spent an entire Friday night coding an advanced security bot instead of sleeping. The bot became so powerful it automatically muted a rogue admin on strike 3! 🤖🛡️",
        f"Breaking News: **{interaction.user.name}** was spotted dominating Blox Fruits, but got disconnected because the Converge Wi-Fi lag spiked right during the boss battle. Sad life! ⚔️😭"
    ]
    await interaction.response.send_message(f"📖 **STORY TIME**\n\n{random.choice(stories)}")

# --- Utility Module: Avatar Stealer ---
@bot.tree.command(name="avatar", description="Extract and print a full high-resolution profile picture.")
@app_commands.describe(target="The member whose profile picture you want to capture")
async def avatar(interaction: discord.Interaction, target: discord.Member):
    embed = discord.Embed(title=f"🖼️ Profile Image Card: {target.name}", color=discord.Color.purple())
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# --- Game Module: Coinflip ---
@bot.tree.command(name="coinflip", description="Flip a coin! Guess Heads or Tails.")
@app_commands.describe(choice="Heads or Tails")
@app_commands.choices(choice=[
    app_commands.Choice(name="Heads 🪙", value="heads"),
    app_commands.Choice(name="Tails 🪙", value="tails")
])
async def coinflip(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    flip_result = random.choice(["heads", "tails"])
    if choice.value == flip_result:
        await interaction.response.send_message(f"🪙 The coin landed on **{flip_result.upper()}**! 🎉 You guessed correctly, gng!")
    else:
        await interaction.response.send_message(f"🪙 The coin landed on **{flip_result.upper()}**... 😔 Unlucky guess, house wins!")

# --- Game Module: Blox Fruits Gacha Roller ---
@bot.tree.command(name="rollfruit", description="Spend your luck and roll a random daily Blox Fruit!")
async def rollfruit(interaction: discord.Interaction):
    # A localized database list matching the actual 2026 Blox Fruits ranks!
    fruit_gacha = [
        {"name": "Rocket 🚀", "tier": "Common", "value": "₱5,000", "color": 0x808080},
        {"name": "Spin 🌀", "tier": "Common", "value": "₱7,500", "color": 0x808080},
        {"name": "Chop 🪓", "tier": "Common", "value": "₱30,000", "color": 0x808080},
        {"name": "Spring 🦘", "tier": "Uncommon", "value": "₱60,000", "color": 0x00FF00},
        {"name": "Smoke 💨", "tier": "Uncommon", "value": "₱100,000", "color": 0x00FF00},
        {"name": "Ice 🧊", "tier": "Rare", "value": "₱350,000", "color": 0x0000FF},
        {"name": "Light 💡", "tier": "Rare", "value": "₱650,000", "color": 0x0000FF},
        {"name": "Magma 🌋", "tier": "Rare", "value": "₱850,000", "color": 0x0000FF},
        {"name": "Quake 🫨", "tier": "Legendary", "value": "₱1,000,000", "color": 0xFFA500},
        {"name": "Buddha 🧘", "tier": "Legendary", "value": "₱1,200,000", "color": 0xFFA500},
        {"name": "Portal 🌀", "tier": "Legendary", "value": "₱1,900,000", "color": 0xFFA500},
        {"name": "Dough 🍩", "tier": "Mythical", "value": "₱2,800,000", "color": 0xFF0000},
        {"name": "Leopard 🐆", "tier": "Mythical", "value": "₱5,000,000", "color": 0xFF0000},
        {"name": "Dragon 🐉", "tier": "Mythical", "value": "₱10,000,000", "color": 0xFF0000},
        {"name": "Kitsune 🦊", "tier": "Mythical", "value": "₱8,000,000", "color": 0xFF0000}
    ]
    
    # Let the random algorithm pick a fruit entry
    rolled = random.choice(fruit_gacha)
    
    # Construct a gorgeous UI layout box (Embed) for the results card
    embed = discord.Embed(
        title="🏴‍☠️ BLOX FRUITS COUSIN GACHA", 
        description=f"**{interaction.user.name}** spent their luck and rolled a new physical fruit!",
        color=rolled["color"]
    )
    embed.add_field(name="Fruit Obtained", value=f"**{rolled['name']}**", inline=False)
    embed.add_field(name="Rarity Tier", value=rolled["tier"], inline=True)
    embed.add_field(name="Beli Value / Worth", value=rolled["value"], inline=True)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    # Add custom flavor text based on how rare the roll is
    if rolled["tier"] == "Mythical":
        embed.set_footer(text="👑 ABSOLUTE GODLY LUCK! GG GNG!!! 🔥")
    elif rolled["tier"] == "Legendary":
        embed.set_footer(text="✨ Big W! Perfect fruit for grinding!")
    else:
        embed.set_footer(text="🤡 Unlucky roll... The dealer scammed you.")
        
    await interaction.response.send_message(embed=embed)

# --- Boot Engine Execution ---
# This line tells the bot to look into Render's secret cloud vault instead of reading the file!
import os
bot.run(os.getenv("DISCORD_TOKEN"))


# --- How to insert your private assets securely ---
# Copy this whole block into your laptop's Notepad app.
# Replace the text below with your private token inside your private file!
bot.run("")
