# Introduction
PiHoleSync its a script written in Python3 which can be used to synchronize the configuration from a source server to one or more destination Pi-Hole servers.

PiHoleSync uses Pi-Hole Teleporter backup and restore functions to backup the configuration from the source server and then restore it to other Pi-Hole servers.

# Table of contents

* [Requirements](#requirements)
* [Configuration](#configuration)
* [Arguments](#arguments)

# Requirements

- Python 3
- One or more instances of Pi-Hole servers

# Configuration
PiHoleSync configuration is read from **piholesync.ini**. The configuration files requires a **DEFAULT** section and one or more sections for each Pi-Hole server.

Sample INI file
```ini
[DEFAULT]
Action = sync
RetainBackupFiles = 30
BackupDir = /tmp/pihole
BackupFrom = pihole1

[pihole1]
Host = 192.168.51.11
Port = 80
Proto = http
Password = ChangeMe

[pihole2]
Host = 192.168.51.12
Port = 8080
Proto = http
Password = ChangeMe
```

## DEFAULT section
- Action: Can be **backup** or **sync**, either to backup the selected server or to synchronize the configuration from the selected server to the other servers
- RetainBackupFiles: Number of backup files to keep in the backup directory
- BackupDir: Path where to store the backup files
- BackupFrom: Name of the section in the INI file representing a Pi-Hole server to use as the source, in the example above **pihole1** would be the source server

## Server section
Add a server section for each Pi-Hole server
- Host: Hostname or IP address of the Pi-Hole server
- Port: Port used by Pi-Hole web interface
- Proto: Protocol (http or https) used to access Pi-Hole web interface
- Password: Admin password to login to Pi-Hole web interface

# Arguments
PiHoleSync can receive command line arguments to change its behaviour when running, any argument passed will take preference over the settings in the INI file

- -i, --ini: Path to alternative INI configuration file
- -a, --action: backup, restore or sync
- -d, --directory: Backup directory
- -s, --source: Name of the section in the INI file to use as the source Pi-Hole server
- -t, --target: Name of the section in the INI file to use the target Pi-Hole server to restore the latest backup to. This opton is only supported with the **restore** action.

```bash
# Restore the latest backup to the Pi-Hole server pihole1 as defined in the INI file
$ ./piholesync.py -a restore -t pihole1
```