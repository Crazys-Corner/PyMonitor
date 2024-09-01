import discord
from discord.ext import tasks, commands
import psutil
import os
import json
import socket

CONFIG_FILE = "config.json"
hostname = socket.gethostname()
message_to_update = None

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)
    return None

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file)

def get_config():
    config = load_config()
    
    if config is None:
    
        print("It looks like this is your first time running the app.")
        token = input("Please enter your Discord Bot Token: ")
        channel_id = input("Please enter your Discord Channel ID: ")
        
        config = {
            "DISCORD_BOT_TOKEN": token,
            "DISCORD_CHANNEL_ID": channel_id
        }
        
      
        save_config(config)
    else:
        print("Configuration loaded.")
    
    return config


config = get_config()
TOKEN = config["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(config["DISCORD_CHANNEL_ID"])

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

def cpu_usage():
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    return cpu_usage, cpu_count

def ram_usage():
    mem = psutil.virtual_memory()
    memory_total = mem.total
    memory_available = mem.available
    memory_used = memory_total - memory_available
    return memory_total, memory_available, memory_used

def disk_usage():
    disk = psutil.disk_usage('/')
    disk_total = disk.total
    disk_used = disk.used
    disk_free = disk.free
    return disk_total, disk_used, disk_free

def net_usage():
    net_io = psutil.net_io_counters()
    net_sent = net_io.bytes_sent
    net_received = net_io.bytes_recv
    return net_sent, net_received

def create_embed(cpu, ram, disk, net):
    embed = discord.Embed(
        title=f"Server Resource Usage - {hostname}",
        color=discord.Color.blue()
    )
    embed.add_field(name="CPU Usage", value=f"Usage: {cpu[0]}%\nCores: {cpu[1]}", inline=False)
    embed.add_field(name="RAM Usage", value=f"Total: {ram[0] / (1024 ** 3):.2f} GB\nUsed: {ram[2] / (1024 ** 3):.2f} GB\nAvailable: {ram[1] / (1024 ** 3):.2f} GB", inline=False)
    embed.add_field(name="Disk Usage", value=f"Total: {disk[0] / (1024 ** 3):.2f} GB\nUsed: {disk[1] / (1024 ** 3):.2f} GB\nFree: {disk[2] / (1024 ** 3):.2f} GB", inline=False)
    embed.add_field(name="Network Usage", value=f"Sent: {net[0] / (1024 ** 2):.2f} MB\nReceived: {net[1] / (1024 ** 2):.2f} MB", inline=False)
    return embed

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    channel = bot.get_channel(CHANNEL_ID)
    
    global message_to_update
    
    # Send an initial message
    cpu = cpu_usage()
    ram = ram_usage()
    disk = disk_usage()
    net = net_usage()
    embed = create_embed(cpu, ram, disk, net)
    message_to_update = await channel.send(embed=embed)

    update_embed.start()

@tasks.loop(seconds=1)
async def update_embed():
    global message_to_update
    
    if message_to_update:
        cpu = cpu_usage()
        ram = ram_usage()
        disk = disk_usage()
        net = net_usage()
        embed = create_embed(cpu, ram, disk, net)
        
        await message_to_update.edit(embed=embed)

bot.run(TOKEN)
