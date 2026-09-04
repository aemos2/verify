import json
import os
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks


API_URL = "https://whatexpsare.online/api/status/exploits"

CONFIG_FILE = "data/executor_checker.json"

CHECK_INTERVAL = 60


class ExecutorChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        os.makedirs("data", exist_ok=True)

        self.config = self.load_json(CONFIG_FILE)

        # guild_id -> executor_id -> state
        self.previous_states = self.config.get(
            "states",
            {}
        )

        self.check_executors.start()

    def cog_unload(self):
        self.check_executors.cancel()

    # =========================================================
    # JSON
    # =========================================================

    def load_json(self, path):

        if not os.path.exists(path):
            return {}

        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)

        except Exception:
            return {}

    def save_json(self):

        data = {
            "guilds": self.config.get(
                "guilds",
                {}
            ),
            "states": self.previous_states
        }

        with open(
            CONFIG_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4
            )

    # =========================================================
    # API
    # =========================================================

    async def fetch_executors(self):

        headers = {
            "User-Agent": "WEAO-3PService",
            "Accept": "application/json"
        }

        timeout = aiohttp.ClientTimeout(
            total=20
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                API_URL,
                headers=headers
            ) as response:

                if response.status != 200:
                    raise RuntimeError(
                        f"HTTP {response.status}"
                    )

                data = await response.json()

                if not isinstance(data, list):
                    raise RuntimeError(
                        "Invalid API response"
                    )

                return data

    # =========================================================
    # SETUP COMMAND
    # =========================================================

    @app_commands.command(
        name="executorsetup",
        description="Set up automatic executor status updates."
    )
    @app_commands.describe(
        channel="Channel where executor updates will be posted.",
        ping_role="Role to ping when an update is detected."
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def executorsetup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        ping_role: discord.Role | None = None
    ):

        guild_id = str(
            interaction.guild.id
        )

        self.config.setdefault(
            "guilds",
            {}
        )

        self.config["guilds"][guild_id] = {
            "channel_id": channel.id,
            "role_id": (
                ping_role.id
                if ping_role
                else None
            )
        }

        self.save_json()

        role_text = (
            ping_role.mention
            if ping_role
            else "No role"
        )

        embed = discord.Embed(
            title="✅ Executor Updater Configured",
            description=(
                f"Automatic executor updates will be "
                f"posted in {channel.mention}."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Update Channel",
            value=channel.mention,
            inline=True
        )

        embed.add_field(
            name="Update Ping",
            value=role_text,
            inline=True
        )

        embed.add_field(
            name="Check Interval",
            value="Every 60 seconds",
            inline=True
        )

        embed.set_footer(
            text="Powered by WEAO"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================================================
    # CHECKER
    # =========================================================

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_executors(self):

        try:
            executors = await self.fetch_executors()

        except Exception as e:

            print(
                f"[Executor Checker] API error: {e}"
            )

            return

        guild_configs = self.config.get(
            "guilds",
            {}
        )

        if not guild_configs:
            return

        # -----------------------------------------------------
        # Process every configured guild
        # -----------------------------------------------------

        for guild_id, guild_config in guild_configs.items():

            channel_id = guild_config.get(
                "channel_id"
            )

            if not channel_id:
                continue

            channel = self.bot.get_channel(
                channel_id
            )

            if channel is None:

                try:
                    channel = await self.bot.fetch_channel(
                        channel_id
                    )

                except Exception:
                    continue

            role_id = guild_config.get(
                "role_id"
            )

            # State storage for this guild
            guild_states = self.previous_states.setdefault(
                guild_id,
                {}
            )

            # -------------------------------------------------
            # Process executors
            # -------------------------------------------------

            for executor in executors:

                executor_id = str(
                    executor.get(
                        "trackerId"
                    )
                    or executor.get(
                        "_id"
                    )
                    or executor.get(
                        "title"
                    )
                )

                name = executor.get(
                    "title",
                    "Unknown"
                )

                version = executor.get(
                    "version",
                    "Unknown"
                )

                rbxversion = executor.get(
                    "rbxversion",
                    "Unknown"
                )

                detected = bool(
                    executor.get(
                        "detected",
                        False
                    )
                )

                update_status = bool(
                    executor.get(
                        "updateStatus",
                        False
                    )
                )

                updated_date = executor.get(
                    "updatedDate",
                    "Unknown"
                )

                old = guild_states.get(
                    executor_id
                )

                # -------------------------------------------------
                # First time seeing executor
                # -------------------------------------------------

                if old is None:

                    guild_states[executor_id] = {
                        "title": name,
                        "version": version,
                        "rbxversion": rbxversion,
                        "detected": detected,
                        "updatedDate": updated_date
                    }

                    continue

                old_version = old.get(
                    "version"
                )

                old_rbxversion = old.get(
                    "rbxversion"
                )

                old_detected = old.get(
                    "detected",
                    False
                )

                # -------------------------------------------------
                # Detect actual version/update change
                # -------------------------------------------------

                version_changed = (
                    old_version != version
                    and version != "Unknown"
                )

                roblox_version_changed = (
                    old_rbxversion != rbxversion
                    and rbxversion != "Unknown"
                )

                became_detected = (
                    old_detected is False
                    and detected is True
                )

                became_undetected = (
                    old_detected is True
                    and detected is False
                )

                # -------------------------------------------------
                # Send update notification
                # -------------------------------------------------

                if (
                    version_changed
                    or roblox_version_changed
                    or became_detected
                    or became_undetected
                ):

                    embed = self.create_embed(
                        executor=executor,
                        version_changed=version_changed,
                        became_detected=became_detected,
                        became_undetected=became_undetected
                    )

                    content = ""

                    if role_id:

                        role = (
                            interaction_role
                            if False
                            else None
                        )

                        guild = getattr(
                            channel,
                            "guild",
                            None
                        )

                        if guild:

                            role = guild.get_role(
                                role_id
                            )

                            if role:
                                content = role.mention

                    try:

                        await channel.send(
                            content=content or None,
                            embed=embed,
                            view=self.create_buttons(
                                executor
                            ),
                            allowed_mentions=discord.AllowedMentions(
                                roles=True
                            )
                        )

                        print(
                            f"[Executor Checker] "
                            f"{name} changed "
                            f"in guild {guild_id}"
                        )

                    except Exception as e:

                        print(
                            f"[Executor Checker] "
                            f"Discord error: {e}"
                        )

                # -------------------------------------------------
                # Save latest state
                # -------------------------------------------------

                guild_states[executor_id] = {
                    "title": name,
                    "version": version,
                    "rbxversion": rbxversion,
                    "detected": detected,
                    "updatedDate": updated_date
                }

        self.save_json()

    # =========================================================
    # EMBED
    # =========================================================

    def create_embed(
        self,
        executor,
        version_changed=False,
        became_detected=False,
        became_undetected=False
    ):

        name = executor.get(
            "title",
            "Unknown"
        )

        version = executor.get(
            "version",
            "Unknown"
        )

        rbxversion = executor.get(
            "rbxversion",
            "Unknown"
        )

        updated_date = executor.get(
            "updatedDate",
            "Unknown"
        )

        detected = executor.get(
            "detected",
            False
        )

        platform = executor.get(
            "platform",
            "Unknown"
        )

        # -----------------------------------------------------
        # Title / color
        # -----------------------------------------------------

        if became_detected:

            title = f"🚩 {name} Detected"
            color = discord.Color.red()

        elif became_undetected:

            title = f"🟢 {name} Undetected"
            color = discord.Color.green()

        else:

            title = f"🟨 {name} Updated"
            color = discord.Color.orange()

        embed = discord.Embed(
            title=title,
            color=color
        )

        # -----------------------------------------------------
        # Version
        # -----------------------------------------------------

        embed.add_field(
            name="Version",
            value=f"`{version}`",
            inline=False
        )

        # -----------------------------------------------------
        # Roblox Version
        # -----------------------------------------------------

        embed.add_field(
            name="Roblox Version",
            value=f"`{rbxversion}`",
            inline=False
        )

        # -----------------------------------------------------
        # Last Updated
        # -----------------------------------------------------

        embed.add_field(
            name="Last Updated",
            value=f"`{updated_date}`",
            inline=False
        )

        # -----------------------------------------------------
        # Status
        # -----------------------------------------------------

        if detected:
            status = "🚩 Detected"
        else:
            status = "🟢 Undetected"

        embed.add_field(
            name="Status",
            value=status,
            inline=False
        )

        # -----------------------------------------------------
        # Footer
        # -----------------------------------------------------

        embed.set_footer(
            text=(
                f"Powered by WEAO • "
                f"{platform} • "
                f"Automatic Status Monitor"
            )
        )

        # -----------------------------------------------------
        # Logo
        # -----------------------------------------------------

        slug = executor.get(
            "slug",
            {}
        )

        logo = (
            slug.get("logo")
            if isinstance(slug, dict)
            else None
        )

        if logo:
            embed.set_thumbnail(
                url=logo
            )

        return embed

    # =========================================================
    # BUTTONS
    # =========================================================

    def create_buttons(self, executor):

        view = discord.ui.View(
            timeout=None
        )

        website = executor.get(
            "websitelink"
        )

        discord_link = executor.get(
            "discordlink"
        )

        purchase = executor.get(
            "purchaselink"
        )

        if website:

            view.add_item(
                discord.ui.Button(
                    label="Website",
                    style=discord.ButtonStyle.link,
                    url=website,
                    emoji="🔗"
                )
            )

        if discord_link:

            view.add_item(
                discord.ui.Button(
                    label="Discord",
                    style=discord.ButtonStyle.link,
                    url=discord_link,
                    emoji="💬"
                )
            )

        if purchase:

            view.add_item(
                discord.ui.Button(
                    label="Purchase",
                    style=discord.ButtonStyle.link,
                    url=purchase,
                    emoji="🛒"
                )
            )

        return view

    # =========================================================
    # READY
    # =========================================================

    @check_executors.before_loop
    async def before_checker(self):

        await self.bot.wait_until_ready()

        print(
            "[Executor Checker] "
            "Automatic checker started."
        )


async def setup(bot):

    await bot.add_cog(
        ExecutorChecker(bot)
    )
