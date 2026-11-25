Option Explicit
Dim shell, fs, folder, command, result
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & folder & "\Install-Brave.ps1"""
result = shell.Run(command, 0, True)
If result = 0 Then
  MsgBox "Brave Assistant is installed. Open it from the Start menu.", vbInformation, "Brave"
Else
  MsgBox "Installation failed. Run Install-Brave.ps1 to see the error.", vbExclamation, "Brave"
End If
