import discord
from discord.ext import tasks, commands
import psutil
import os
import json
import socket
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import io
import subprocess
import platform

CONFIG_FILE = "config.json"
hostname = socket.gethostname()
message_to_update = None

# Set up SQLite connection
conn = sqlite3.connect('server_usage.db')
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usage_data (
        timestamp TEXT,
        cpu_usage REAL,
        ram_usage REAL,
        disk_used REAL,
        disk_free REAL,
        net_sent REAL,
        net_received REAL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS monitored_services (
        service_name TEXT PRIMARY KEY
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS service_notifications (
        service_name TEXT,
        user_id INTEGER,
        PRIMARY KEY (service_name, user_id)
    )
''')
conn.commit()

# Load config
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)
    return None

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file)

def get_cpu_info():
    if platform.system() == "Linux":
        # Linux specific method
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":")[1].strip()
    else:
        # Fallback for other platforms
        return platform.processor()

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

def check_service_status(service_name):
    """Check if a specific service is running."""
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == service_name:
            return True
    return False

def check_drive_health(drive):
    """
    Check the health of a specific drive using smartctl.
    :param drive: The drive to check (e.g., /dev/sda)
    :return: A dictionary containing health information.
    """
    try:
        # Run smartctl command to check drive health
        result = subprocess.run(
            ['smartctl', '-H', drive],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Parse the result
        if "PASSED" in result.stdout:
            return {"drive": drive, "status": "PASSED"}
        elif "FAILED" in result.stdout:
            return {"drive": drive, "status": "FAILED"}
        else:
            return {"drive": drive, "status": "UNKNOWN"}
    except Exception as e:
        return {"drive": drive, "status": "ERROR", "message": str(e)}

def list_all_drives():
    """
    List all physical drives on the system.
    :return: A list of drives (e.g., ['/dev/sda', '/dev/nvme0n1'])
    """
    drives = []
    
  
    partitions = psutil.disk_partitions(all=False)
    for partition in partitions:
        device = partition.device
        if device not in drives:
            drives.append(device)
    

    
    return drives

def collect_data():
    print("Collecting data...")
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent

    # Aggregate disk usage across all partitions
    disk_data = disk_usage()
    total_disk_used = sum(usage['used'] for usage in disk_data.values())
    total_disk_free = sum(usage['free'] for usage in disk_data.values())

    net_sent, net_received = net_usage()
    timestamp = datetime.now().isoformat()

    # Insert data into SQLite database
    cursor.execute('''
        INSERT INTO usage_data (timestamp, cpu_usage, ram_usage, disk_used, disk_free, net_sent, net_received)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, cpu, ram, total_disk_used, total_disk_free, net_sent, net_received))
    conn.commit()
    print(f"Data collected: CPU {cpu}%, RAM {ram}%, Disk Used {total_disk_used / (1024 ** 3):.2f} GB, Disk Free {total_disk_free / (1024 ** 3):.2f} GB, Net Sent {net_sent / (1024 ** 2):.2f} MB, Net Received {net_received / (1024 ** 2):.2f} MB")

def create_graph():
    cursor.execute('''
        SELECT timestamp, cpu_usage, ram_usage, disk_used, disk_free, net_sent, net_received FROM usage_data
        ORDER BY timestamp ASC
    ''')
    rows = cursor.fetchall()

    if len(rows) < 2:
        print("Not enough data to create a graph.")
        return None

    timestamps = [row[0] for row in rows]
    cpu_data = [row[1] for row in rows]
    ram_data = [row[2] for row in rows]
    disk_used_data = [row[3] for row in rows]
    disk_free_data = [row[4] for row in rows]
    net_sent_data = [row[5] for row in rows]
    net_received_data = [row[6] for row in rows]

    plt.figure(figsize=(10, 5))
    
    # Plot CPU usage
    plt.plot(timestamps, cpu_data, label="CPU Usage (%)", color="blue", marker="o")
    
    # Plot RAM usage
    plt.plot(timestamps, ram_data, label="RAM Usage (%)", color="green", marker="o")
    
    # Plot Disk usage
    plt.plot(timestamps, [used / (1024 ** 3) for used in disk_used_data], label="Disk Used (GB)", color="red", marker="o")
    plt.plot(timestamps, [free / (1024 ** 3) for free in disk_free_data], label="Disk Free (GB)", color="orange", marker="o")
    
    # Plot Network usage
    plt.plot(timestamps, [sent / (1024 ** 2) for sent in net_sent_data], label="Net Sent (MB)", color="purple", marker="o")
    plt.plot(timestamps, [received / (1024 ** 2) for received in net_received_data], label="Net Received (MB)", color="brown", marker="o")
    
    plt.xlabel("Time")
    plt.ylabel("Usage")
    plt.title(f"Server Resource Usage Over Time - {hostname}")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)  # Rotate timestamps for better readability
    
    # Save the plot to a BytesIO object
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    
    print("Graph created successfully.")
    return buf

def create_embed(cpu, ram, disk, net, services_status):
    embed = discord.Embed(
        title=f"Server Resource Usage - {hostname}",
        color=discord.Color.blue()
    )
    cpu_info = get_cpu_info()
    embed.add_field(name="CPU Model", value=cpu_info, inline=False)
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
    
    for service, status in services_status.items():
        embed.add_field(name=f"Service: {service}", value=f"Status: {'Running' if status else 'Not Running'}", inline=False)
    
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

    services_status = {}
    cursor.execute('SELECT service_name FROM monitored_services')
    services = cursor.fetchall()
    for service in services:
        service_name = service[0]
        services_status[service_name] = check_service_status(service_name)

    embed = create_embed(cpu, ram, disk, net, services_status)
    message_to_update = await channel.send(embed=embed)

    collect_data_task.start()
    update_embed.start()

@tasks.loop(minutes=1)  
async def collect_data_task():
    collect_data()

@tasks.loop(seconds=10)
async def update_embed():
    global message_to_update

    if message_to_update:
        cpu = cpu_usage()
        ram = ram_usage()
        disk = disk_usage()
        net = net_usage()

       
        drives_to_monitor = list_all_drives()
        drive_health_status = {}
        for drive in drives_to_monitor:
            health_status = check_drive_health(drive)
            drive_health_status[drive] = health_status['status']

            # Notify if the drive health is not "PASSED"
            if health_status['status'] == "FAILED":
                cursor.execute('SELECT user_id FROM service_notifications WHERE service_name = "all"')
                users_to_notify = cursor.fetchall()
                for user in users_to_notify:
                    user_id = user[0]
                    user_obj = await bot.fetch_user(user_id)
                    await user_obj.send(f"🔴 Alert: The drive `{drive}` has reported a health status of `{health_status['status']}`!")

        services_status = {}
        cursor.execute('SELECT service_name FROM monitored_services')
        services = cursor.fetchall()
        for service in services:
            service_name = service[0]
            is_running = check_service_status(service_name)
            services_status[service_name] = is_running

            if not is_running:
                cursor.execute('SELECT user_id FROM service_notifications WHERE service_name = ? OR service_name = "all"', (service_name,))
                users_to_notify = cursor.fetchall()
                for user in users_to_notify:
                    user_id = user[0]
                    user_obj = await bot.fetch_user(user_id)
                    await user_obj.send(f"🔴 Alert: The service `{service_name}` has stopped running!")

        embed = create_embed(cpu, ram, disk, net, services_status)
        await message_to_update.edit(embed=embed)

# Register a slash command for admins to add a service to monitor
@bot.slash_command(name="add_service", description="Add a service to monitor (Admins only)")
async def add_service(ctx: discord.ApplicationContext, service_name: str):
    if ctx.author.guild_permissions.administrator:
        cursor.execute('INSERT OR IGNORE INTO monitored_services (service_name) VALUES (?)', (service_name,))
        conn.commit()
        await ctx.respond(f"Service `{service_name}` has been added to the monitoring list.")
    else:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)

# Register a slash command for admins to remove a service from monitoring
@bot.slash_command(name="remove_service", description="Remove a service from monitoring (Admins only)")
async def remove_service(ctx: discord.ApplicationContext, service_name: str):
    if ctx.author.guild_permissions.administrator:
        cursor.execute('DELETE FROM monitored_services WHERE service_name = ?', (service_name,))
        conn.commit()
        await ctx.respond(f"Service `{service_name}` has been removed from the monitoring list.")
    else:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)

# Register a slash command to list monitored services
@bot.slash_command(name="list_services", description="List all monitored services")
async def list_services(ctx: discord.ApplicationContext):
    cursor.execute('SELECT service_name FROM monitored_services')
    services = cursor.fetchall()
    service_list = "\n".join([service[0] for service in services])
    if service_list:
        await ctx.respond(f"Monitored Services:\n{service_list}")
    else:
        await ctx.respond("No services are being monitored.")

# Register a slash command to generate and display the resource usage graph
@bot.slash_command(name="graph", description="Displays a graph of server resource usage over time")
async def show_graph(ctx: discord.ApplicationContext):
    print("Graph slash command invoked.")
    graph_image = create_graph()
    if graph_image:
        await ctx.respond(file=discord.File(fp=graph_image, filename="server_usage.png"))
    else:
        await ctx.respond("Not enough data to create a graph.")

# Register a slash command for users to receive notifications if any service stops
@bot.slash_command(name="notify_me", description="Get notified if any monitored service stops running")
async def notify_me(ctx: discord.ApplicationContext):
    cursor.execute('INSERT OR IGNORE INTO service_notifications (service_name, user_id) VALUES ("all", ?)', (ctx.author.id,))
    conn.commit()
    await ctx.respond(f"You will be notified if any monitored service stops running.")

# Register a slash command for users to stop receiving notifications for all services
@bot.slash_command(name="unnotify_me", description="Stop receiving notifications for all monitored services")
async def unnotify_me(ctx: discord.ApplicationContext):
    cursor.execute('DELETE FROM service_notifications WHERE service_name = "all" AND user_id = ?', (ctx.author.id,))
    conn.commit()
    await ctx.respond(f"You will no longer be notified if any monitored service stops running.")

bot.run(TOKEN)
