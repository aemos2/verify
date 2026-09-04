import random
import string

import discord
from discord import app_commands
from discord.ext import commands

from config import load_config, save_config


def generate_code():
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choices(characters, k=6))


class CaptchaModal(discord.ui.Modal, title="Captcha"):
    answer = discord.ui.TextInput(
        label="Enter the code",
        placeholder="Enter the code shown above",
        min_length=6,
        max_length=6,
        required=True
    )

    def __init__(self, bot, expected_code):
        super().__init__()
        self.bot = bot
        self.expected_code = expected_code

    async def on_submit(self, interaction: discord.Interaction):
        if self.answer.value.strip().upper() != self.expected_code:
            await interaction.response.send_message(
                "Incorrect code.",
                ephemeral=True
            )
            return

        config = load_config()
        role_id = config.get("verify_role_id")

        if not role_id:
            await interaction.response.send_message(
                "Verification has not been configured.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message(
                "The verification role no longer exists.",
                ephemeral=True
            )
            return

        member = interaction.user

        if role in member.roles:
            await interaction.response.send_message(
                "You are already verified.",
                ephemeral=True
            )
            return

        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message(
                "I cannot assign the verification role. Move my bot role above it.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(
                role,
                reason="Completed verification captcha"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to assign the verification role.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Verification successful.",
            ephemeral=True
        )

        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = interaction.guild.get_channel(log_channel_id)

            if channel:
                embed = discord.Embed(
                    title="Verification",
                    description=f"{member.mention} completed verification.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(
                    name="User ID",
                    value=str(member.id)
                )

                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass


class CaptchaView(discord.ui.View):
    def __init__(self, bot, code):
        super().__init__(timeout=120)
        self.bot = bot
        self.code = code

    @discord.ui.button(
        label="Submit Captcha",
        style=discord.ButtonStyle.primary
    )
    async def submit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            CaptchaModal(self.bot, self.code)
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class VerifyView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        custom_id="verification:verify"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        config = load_config()
        role_id = config.get("verify_role_id")

        if not role_id:
            await interaction.response.send_message(
                "Verification has not been configured.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message(
                "The verification role no longer exists.",
                ephemeral=True
            )
            return

        if role in interaction.user.roles:
            await interaction.response.send_message(
                "You are already verified.",
                ephemeral=True
            )
            return

        code = generate_code()

        embed = discord.Embed(
            title="Captcha",
            description=(
                "Enter the code shown below.\n\n"
                f"**{code}**"
            ),
            color=discord.Color.blurple()
        )

        view = CaptchaView(self.bot, code)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


class Verification(commands.Cog):
    verify_group = app_commands.Group(
        name="verify",
        description="Verification system commands"
    )

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerifyView(bot))

    @verify_group.command(
        name="setrole",
        description="Set the role given after verification."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        if role.is_default():
            await interaction.response.send_message(
                "The @everyone role cannot be used.",
                ephemeral=True
            )
            return

        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message(
                "I cannot assign that role. Move my bot role above it.",
                ephemeral=True
            )
            return

        config = load_config()
        config["verify_role_id"] = role.id
        save_config(config)

        await interaction.response.send_message(
            f"Verification role set to {role.mention}.",
            ephemeral=True
        )

    @verify_group.command(
        name="setlogs",
        description="Set the verification log channel."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlogs(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        config = load_config()
        config["log_channel_id"] = channel.id
        save_config(config)

        await interaction.response.send_message(
            f"Verification logs set to {channel.mention}.",
            ephemeral=True
        )

    @verify_group.command(
        name="setup",
        description="Create the verification panel."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction):
        config = load_config()
        role_id = config.get("verify_role_id")

        if not role_id:
            await interaction.response.send_message(
                "Set the verification role first with /verify setrole.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message(
                "The configured verification role no longer exists.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Server Verification",
            description="Click Verify to begin verification.",
            color=discord.Color.blurple()
        )

        await interaction.channel.send(
            embed=embed,
            view=VerifyView(self.bot)
        )

        await interaction.response.send_message(
            "Verification panel created.",
            ephemeral=True
        )

    @verify_group.command(
        name="status",
        description="Show verification settings."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        config = load_config()

        role = (
            interaction.guild.get_role(config["verify_role_id"])
            if config.get("verify_role_id")
            else None
        )

        channel = (
            interaction.guild.get_channel(config["log_channel_id"])
            if config.get("log_channel_id")
            else None
        )

        embed = discord.Embed(
            title="Verification Status",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Role",
            value=role.mention if role else "Not configured",
            inline=False
        )
        embed.add_field(
            name="Logs",
            value=channel.mention if channel else "Not configured",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Verification(bot))
