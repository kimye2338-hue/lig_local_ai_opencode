Dim sh, bat, cmd
Set sh = CreateObject("WScript.Shell")
bat = Replace(WScript.ScriptFullName, "hamster_hidden.vbs", "hamster.bat")
cmd = """" & bat & """ --hidden"
sh.Run cmd, 0, False
