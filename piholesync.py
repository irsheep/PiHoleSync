#!/usr/bin/env python3
import requests
import re
import configparser
import sys
from os.path import exists, realpath, getmtime
from os import mkdir, unlink
from pathlib import Path

class Arguments:
  Action = None
  BackupDir = None
  BackupFrom = None
  RestoreTarget = None
  IniFile = "piholesync.ini"

  def __init__ (self):
    args = sys.argv[1:]
    argc = len(sys.argv[1:])

    getArgument = lambda i: (args[i], args[i+1])

    for x in range(0, argc, 2):
      (key, val) = getArgument(x)
      # print(f"Argument {key}: {val}")
      if key == "-a" or key == "--action": self.Action = val
      elif key == "-s" or key == "--source": self.BackupFrom = val
      elif key == "-d" or key == "--directory": self.BackupDir = val
      elif key == "-i" or key == "--ini": self.IniFile = val
      elif key == "-t" or key == "--target": self.RestoreTarget = val
      else:
        print(f"Invalid argument {key}")
        exit(1)

  def MergeWith(self, settings):
    getSettingValue = lambda x: getattr(settings, x) if getattr(self, x) == None else getattr(self, x)
    settings.Action = getSettingValue("Action")
    settings.BackupDir = getSettingValue("BackupDir")
    settings.BackupFrom = getSettingValue("BackupFrom")
    settings.RestoreTarget = getSettingValue("RestoreTarget")
    return settings

class PiSyncSettings:
  # Settings from DEFAULT section
  Action = None
  RetainBackupFiles = None
  BackupDir = None
  BackupFrom = None
  RestoreTarget = None
  # Host section settings
  Address = None
  Password = None

  @staticmethod
  def ValidateConfig(config):
    for section in config.sections():
      if section == configparser.DEFAULTSECT:
        if sorted(['action', 'retainbackupfiles', 'backupdir', 'backupfrom']) != sorted(dict(config[section]).keys()):
          print(f"ERROR: Invalid INI file, section [{section}] has missing or invalid items.")
          exit(1)
      else:
        if sorted([
            # These items shouldn't be here, maybe a bug with the 'configparser'!!!
            'action', 'retainbackupfiles', 'backupdir', 'backupfrom',
            'host', 'port', 'proto', 'password'
        ]) != sorted(dict(config[section]).keys()):
          print(f"ERROR: Invalid INI file, section [{section}] has missing or invalid items.")
          exit(1)

  def __init__(self, config, section=None):
    if section == configparser.DEFAULTSECT:
      self.Action = self.StripQuotes(config["Action"])
      self.RetainBackupFiles = int(config["RetainBackupFiles"])
      self.BackupDir = self.StripQuotes(config["BackupDir"])
      self.BackupFrom = self.StripQuotes(config["BackupFrom"])
    else:
      proto = self.StripQuotes(config["Proto"])
      host = self.StripQuotes(config["Host"])
      port = int(config["Port"])
      if port == 80 or port == 443:
        self.Address = f"{proto}://{host}"
      else:
        self.Address = f"{proto}://{host}:{port}"
      self.Password = self.StripQuotes(config["Password"])

  def StripQuotes(self, value):
    strip = lambda s, c: s.lstrip(c).rstrip(c) if s.startswith(c) and s.endswith(s) else s
    if value.startswith("'"):
      return strip(value, "'")
    if value.startswith('"'):
      return strip(value, '"')
    else:
      return value

class PiHoleUrls:
  def __init__(self, host):
    self.login = f"{host}/admin/login.php"
    self.teleporter = f"{host}/admin/scripts/pi-hole/php/teleporter.php"

class PiHole:
  REGEX_TOKEN = r"div id=.token..+?>(?P<token>.+)<\/div>"

  def __init__(self, settings):
    self.urls = PiHoleUrls(settings.Address)
    self.loggedin = False

    postData = { 'pw': settings.Password }
    response = requests.post(self.urls.login, data=postData)
    # Get token from admin portal
    matches = re.findall(self.REGEX_TOKEN, response.text, re.MULTILINE)
    self.token = matches[0]
    self.cookies = response.cookies
    # TODO: Check if login was successfull, we have a token and cookies
    self.loggedin = True

  def UploadBackupFile(self, backupFile):
    if not self.loggedin:
      print("ERROR: Not logged in to PiHole")
      return False

    if not exists(backupFile):
      print (f"ERROR: can't find file {backupFile}")
      exit(1)

    # Load backup file
    uploadFiles = { 'zip_file': open(backupFile, "rb") }
    postData = {
      'token': self.token,
      # What to restore
      'whitelist': 'true',
      'regex_whitelist': 'true',
      'blacklist': 'true',
      'regex_blacklist': 'true',

      'group': 'true',
      'client': 'true',
      'adlist': 'true',
      'auditlog': 'true',

      'staticdhcpleases': 'true',
      'localdnsrecords': 'true',
      'localcnamerecords': 'true',
      # Clear existing data
      'flushtables': 'true',
      # PHP script action
      'action': 'in'
    }

    # Upload backedup data
    response = requests.post(
      self.urls.teleporter,
      files=uploadFiles,
      data=postData,
      cookies=self.cookies
    )

    # Say cheese
    print(response.text)

  def DownloadBackup(self, path, filename=None):
    if not self.loggedin:
      print("ERROR: Not logged in to PiHole")
      return False

    postData = { 'token': self.token }
    response = requests.post(
      self.urls.teleporter,
      data = postData,
      cookies=self.cookies,
      stream=True
    )

    if not exists(path):
      mkdir(path)

    if filename == None:
      contentDisposition = response.headers['Content-Disposition']
      filename = contentDisposition.replace("attachment; filename=", "")

    with open(f"{path.rstrip('/')}/{filename}", 'wb') as fd:
      for chunk in response.iter_content(chunk_size=1024):
        fd.write(chunk)

def DownloadBackup(configSection, backupDir):
  settings = PiSyncSettings(configSection)
  # print (f"Downloading backup to: {backupDir}")
  # print (vars(settings))
  pi = PiHole(settings)
  pi.DownloadBackup(backupDir)

def RestoreBackup(configSection, backupFile):
  settings = PiSyncSettings(configSection)
  # print (f"Restoring from: {backupFile}")
  # print (vars(settings))
  pi = PiHole(settings)
  pi.UploadBackupFile(backupFile)

def DeleteOldBackups(backupDir, retentionPeriod):
  backupFiles = sorted(Path(backupDir).iterdir(), key=getmtime)
  if len(backupFiles) < retentionPeriod:
    return False
  for backupFile in backupFiles[:retentionPeriod*-1]:
    print(f"Removing backup {realpath(backupFile)}")
    unlink(realpath(backupFile))

if __name__ == '__main__':
  # Process command line arguments
  args = Arguments()

  if not exists(args.IniFile):
    print(f"Could not find INI file {args.IniFile}")
    exit(1)

  # Read configuration from INI file
  config = configparser.ConfigParser()
  config.read(args.IniFile)
  PiSyncSettings.ValidateConfig(config)
  piSyncSettings = PiSyncSettings(config[configparser.DEFAULTSECT], configparser.DEFAULTSECT)
  # Merge with CLI arguments
  piSettings = args.MergeWith(piSyncSettings)
  print(vars(piSettings))

  # Target argument not supported with backup or sync actions
  if (piSettings.Action == "backup" or piSettings.Action == "sync") and piSettings.RestoreTarget != None:
    print("Ignoring '--target' argument, is not supported in 'backup' or 'sync' actions.")

  # Perform a backup of the source server for backup or sync actions
  if piSettings.Action == "backup" or piSettings.Action == "sync":
    if piSettings.BackupFrom not in config.sections():
      print(f"Host section [{piSettings.BackupFrom}] not found in INI file.")
      exit(1)
    DownloadBackup(config[piSyncSettings.BackupFrom], piSyncSettings.BackupDir)
    DeleteOldBackups(piSyncSettings.BackupDir, piSyncSettings.RetainBackupFiles)

  # Get the latest backup file from backup directory
  backups = sorted(Path(piSyncSettings.BackupDir).iterdir(), key=getmtime)
  backupFile = realpath(backups[-1])

  # Restore the latest backup on other servers
  if piSettings.Action == "sync":
    for section in config.sections():
      if section != configparser.DEFAULTSECT and section != piSyncSettings.BackupFrom:
        RestoreBackup(config[section], backupFile)

  # Restore the latest backup on the selected server
  if piSettings.Action == "restore":
    if piSettings.RestoreTarget == None:
      print("Unable to restore, not target (-t or --target) was specified")
      exit(1)
    elif piSettings.RestoreTarget not in config.sections():
      print(f"Host section [{piSettings.RestoreTarget}] not found in INI file.")
      exit(1)

    RestoreBackup(config[piSettings.RestoreTarget], backupFile)
