from discord.ext import commands
import discord
#

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            activity=discord.CustomActivity(name="!help"),
            intents=discord.Intents.all(),
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

        # Load the 'music' cog
        await self.load_extension('cogs.music')


        # Other way to automatically add cogs
        #for filename in os.listdir("./cogs"):
            #if filename.endswith(".py"):
                #self.load_extension(f"cogs.{filename[:-3]}")

