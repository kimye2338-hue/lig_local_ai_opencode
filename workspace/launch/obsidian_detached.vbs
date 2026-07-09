Option Explicit
Dim shell, exePath, vaultPath, cmd
If WScript.Arguments.Count < 2 Then WScript.Quit 1
exePath = WScript.Arguments(0)
vaultPath = WScript.Arguments(1)
Set shell = CreateObject("WScript.Shell")
cmd = Chr(34) & exePath & Chr(34) & " " & Chr(34) & vaultPath & Chr(34)
shell.Run cmd, 1, False
