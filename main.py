import discord
from discord.ext import tasks, commands
import psutil
import os
import json
import socket
import matplotlib.pyplot as plt
import io

CONFIG_FILE = "config.json"
hostname = socket.gethostname()
message_to_update = None
cpu_data = []
ram_data = []
timestamps = []

# Load config
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

# Monitoring functions
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
    partitions = psutil.disk_partitions()
    partition_usage = {}
    
    for partition in partitions:
        if partition.device.startswith('/dev/') and not any(kw in partition.mountpoint for kw in ['snap', 'loop', 'var']):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partition_usage[partition.mountpoint] = {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                }
            except PermissionError:
                continue
    
    return partition_usage

def net_usage():
    net_io = psutil.net_io_counters()
    net_sent = net_io.bytes_sent
    net_received = net_io.bytes_recv
    return net_sent, net_received

def collect_data():
    print("Collecting data...")
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    cpu_data.append(cpu)
    ram_data.append(ram)
    timestamps.append(len(cpu_data))  
    print(f"Data collected: CPU {cpu}%, RAM {ram}%")

def create_graph():
    if len(cpu_data) < 2:
        print("Not enough data to create a graph.")
        return None
    
    plt.figure(figsize=(10, 5))
    

    plt.plot(timestamps, cpu_data, label="CPU Usage (%)", color="blue", marker="o")
    

    plt.plot(timestamps, ram_data, label="RAM Usage (%)", color="green", marker="o")
    
    plt.xlabel("Time")
    plt.ylabel("Usage (%)")
    plt.title(f"Server Resource Usage Over Time - {hostname}")
    plt.legend()
    plt.grid(True)
    

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    
    print("Graph created successfully.")
    return buf

def create_embed(cpu, ram, disk, net):
    embed = discord.Embed(
        title=f"Server Resource Usage - {hostname}",
        color=discord.Color.blue()
    )
    embed.add_field(name="CPU Usage", value=f"Usage: {cpu[0]}%\nCores: {cpu[1]}", inline=False)
    embed.add_field(name="RAM Usage", value=f"Total: {ram[0] / (1024 ** 3):.2f} GB\nUsed: {ram[2] / (1024 ** 3):.2f} GB\nAvailable: {ram[1] / (1024 ** 3):.2f} GB", inline=False)
    
  
    for mountpoint, usage in disk.items():
        embed.add_field(
            name=f"Disk Usage ({mountpoint})", 
            value=f"Total: {usage['total'] / (1024 ** 3):.2f} GB\n"
                  f"Used: {usage['used'] / (1024 ** 3):.2f} GB\n"
                  f"Free: {usage['free'] / (1024 ** 3):.2f} GB", 
            inline=False
        )
    
    embed.add_field(name="Network Usage", value=f"Sent: {net[0] / (1024 ** 2):.2f} MB\nReceived: {net[1] / (1024 ** 2):.2f} MB", inline=False)
    return embed

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    channel = bot.get_channel(CHANNEL_ID)
    
    global message_to_update

    cpu = cpu_usage()
    ram = ram_usage()
    disk = disk_usage()
    net = net_usage()
    embed = create_embed(cpu, ram, disk, net)
    message_to_update = await channel.send(embed=embed)

    collect_data_task.start()
    update_embed.start()

@tasks.loop(minutes=1) 
async def collect_data_task():
    collect_data()

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


@bot.slash_command(name="graph", description="Displays a graph of server resource usage over time")
async def show_graph(ctx: discord.ApplicationContext):
    print("Graph slash command invoked.")
    if len(cpu_data) > 1: 
        graph_image = create_graph()
        if graph_image:
            await ctx.respond(file=discord.File(fp=graph_image, filename="server_usage.png"))
        else:
            await ctx.respond("Not enough data to create a graph.")
    else:
        await ctx.respond("Not enough data to create a graph.")

bot.run(TOKEN)
