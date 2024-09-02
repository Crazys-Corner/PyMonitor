import discord
from discord.ext import tasks, commands
import json
import sqlite3
from flask import Flask, request, jsonify
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta
import os
from asyncio import Queue

app = Flask(__name__)

# Set up SQLite connection
conn = sqlite3.connect('server_usage.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS server_data (
        hostname TEXT PRIMARY KEY,
        data TEXT,
        last_report_time TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS service_notifications (
        hostname TEXT,
        user_id INTEGER,
        PRIMARY KEY (hostname, user_id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS monitored_services (
        hostname TEXT,
        service_name TEXT,
        PRIMARY KEY (hostname, service_name)
    )
''')

conn.commit()

CONFIG_FILE = "config.json"
update_queue = Queue()  # Queue to manage incoming data updates

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
bot = commands.Bot(command_prefix="!", intents=intents)

@app.route('/report', methods=['POST'])
def report():
    data = request.json
    hostname = data.get("hostname")
    data_json = json.dumps(data)
    last_report_time = datetime.now().isoformat()

    cursor.execute('''
        INSERT OR REPLACE INTO server_data (hostname, data, last_report_time)
        VALUES (?, ?, ?)
    ''', (hostname, data_json, last_report_time))
    conn.commit()

    # Add the hostname to the update queue
    bot.loop.create_task(update_queue.put(hostname))

    # Check for notifications
    check_notifications(hostname, data)

    return jsonify({"status": "success"}), 200

def start_flask_server():
    app.run(host='0.0.0.0', port=5000)

def check_notifications(hostname, data):
    services = data.get('services', {})
    for service, status in services.items():
        if not status:
            cursor.execute('SELECT user_id FROM service_notifications WHERE hostname = ?', (hostname,))
            users_to_notify = cursor.fetchall()
            for user in users_to_notify:
                user_id = user[0]
                user_obj = bot.get_user(user_id)
                if user_obj:
                    bot.loop.create_task(user_obj.send(f"🔴 Alert: {hostname} service {service} has stopped running!"))

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    channel = bot.get_channel(CHANNEL_ID)

    global message_to_update
    message_to_update = None
    
    # Check if there's already a message from the bot
    async for message in channel.history(limit=10):
        if message.author == bot.user:
            message_to_update = message
            break

    if message_to_update is None:
        print("Sending new status message...")
        message_to_update = await channel.send("Monitoring server status...")

    print("Ready to receive data and update status.")
    process_queue.start()  # Start processing the update queue
    check_server_statuses.start()  # Start checking for server downtime

@tasks.loop(seconds=5)  # Process the queue every 5 seconds
async def process_queue():
    if not update_queue.empty():
        hostname = await update_queue.get()
        print(f"Processing update for {hostname}...")
        await update_status()

@tasks.loop(minutes=1)  # Check for server downtime every minute
async def check_server_statuses():
    print("Checking server statuses...")
    cursor.execute('SELECT hostname, last_report_time FROM server_data')
    servers = cursor.fetchall()

    now = datetime.now()
    down_servers = []

    for server in servers:
        hostname, last_report_time = server
        last_report_time = datetime.fromisoformat(last_report_time)
        if now - last_report_time > timedelta(minutes=1): 
            down_servers.append(hostname)

    if down_servers:
        print(f"Detected down servers: {', '.join(down_servers)}")
        channel = bot.get_channel(CHANNEL_ID)
        for hostname in down_servers:
            await channel.send(f"⚠️ Server {hostname} appears to be down. No report received for over 5 minutes.")

async def update_status():
    print("Update triggered by new data...")
    if message_to_update:
        try:
            cursor.execute('SELECT * FROM server_data')
            servers = cursor.fetchall()

            embed = discord.Embed(title="Server Status Overview", color=discord.Color.blue())
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            for server in servers:
                hostname, data_json, last_report_time = server
                data = json.loads(data_json)
                cpu_info = data.get('cpu_info', 'N/A')
                cpu_usage = data['cpu_usage']
                ram_used = data['ram_used']
                ram_total = data['ram_total']
                ram_usage = f"{ram_used / (1024 ** 3):.2f} GB / {ram_total / (1024 ** 3):.2f} GB"
                
                # Add CPU and RAM info
                embed.add_field(name=f"{hostname} - CPU", value=f"Model: {cpu_info}\nUsage: {cpu_usage}%", inline=False)
                embed.add_field(name=f"{hostname} - RAM", value=ram_usage, inline=False)

                # Add Disk Usage info
                disk_data = data.get('disk_usage', {})
                for mountpoint, usage in disk_data.items():
                    embed.add_field(
                        name=f"{hostname} - Disk ({mountpoint})",
                        value=f"Total: {usage['total'] / (1024 ** 3):.2f} GB\n"
                              f"Used: {usage['used'] / (1024 ** 3):.2f} GB\n"
                              f"Free: {usage['free'] / (1024 ** 3):.2f} GB",
                        inline=False
                    )
                
                # Add Network Usage info
                net_sent = data['net_sent'] / (1024 ** 2)
                net_received = data['net_received'] / (1024 ** 2)
                embed.add_field(name=f"{hostname} - Network", value=f"Sent: {net_sent:.2f} MB\nReceived: {net_received:.2f} MB", inline=False)

                # Add Service Status info
                services = data.get('services', {})
                for service, status in services.items():
                    embed.add_field(name=f"{hostname} - Service: {service}", value=f"Status: {'Running' if status else 'Not Running'}", inline=False)

            print("Updating the message...")
            await message_to_update.edit(embed=embed)
            print("Message updated.")
        
        except Exception as e:
            print(f"Error during update: {e}")

@bot.slash_command(name="list_hosts", description="List all connected hosts")
async def list_hosts(ctx):
    cursor.execute('SELECT hostname FROM server_data')
    servers = cursor.fetchall()
    host_list = "\n".join([server[0] for server in servers])
    if host_list:
        await ctx.respond(f"Connected Hosts:\n{host_list}")
    else:
        await ctx.respond("No hosts are currently connected.")

@bot.slash_command(name="add_service", description="Add a service to monitor on a server (Admins only)")
async def add_service(ctx: discord.ApplicationContext, hostname: str, service_name: str):
    if ctx.author.guild_permissions.administrator:
        cursor.execute('INSERT OR IGNORE INTO monitored_services (hostname, service_name) VALUES (?, ?)', (hostname, service_name))
        conn.commit()
        await ctx.respond(f"Service `{service_name}` on `{hostname}` has been added to the monitoring list.")
    else:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)

@bot.slash_command(name="remove_service", description="Remove a service from monitoring on a server (Admins only)")
async def remove_service(ctx: discord.ApplicationContext, hostname: str, service_name: str):
    if ctx.author.guild_permissions.administrator:
        cursor.execute('DELETE FROM monitored_services WHERE hostname = ? AND service_name = ?', (hostname, service_name))
        conn.commit()
        await ctx.respond(f"Service `{service_name}` on `{hostname}` has been removed from the monitoring list.")
    else:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)

@bot.slash_command(name="notify_me", description="Get notified if any monitored service stops running on a server")
async def notify_me(ctx, hostname: str):
    cursor.execute('INSERT OR IGNORE INTO service_notifications (hostname, user_id) VALUES (?, ?)', (hostname, ctx.author.id))
    conn.commit()
    await ctx.respond(f"You will be notified if any monitored service on `{hostname}` stops running.")

@bot.slash_command(name="unnotify_me", description="Stop receiving notifications for all monitored services on a server")
async def unnotify_me(ctx, hostname: str):
    cursor.execute('DELETE FROM service_notifications WHERE hostname = ? AND user_id = ?', (hostname, ctx.author.id))
    conn.commit()
    await ctx.respond(f"You will no longer be notified if any monitored service on `{hostname}` stops running.")

@bot.slash_command(name="graph", description="Displays a graph of server resource usage over time")
async def show_graph(ctx, hostname: str):
    cursor.execute('SELECT data FROM server_data WHERE hostname = ?', (hostname,))
    server = cursor.fetchone()

    if server:
        data = json.loads(server[0])

        timestamps = [datetime.fromtimestamp(entry['timestamp']) for entry in data.get('history', [])]
        if not timestamps:
            await ctx.respond("No historical data available.")
            return
        
        cpu_data = [entry['cpu_usage'] for entry in data['history']]
        ram_data = [entry['ram_used'] for entry in data['history']]

        plt.figure(figsize=(10, 5))
        plt.plot(timestamps, cpu_data, label="CPU Usage (%)", color="blue", marker="o")
        plt.plot(timestamps, [used / (1024 ** 3) for used in ram_data], label="RAM Usage (GB)", color="green", marker="o")

        plt.xlabel("Time")
        plt.ylabel("Usage")
        plt.title(f"Server Resource Usage Over Time - {hostname}")
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        await ctx.respond(file=discord.File(fp=buf, filename="server_usage.png"))
    else:
        await ctx.respond(f"No data found for server: {hostname}")

# Run the Flask server and Discord bot
if __name__ == "__main__":
    from threading import Thread
    flask_thread = Thread(target=start_flask_server)
    flask_thread.start()
    bot.run(TOKEN)
