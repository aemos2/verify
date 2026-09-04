import discord
from discord.ext import commands, tasks
import requests
import json
import asyncio
from datetime import datetime
import logging
from config import load_config, save_config

class ExecutorChecker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        
        # Load settings from config
        self.executor_config = self.config.get("executor_check", {})
        self.enabled = self.executor_config.get("enabled", True)
        self.check_interval = self.executor_config.get("check_interval_hours", 1)
        self.executors_to_check = self.executor_config.get("executors_to_check", [])
        self.platform_groups = self.executor_config.get("platform_groups", {})
        
        # API configuration
        self.api_base_url = "https://weao.xyz/api/status/exploits"
        self.api_versions_url = "https://weao.xyz/api/versions"
        self.last_known_rbx_version = None
        self.status_cache = {}
        
        # Start the background task if enabled
        if self.enabled:
            self.check_updates.start()
            logging.info("Executor checker enabled and running")
        else:
            logging.info("Executor checker is disabled in config")
    
    def cog_unload(self):
        self.check_updates.cancel()
    
    @tasks.loop(hours=1)
    async def check_updates(self):
        """Background task to check for Roblox updates and executor status changes"""
        if not self.enabled:
            return
        
        try:
            logging.info("Running scheduled executor status check...")
            await self.check_executor_status(notify_on_change=True)
        except Exception as e:
            logging.error(f"Error in scheduled check: {e}")
    
    @check_updates.before_loop
    async def before_check_updates(self):
        """Wait for bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()
    
    async def fetch_data(self, url):
        """Helper function to fetch and parse JSON data"""
        try:
            async with requests.Session() as session:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, session.get, url
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logging.error(f"Error fetching data from {url}: {e}")
            return None
    
    async def check_roblox_update(self):
        """Check if a new Roblox update has been released"""
        current_data = await self.fetch_data(f"{self.api_versions_url}/current")
        past_data = await self.fetch_data(f"{self.api_versions_url}/past")
        
        if not current_data or not past_data:
            return None, None
        
        current_version = current_data.get("Windows")
        past_version = past_data.get("Windows")
        
        return current_version, past_version
    
    async def get_executor_compatibility(self, executor_name, current_rbx_version, past_rbx_version):
        """Check an executor's compatibility with current Roblox version"""
        # Handle URL encoding for executor names with spaces
        encoded_name = executor_name.replace(" ", "%20")
        executor_data = await self.fetch_data(f"{self.api_base_url}/{encoded_name}")
        if not executor_data:
            return None
        
        executor_version = executor_data.get('rbxversion')
        
        # Determine if it's a Windows, Mac, Android, or iOS executor
        platform = executor_data.get('platform', 'Unknown')
        extype = executor_data.get('extype', 'Unknown')
        
        status_info = {
            'name': executor_name,
            'version': executor_data.get('version', 'N/A'),
            'updated_date': executor_data.get('updatedDate', 'N/A'),
            'detected': executor_data.get('detected', False),
            'compatible_version': executor_version,
            'is_compatible': executor_version == current_rbx_version if executor_version and current_rbx_version else False,
            'needs_update': executor_version == past_rbx_version if executor_version and past_rbx_version else False,
            'update_status': executor_data.get('updateStatus', False),
            'free': executor_data.get('free', False),
            'platform': platform,
            'extype': extype,
            'cost': executor_data.get('cost', 'N/A'),
            'sunc_percentage': executor_data.get('suncPercentage', 'N/A'),
            'unc_percentage': executor_data.get('uncPercentage', 'N/A'),
            'detection_reason': executor_data.get('detectionReason', 'N/A'),
            'websitelink': executor_data.get('websitelink', 'N/A'),
            'discordlink': executor_data.get('discordlink', 'N/A')
        }
        
        return status_info
    
    async def check_executor_status(self, notify_on_change=False):
        """Main function to check all executors and send notifications if needed"""
        current_rbx_ver, past_rbx_ver = await self.check_roblox_update()
        
        if not current_rbx_ver:
            return "Could not retrieve Roblox version data."
        
        # Check if Roblox updated
        roblox_updated = self.last_known_rbx_version != current_rbx_ver
        if roblox_updated:
            self.last_known_rbx_version = current_rbx_ver
            logging.info(f"Roblox updated from {past_rbx_ver} to {current_rbx_ver}")
            
            # Send notification about Roblox update
            if notify_on_change:
                await self.send_roblox_update_notification(current_rbx_ver, past_rbx_ver)
        
        # Prepare status report
        report = []
        working_executors = []
        patched_executors = []
        new_statuses = {}
        
        for executor in self.executors_to_check:
            status = await self.get_executor_compatibility(executor, current_rbx_ver, past_rbx_ver)
            if status:
                new_statuses[executor] = status
                
                # Check if status changed (for notifications)
                old_status = self.status_cache.get(executor)
                status_changed = old_status and (
                    old_status.get('is_compatible') != status['is_compatible'] or
                    old_status.get('detected') != status['detected']
                )
                
                if notify_on_change and status_changed:
                    await self.send_status_change_notification(executor, status, old_status)
                
                # Categorize executors
                if status['is_compatible']:
                    working_executors.append(executor)
                elif status['needs_update']:
                    patched_executors.append(executor)
        
        # Update cache
        self.status_cache = new_statuses
        
        # Prepare summary report
        if roblox_updated:
            summary = f"**🚨 Roblox Updated!**\nPast: `{past_rbx_ver}` → Current: `{current_rbx_ver}`\n\n"
        else:
            summary = f"**✅ No New Roblox Update** (Current: `{current_rbx_ver}`)\n\n"
        
        summary += f"**Working Executors:** {len(working_executors)}\n"
        summary += f"**Patched Executors:** {len(patched_executors)}\n\n"
        
        # Add working executors
        if working_executors:
            summary += "**✅ Working:** " + ", ".join(working_executors[:10]) + ("..." if len(working_executors) > 10 else "") + "\n"
        
        # Add patched executors
        if patched_executors:
            summary += "**❌ Patched:** " + ", ".join(patched_executors[:10]) + ("..." if len(patched_executors) > 10 else "")
        
        return summary
    
    def get_channel(self):
        """Get the notification channel from config"""
        channel_id = self.config.get("executor_update_channel_id")
        if channel_id:
            return self.bot.get_channel(channel_id)
        return None
    
    def get_role(self):
        """Get the notification role from config"""
        role_id = self.config.get("executor_update_role_id")
        if role_id:
            return role_id
        return None
    
    async def send_roblox_update_notification(self, current_version, past_version):
        """Send a notification when Roblox updates"""
        channel = self.get_channel()
        if not channel:
            return
        
        role = self.get_role()
        mention = f"<@&{role}> " if role else ""
        
        embed = discord.Embed(
            title="🚨 Roblox Update Detected!",
            description=f"{mention}All executors need to be checked for compatibility.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Previous Version",
            value=f"`{past_version}`",
            inline=True
        )
        
        embed.add_field(
            name="Current Version",
            value=f"`{current_version}`",
            inline=True
        )
        
        embed.set_footer(text="Checking executor compatibility...")
        
        await channel.send(content=mention if role else None, embed=embed)
    
    async def send_status_change_notification(self, executor_name, new_status, old_status):
        """Send a notification when an executor's status changes"""
        channel = self.get_channel()
        if not channel:
            return
        
        # Determine color based on status change
        if new_status['is_compatible'] and not old_status.get('is_compatible', False):
            color = discord.Color.green()  # Fixed/Updated
        elif not new_status['is_compatible'] and old_status.get('is_compatible', True):
            color = discord.Color.red()  # Patched/Outdated
        else:
            color = discord.Color.blue()  # Other change
        
        embed = discord.Embed(
            title=f"🔄 Executor Status Changed: {executor_name}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Add platform and type info
        embed.add_field(
            name="Platform/Type",
            value=f"{new_status['platform']} ({new_status['extype']})",
            inline=True
        )
        
        embed.add_field(
            name="Version",
            value=f"{new_status['version']}",
            inline=True
        )
        
        embed.add_field(
            name="Cost",
            value=f"{new_status['cost']}",
            inline=True
        )
        
        embed.add_field(
            name="Previous Status",
            value=f"Compatible: {old_status.get('is_compatible', 'Unknown')}\nDetected: {old_status.get('detected', 'Unknown')}",
            inline=True
        )
        
        embed.add_field(
            name="New Status",
            value=f"Compatible: {new_status['is_compatible']}\nDetected: {new_status['detected']}",
            inline=True
        )
        
        embed.add_field(
            name="Last Updated",
            value=f"{new_status['updated_date']}",
            inline=False
        )
        
        if new_status['websitelink'] != 'N/A':
            embed.add_field(
                name="Website",
                value=f"[Link]({new_status['websitelink']})",
                inline=True
            )
        
        if new_status['discordlink'] != 'N/A':
            embed.add_field(
                name="Discord",
                value=f"[Invite]({new_status['discordlink']})",
                inline=True
            )
        
        await channel.send(embed=embed)
    
    # --- Discord Commands ---
    
    @commands.command(name='check', aliases=['executor', 'status'])
    async def check_executor_command(self, ctx, *, executor_name: str = None):
        """Check executor compatibility with current Roblox version
        Usage: !check [executor_name]
        Example: !check Solara
        Example: !check (to check all executors)"""
        
        # Sending typing indicator
        async with ctx.typing():
            if executor_name:
                # Check single executor
                current_rbx_ver, past_rbx_ver = await self.check_roblox_update()
                if not current_rbx_ver:
                    await ctx.send("❌ Could not retrieve Roblox version data.")
                    return
                
                # Try to find the executor with proper capitalization
                found_executor = None
                for exe in self.executors_to_check:
                    if exe.lower() == executor_name.lower():
                        found_executor = exe
                        break
                
                if not found_executor:
                    await ctx.send(f"❌ Could not find executor: `{executor_name}`")
                    return
                
                status = await self.get_executor_compatibility(found_executor, current_rbx_ver, past_rbx_ver)
                if not status:
                    await ctx.send(f"❌ Could not retrieve data for: `{found_executor}`")
                    return
                
                embed = discord.Embed(
                    title=f"📊 Executor Status: {found_executor}",
                    color=discord.Color.green() if status['is_compatible'] else discord.Color.red()
                )
                
                embed.add_field(name="Version", value=status['version'], inline=True)
                embed.add_field(name="Last Updated", value=status['updated_date'], inline=True)
                embed.add_field(name="Platform", value=status['platform'], inline=True)
                embed.add_field(name="Type", value=status['extype'], inline=True)
                embed.add_field(name="Cost", value=status['cost'], inline=True)
                embed.add_field(name="Free", value="Yes ✅" if status['free'] else "No ❌", inline=True)
                embed.add_field(
                    name="Detected by Roblox", 
                    value="⚠️ Yes" if status['detected'] else "✅ No", 
                    inline=True
                )
                embed.add_field(
                    name="Status", 
                    value="✅ Working (Compatible)" if status['is_compatible'] else "❌ Patched/Outdated", 
                    inline=True
                )
                embed.add_field(
                    name="Roblox Version", 
                    value=status['compatible_version'] or "Unknown", 
                    inline=False
                )
                
                if status['detection_reason'] != 'N/A':
                    embed.add_field(
                        name="Detection Info",
                        value=status['detection_reason'],
                        inline=False
                    )
                
                if status['sunc_percentage'] != 'N/A':
                    embed.add_field(
                        name="sUNC",
                        value=f"{status['sunc_percentage']}%",
                        inline=True
                    )
                
                if status['unc_percentage'] != 'N/A':
                    embed.add_field(
                        name="UNC",
                        value=f"{status['unc_percentage']}%",
                        inline=True
                    )
                
                await ctx.send(embed=embed)
            else:
                # Check all executors
                report = await self.check_executor_status(notify_on_change=False)
                if len(report) > 1900:  # Discord character limit
                    # Split into multiple messages if too long
                    chunks = [report[i:i+1900] for i in range(0, len(report), 1900)]
                    for chunk in chunks:
                        await ctx.send(chunk)
                else:
                    await ctx.send(report)
    
    @commands.command(name='checkall')
    async def check_all_command(self, ctx):
        """Check status of all configured executors (detailed view)"""
        async with ctx.typing():
            current_rbx_ver, past_rbx_ver = await self.check_roblox_update()
            if not current_rbx_ver:
                await ctx.send("❌ Could not retrieve Roblox version data.")
                return
            
            embed = discord.Embed(
                title=f"🔄 Roblox Version Status",
                description=f"**Current:** `{current_rbx_ver}`\n**Past:** `{past_rbx_ver or 'N/A'}`",
                color=discord.Color.blue()
            )
            
            # Group executors by platform using config
            for platform_name, executor_list in self.platform_groups.items():
                if not executor_list:
                    continue
                    
                platform_status = []
                for executor in executor_list:
                    # Handle duplicate executor names (like Delta on Android and iOS)
                    # We'll check if it exists in our main list
                    if executor not in self.executors_to_check:
                        continue
                    
                    status = await self.get_executor_compatibility(executor, current_rbx_ver, past_rbx_ver)
                    if status:
                        status_emoji = "✅" if status['is_compatible'] else "❌" if status['needs_update'] else "❓"
                        detected_emoji = "⚠️" if status['detected'] else "✅"
                        platform_status.append(f"{status_emoji} {executor} (v{status['version']})")
                
                if platform_status:
                    display_name = platform_name.replace('_', ' ').title()
                    embed.add_field(
                        name=f"📱 {display_name} ({len(platform_status)})",
                        value="\n".join(platform_status[:10]) + ("..." if len(platform_status) > 10 else ""),
                        inline=False
                    )
            
            await ctx.send(embed=embed)
    
    @commands.command(name='listexecutors')
    async def list_executors_command(self, ctx, platform: str = None):
        """List all available executors, optionally filtered by platform
        Usage: !listexecutors [platform]
        Platforms: windows_internal, windows_external, mac, android, ios"""
        
        embed = discord.Embed(
            title="📋 Available Executors",
            color=discord.Color.blue()
        )
        
        if not platform:
            # Show all platforms from config
            total = 0
            for platform_name, executor_list in self.platform_groups.items():
                if executor_list:
                    display_name = platform_name.replace('_', ' ').title()
                    embed.add_field(
                        name=f"{display_name} ({len(executor_list)})",
                        value=", ".join(executor_list[:15]) + ("..." if len(executor_list) > 15 else ""),
                        inline=False
                    )
                    total += len(executor_list)
            embed.set_footer(text=f"Total Executors: {total}")
        else:
            # Filter by platform
            platform_lower = platform.lower()
            if platform_lower in self.platform_groups:
                executor_list = self.platform_groups[platform_lower]
                display_name = platform_lower.replace('_', ' ').title()
                embed.add_field(
                    name=f"{display_name} ({len(executor_list)})",
                    value=", ".join(executor_list),
                    inline=False
                )
            else:
                await ctx.send(f"❌ Invalid platform. Options: {', '.join(self.platform_groups.keys())}")
                return
        
        await ctx.send(embed=embed)
    
    @commands.command(name='checkplatform')
    async def check_platform_command(self, ctx, platform: str):
        """Check status of all executors on a specific platform
        Usage: !checkplatform windows_internal
        Options: windows_internal, windows_external, mac, android, ios"""
        
        platform_lower = platform.lower()
        if platform_lower not in self.platform_groups:
            await ctx.send(f"❌ Invalid platform. Options: {', '.join(self.platform_groups.keys())}")
            return
        
        executors_to_check = self.platform_groups[platform_lower]
        if not executors_to_check:
            await ctx.send(f"❌ No executors found for platform: {platform}")
            return
        
        async with ctx.typing():
            current_rbx_ver, past_rbx_ver = await self.check_roblox_update()
            if not current_rbx_ver:
                await ctx.send("❌ Could not retrieve Roblox version data.")
                return
            
            display_name = platform_lower.replace('_', ' ').title()
            embed = discord.Embed(
                title=f"📱 {display_name} Executor Status",
                description=f"Roblox Version: `{current_rbx_ver}`",
                color=discord.Color.blue()
            )
            
            working = []
            patched = []
            unknown = []
            
            for executor in executors_to_check:
                if executor not in self.executors_to_check:
                    continue
                    
                status = await self.get_executor_compatibility(executor, current_rbx_ver, past_rbx_ver)
                if status:
                    if status['is_compatible']:
                        working.append(f"✅ {executor} (v{status['version']})")
                    elif status['needs_update']:
                        patched.append(f"❌ {executor} (v{status['version']})")
                    else:
                        unknown.append(f"❓ {executor} (v{status['version']})")
            
            if working:
                embed.add_field(name=f"✅ Working ({len(working)})", value="\n".join(working[:10]) + ("..." if len(working) > 10 else ""), inline=False)
            if patched:
                embed.add_field(name=f"❌ Patched/Outdated ({len(patched)})", value="\n".join(patched[:10]) + ("..." if len(patched) > 10 else ""), inline=False)
            if unknown:
                embed.add_field(name=f"❓ Unknown Status ({len(unknown)})", value="\n".join(unknown[:10]) + ("..." if len(unknown) > 10 else ""), inline=False)
            
            await ctx.send(embed=embed)
    
    @commands.command(name='setexecutorchannel')
    @commands.has_permissions(administrator=True)
    async def set_executor_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for executor update notifications
        Usage: !setexecutorchannel #channel"""
        if not channel:
            channel = ctx.channel
        
        self.config["executor_update_channel_id"] = channel.id
        save_config(self.config)
        await ctx.send(f"✅ Executor update channel set to {channel.mention}")
    
    @commands.command(name='setexecutorrole')
    @commands.has_permissions(administrator=True)
    async def set_executor_role(self, ctx, role: discord.Role = None):
        """Set the role to mention for executor update notifications
        Usage: !setexecutorrole @role"""
        if not role:
            role = None
        
        self.config["executor_update_role_id"] = role.id if role else None
        save_config(self.config)
        await ctx.send(f"✅ Executor update role set to {role.mention if role else 'None'}")

async def setup(bot):
    await bot.add_cog(ExecutorChecker(bot))
