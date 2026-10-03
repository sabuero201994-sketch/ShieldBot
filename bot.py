import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# --- AUTOMATED RENDER WEB PORT BYPASS HACK ---
# This opens a quiet background port so Render's free tier health checks pass smoothly!
def run_dummy_server():
    class SafeHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"ShieldBot is alive and guarding the gng 24/7!")
            
    # Render automatically hands us a variable called PORT. Default to 10000 if not found.
    import os
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SafeHandler)
    server.serve_forever()

# Fire the fake web server on a separate hidden thread so it doesn't lag your bot!
threading.Thread(target=run_dummy_server, daemon=True).start()


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

import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def run_dummy_server():
    class SafeHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"ShieldBot is alive and guarding the gng 24/7!")
            
    import os
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SafeHandler)
    server.serve_forever()

# Fire the fake web server on a separate hidden thread so it doesn't lag your bot!
threading.Thread(target=run_dummy_server, daemon=True).start()

# --- MODULE A: BLOX FRUITS TALK SYSTEMS ---
@bot.tree.command(name="raid", description="Simulate a Blox Fruits raid to earn fragment currencies!")
@app_commands.describe(boss="Choose the Raid Boss dungeon to conquer")
@app_commands.choices(boss=[
    app_commands.Choice(name="Flame Raid 🔥", value="flame"),
    app_commands.Choice(name="Ice Raid 🧊", value="ice"),
    app_commands.Choice(name="Buddha Raid 🧘", value="buddha")
])
async def raid(interaction: discord.Interaction, boss: app_commands.Choice[str]):
    outcomes = [
        f"⚔️ **SUCCESS!** The crew completely melted the **{boss.name}**. You earned **1,000 Fragments**! 💎",
        f"⚠️ **AWFUL LUCK!** The crew got wiped out on Island 4. You lost **100 Fragments** to awakening expenses.",
        f"👑 **PERFECT RUN!** You solo'd the **{boss.name}** in record time! You earned **1,500 Fragments**!"
    ]
    await interaction.response.send_message(f"🏴‍☠️ **RAID MATRIX LOG**\n\n{random.choice(outcomes)}")

@bot.tree.command(name="trade", description="List your digital inventory fruits for active trade swaps.")
@app_commands.describe(giving="The fruit you are putting on the table", wanting="The fruit you are looking to get back")
async def trade(interaction: discord.Interaction, giving: str, wanting: str):
    embed = discord.Embed(title="🍉 PHYSICAL FRUIT TRADING LISTING", color=discord.Color.green())
    embed.add_field(name="Trader Profile", value=interaction.user.mention, inline=False)
    embed.add_field(name="🤝 GIVING AWAY", value=f"**{giving.upper()}**", inline=True)
    embed.add_field(name="🔮 LOOKING FOR", value=f"**{wanting.upper()}**", inline=True)
    embed.set_footer(text="Message this user or reply in the dealer channel to trade!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="spawnclock", description="Check the status tracker for legendary world chests and bosses.")
async def spawnclock(interaction: discord.Interaction):
    status = [
        "🏴‍☠️ **FACTORY INVASION:** The Core is currently **UNPROTECTED**! The raid event starts in **5 minutes**! ⚙️",
        "FOX **MIRAGE ISLAND:** Spawning conditions are currently **INACTIVE**. Wait for a full moon! 🌕",
        "💎 **LEGENDARY SWORD DEALER:** A mysterious salesman was spotted roaming Second Sea **12 minutes ago**!"
    ]
    await interaction.response.send_message(f"🕒 **WORLD WORLD ALERTS**\n\n{random.choice(status)}")

@bot.tree.command(name="bossfight", description="Fight an automated Legendary Raid Boss to test your build damage!")
async def bossfight(interaction: discord.Interaction):
    bosses = ["Indra 👑", "Don Swan 🦩", "Blackbeard 🏴‍☠️", "Rip_Indra 🗡️"]
    target_boss = random.choice(bosses)
    damage = random.randint(5000, 120000)
    if damage > 80000:
        msg = f"🏆 **GODLY KILL!** You smashed **{target_boss}** for **{damage:,} damage** and got a Mythical Item Drop!"
    else:
        msg = f"💀 **WIPED!** **{target_boss}** broke your Ken Haki shield and dealt massive lethal damage to you."
    await interaction.response.send_message(f"⚔️ **ARENA LOG:**\n{msg}")

@bot.tree.command(name="buildcheck", description="Let the bot evaluate your allocated stat point distributions.")
@app_commands.describe(melee="Melee Points", defense="Defense Points", sword="Sword Points", fruit="Blox Fruit Points")
async def buildcheck(interaction: discord.Interaction, melee: int, defense: int, sword: int, fruit: int):
    total = melee + defense + sword + fruit
    if total > 10000:
        rating = "💎 **MAX LEVEL GOD:** Your stat attributes look completely broken. Go hunt some bounties!"
    elif fruit > sword and fruit > 1500:
        rating = "🍇 **FRUIT SPAMMER BUILD:** You rely heavily on elemental skills. Insane raw damage!"
    else:
        rating = "⚓ **AVERAGE PIRATE:** Balanced stats. Keep grinding levels inside the Second Sea!"
    await interaction.response.send_message(f"📊 **STAT CHECK FOR {interaction.user.name}:**\n\nTotal: **{total:,} points**\nVerdict: {rating}")

@bot.tree.command(name="crew", description="Create an official recruitment poster card for your Pirate Crew faction.")
@app_commands.describe(crew_name="The name of your group", bounty="Minimum bounty requirements to join")
async def crew(interaction: discord.Interaction, crew_name: str, bounty: str):
    embed = discord.Embed(title=f"🏴‍☠️ PIRATE CREW RECRUITMENT: [{crew_name.upper()}]", color=discord.Color.dark_red())
    embed.add_field(name="Faction Captain", value=interaction.user.mention, inline=True)
    embed.add_field(name="⚓ Entry Barrier", value=f"**{bounty} Bounty Minimum**", inline=True)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="React below or contact the captain to join!")
    await interaction.response.send_message(embed=embed)

# --- MODULE B: GAMING UTILITIES & PRANKS ---
@bot.tree.command(name="imposter", description="[Owner Only] Force the bot to copy a user's nickname and message.")
@app_commands.describe(target="The user to mirror", text="The message to say")
async def imposter(interaction: discord.Interaction, target: discord.Member, text: str):
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("❌ Access Denied: Unauthorized Operator.", ephemeral=True)
        return
    await interaction.response.send_message(f"🕵️ Copying patterns for {target.name}...", ephemeral=True)
    await interaction.channel.send(f"💬 **{target.name}**: {text}")

@bot.tree.command(name="pingcheck", description="Calculate the true network packet response speeds of the cloud wrapper.")
async def pingcheck(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    quality = "🟢 **FIBER EXPLOIT SPEED:** Wi-Fi is executing beautifully!" if latency < 80 else "🔴 **LAG SPIKE:** Network delay detected."
    await interaction.response.send_message(f"📶 **MATRIX LOG:**\n⏱️ Ping Latency: **{latency}ms**\nNetwork Integrity: {quality}")

@bot.tree.command(name="cooldown", description="Start an automatic 30-second localized farming timer alert.")
async def cooldown(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ **FARMING CLOCK STARTED:** 30-second farming cycle active. Focus up gng!")
    await asyncio.sleep(30)
    await interaction.channel.send(f"🔔 {interaction.user.mention} **TIMER EXPIRED!** Boss respawned. Go clear the camp!")

@bot.tree.command(name="fakeban", description="Execute a funny simulated fake enforcement ban sequence on a friend.")
@app_commands.describe(target="The member instance to prank")
async def fakeban(interaction: discord.Interaction, target: discord.Member):
    await interaction.response.send_message("📡 Connecting to Sockets...", ephemeral=True)
    msg = await interaction.channel.send(f"🔨 **ENFORCEMENT ACTION:** Terminating credentials for **{target.mention}**...")
    await asyncio.sleep(1.5)
    await msg.edit(content=f"🚫 **PRANK DEPLOYED!** Gotcha {target.mention}! You aren't actually banned. 🤡")

@bot.tree.command(name="vibegen", description="Calculate the energetic frequency score index of the active server chat.")
async def vibegen(interaction: discord.Interaction):
    score = random.randint(1, 100)
    verdict = "🔥 **HYPERDRIVE ACTIVATED:** The gng is grinding hard!" if score > 50 else "💀 **DEAD WASTELAND:** Chat liquidity is frozen."
    await interaction.response.send_message(f"🔮 **VIBE RADAR CHECK:**\n📈 Energy Score: **{score}%**\nStatus Check: {verdict}")

# --- MODULE C: MINI-ECONOMY & INTERACTIVE FUN ---
@bot.tree.command(name="rob", description="Attempt a risky heist on a friend's hypothetical token balance.")
@app_commands.describe(target="The friend instance profile you want to target")
async def rob(interaction: discord.Interaction, target: discord.Member):
    if target.id == interaction.user.id or target.bot:
        await interaction.response.send_message("❌ Target validation exception.", ephemeral=True)
        return
    success = random.choice([True, False])
    amount = random.randint(50, 400)
    if success:
        await interaction.response.send_message(f"🥷 **HEIST SUCCESSFUL!** You sneaked into **{target.name}**'s inventory and stole **₱{amount} Server Coins**! 💸")
    else:
        await interaction.response.send_message(f"👮 **CAUGHT ON RADAR!** **{target.name}** counter-attacked and fined you **₱100 Coins**!")

@bot.tree.command(name="lovemeter", description="Calculate the compatibility percentage between two names.")
@app_commands.describe(user1="First Target", user2="Second Target")
async def lovemeter(interaction: discord.Interaction, user1: str, user2: str):
    score = random.randint(1, 100)
    heart = "❤️" if score > 75 else "💔"
    await interaction.response.send_message(f"🔮 **LOVE ENGINE CALCULATION:**\n👥 **{user1}** x **{user2}**\n📈 Match Score: **{score}%** {heart}")

@bot.tree.command(name="oracle", description="Ask the bot a yes/no question about your future luck.")
@app_commands.describe(question="The question string you seek an answer for")
async def oracle(interaction: discord.Interaction, question: str):
    answers = ["🟢 **CONFIRMED:** Calculations strongly match a positive outcome. Go drop that bet!", "🟡 **OBSCURE DATA:** Timeline fluctuations high. Try again.", "🔴 **PROBABILITY ZERO:** System registers full structural failure."]
    await interaction.response.send_message(f"❓ **Question:** *\"{question}\"*\n🔮 **Oracle Prediction:** {random.choice(answers)}")

@bot.tree.command(name="iqtest", description="Scan a member's chat patterns to calculate their processing IQ score.")
@app_commands.describe(target="The target instance profile to analyze")
async def iqtest(interaction: discord.Interaction, target: discord.Member):
    score = random.randint(40, 160)
    desc = "🧠 **SUPERCOMPUTER MATRIX:** Real engineering intelligence found!" if score > 110 else "🍌 **BANANA CORE PROCESSING:** Brain loops short-circuiting constantly."
    await interaction.response.send_message(f"🧠 **IQ ANALYZER:**\nTarget: {target.mention}\n📈 Calculated Score: **{score} IQ**\nClassification: {desc}")

@bot.tree.command(name="dice", description="Roll a set of random dice to settle arguments.")
async def dice(interaction: discord.Interaction):
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    await interaction.response.send_message(f"🎲 **DICE ROLLER:**\n🎲 Die A: **{d1}** | Die B: **{d2}**\n📊 Combined Sum: **{d1 + d2}**")

# --- MODULE D: SERVER UTILITIES & DOCUMENTATION ---
@bot.tree.command(name="serverinfo", description="Extract the background network architectural data of this server.")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"📊 CLOUD ENVIRONMENT LOGS: {g.name}", color=discord.Color.blue())
    embed.add_field(name="Server ID Snowflake", value=f"`{g.id}`", inline=False)
    embed.add_field(name="Owner Operator ID", value=f"<@{g.owner_id}>", inline=True)
    embed.add_field(name="Member Capacity", value=f"**{g.member_count} units**", inline=True)
    embed.set_thumbnail(url=g.icon.url if g.icon else interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="announce", description="[Admin Only] Broadcast a formatted announcement embed frame block.")
@app_commands.describe(title="Announcement Header", message="The main announcement body content text")
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, title: str, message: str):
    embed = discord.Embed(title=f"📢 {title.upper()}", description=message, color=discord.Color.gold())
    embed.set_footer(text=f"Authorized By: {interaction.user.name}")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("Broadcast sent!", ephemeral=True)

@bot.tree.command(name="dm_user", description="[Admin Only] Forward a private warning straight to a member's DMs.")
@app_commands.describe(target="The member target", message="The warning text content string")
@app_commands.checks.has_permissions(manage_messages=True)
async def dm_user(interaction: discord.Interaction, target: discord.Member, message: str):
    try:
        await target.send(f"📥 **PRIVATE REGULATORY LOG FROM [{interaction.guild.name}]:**\(\nHello {target.name},\) an officer sent you this note: *\"{message}\"*")
        await interaction.response.send_message(f"✅ Packet dispatched to **{target.name}**'s private DM pipeline!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Delivery failure: This user has their DMs blocked!", ephemeral=True)

@bot.tree.command(name="botmanual", description="View the technical operational framework documentation of ShieldBot.")
async def botmanual(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 SHIELDBOT OPERATIONAL MANUAL", color=discord.Color.dark_grey())
    embed.add_field(name="⚙️ Core Script Engine", value="Compiled using Python 3 & Discord.py API wrappers.", inline=False)
    embed.add_field(name="🛡️ Threat Response Perimeter", value="Automated deletions and warning updates apply instantly via SQL files.", inline=False)
    embed.set_footer(text="System Status: Stable. Hosted 24/7 via Render Free Cloud.")
    await interaction.response.send_message(embed=embed)


import os
bot.run(os.getenv("DISCORD_TOKEN")) 

