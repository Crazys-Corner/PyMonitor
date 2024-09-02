# Monitor your server with PyMonitor

PyMonitor is a simplistic monitoring solution that we (@SilentAssassin101 and I) made in a 30 minute coding challenge. We decided to build an infrastructure monitoring tool to help you easily visualize your server resource usage. 

## Install

Installation is easy

**NOTE**: PyMonitor is intended to work with DEBIAN BASED MACHINES ONLY. RHEL-based distros *should* work, but is untested. Windows is unsupported and untested, you will have to build from scratch. 

Option A: Monitoring your own machine 

1: Head over to the [Releases Tab](https://github.com/Crazys-Corner/PyMonitor/releases/)

2: Download the executable 

3: Open up your terminal and navigate to where the file is located

4: Run: `chmod +x main && ./main`

Now you're done! 

Option B: Monitoring a server 

1: SSH into your server

2: `sudo wget https://github.com/Crazys-Corner/PyMonitor/releases/download/V1/main -O /usr/bin/pymonitor` (Replace download url to latest or preferred release file, titled main, this assumes V1)

3: Run the following to test the applciation and go through first time setup - **this is important:** `cd /usr/bin/pymonitor && chmod +x main && ./main` - Once you run the file, you will be prompted to provide your discord bot token (Obtainable here: https://discord.com/developers/applications) and a channel ID to send the bot message to. Please make sure to invite the bot to the server, with adequate permissions before continuing.

4: Create a file in `/etc/systemd/system/pymonitor.service`, here's how I'd do it:

First:
`nano /etc/systemd/system/pymonitor.service`

Then paste the following:

```
[Unit]
Description=Monitor your Server with PyMonitor
After=network.target

[Service]
ExecStart=/usr/bin/pymonitor/main
Restart=on-failure
User=root
WorkingDirectory=/usr/bin/pymonitor/
Environment=FLASK_ENV=production


[Install]
WantedBy=multi-user.target
```

5: Run `systemctl daemon-reload`
6: Run `systemctl enable --now pymonitor.service`

Now you are good to go! The monitor is now running and you should see the embed in the channel ID specified during *step 3*. If the server is rebooted, the process will restart automatically, however it will create a **new** message in the channel, you must delete the old message, or don't, up to you.  

