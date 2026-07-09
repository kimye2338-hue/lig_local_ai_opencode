Dim sh, fso, bat, cmd, logDir, logFile
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
bat = Replace(WScript.ScriptFullName, "hamster_hidden.vbs", "hamster.bat")
logDir = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\OpenCodeLIG_USERDATA\diagnostics"
If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)
logFile = logDir & "\hamster_launcher.log"
cmd = "%ComSpec% /c """ & bat & """ --hidden >> """ & logFile & """ 2>>&1"
sh.Run cmd, 0, False
