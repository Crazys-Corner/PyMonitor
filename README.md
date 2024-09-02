
![Pm](https://github.com/user-attachments/assets/c9fbc9e9-eef6-47f9-ad28-3eef9306ce3c)


# Monitor your server with PyMonitor

PyMonitor is a simplistic monitoring solution that we (@SilentAssassin101 and I) made in a 30 minute coding challenge. We decided to build an infrastructure monitoring tool to help you easily visualize your server resource usage. 

## Install

Installation is easy

**NOTE**: PyMonitor is intended to work with DEBIAN BASED MACHINES ONLY. RHEL-based distros *should* work, but is untested. Windows is unsupported and untested, you will have to build from scratch. 

Prerequisites:
 
ATLEAST 1 Debian-based Machine (Windows is unsupported, feel free to try, RHEL should work but is untested)

   We suggest using two machines, one to run the control server, one to be a daemon monitored by the control server. One machine CAN run both the control server and the daemon. You must connect all daemons to the control server. 
   
1: SSH into your control server. 

2: `sudo wget https://github.com/Crazys-Corner/PyMonitor/releases/download/V3/control -O /usr/bin/pymonitor/control` 

3: Run the following to test the applciation and go through first time setup - **this is important:** `cd /usr/bin/pymonitor && chmod +x control && ./control` - Once you run the file, you will be prompted to provide your discord bot token (Obtainable here: https://discord.com/developers/applications) and a channel ID to send the bot message to. Please make sure to invite the bot to the server, with adequate permissions before continuing. You should give it applications.commands, bot, and administrator

4: Create a file in `/etc/systemd/system/pymonitor.service`, here's how I'd do it:

First:
`nano /etc/systemd/system/pymonitor.service`

Then paste the following:

```
[Unit]
Description=Monitor your Server with PyMonitor
After=network.target

[Service]
ExecStart=/usr/bin/pymonitor/control
Restart=on-failure
User=root
WorkingDirectory=/usr/bin/pymonitor/
Environment=FLASK_ENV=production


[Install]
WantedBy=multi-user.target
```

5: Run `systemctl daemon-reload`
6: Run `systemctl enable --now pymonitor.service`

Now you are good to go! The monitor control is now running and you should see the embed in the channel ID specified during *step 3*. If the server is rebooted, the process will restart automatically, however it will create a **new** message in the channel, you must delete the old message, or don't, up to you.

Now to setup the individual daemons. These are the servers that are monitored by the control server we just setup. 

1: SSH into a server you would like to monitor. *Note*: You **CAN** use the same server as control, however in the event that this server goes down, you will not be notified (logically) 

2: `sudo wget https://github.com/Crazys-Corner/PyMonitor/releases/download/V3/daemon -O /usr/bin/pymonitor/daemon`

3: Run the following to test the applciation and go through first time setup - **this is important:** `cd /usr/bin/pymonitor && chmod +x daemon && ./daemon` - Once you run the file, you will be prompted to provide the URL to your control server. This is going to be http://yourcontrolserverip:5000/

4: Create a file in `/etc/systemd/system/pydaemon.service`, here's how I'd do it:

First:
`nano /etc/systemd/system/pydaemon.service`

Then paste the following:

```
[Unit]
Description=Monitor your Server with PyMonitor
After=network.target

[Service]
ExecStart=/usr/bin/pymonitor/daemon
Restart=on-failure
User=root
WorkingDirectory=/usr/bin/pymonitor/
Environment=FLASK_ENV=production


[Install]
WantedBy=multi-user.target
```

5: Run `systemctl daemon-reload`
6: Run `systemctl enable --now pydaemon.service`

Now everything is setup and should be running correctly. 

## Product Demo

![Screenshot_20240902_004315](https://github.com/user-attachments/assets/be2cd378-4aa7-4e56-9659-22ca29e42100)


Displays actively updating server data across 2 machines. 

![Screenshot_20240902_004315](https://github.com/user-attachments/assets/21f64454-4947-4e3c-8e56-bcd881d89331)

You can receive notifications on each node if something happens.

![Screenshot_20240902_004555](https://github.com/user-attachments/assets/bc8f718b-657f-4941-8268-86dc4af94595)

You can list all actively connected hosts

![Screenshot_20240902_004629](https://github.com/user-attachments/assets/467ec06a-f226-4640-ac15-caf9d49e3e11)

Try out the other features!


