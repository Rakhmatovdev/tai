Option Explicit
Dim fs, sh, root, cfg, line, home, interpreter, env
Set fs = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
home = ""
If fs.FileExists(fs.BuildPath(root, ".venv\pyvenv.cfg")) Then
    Set cfg = fs.OpenTextFile(fs.BuildPath(root, ".venv\pyvenv.cfg"), 1)
    Do Until cfg.AtEndOfStream
        line = cfg.ReadLine
        If InStr(line, "=") > 0 Then
            If LCase(Trim(Split(line, "=")(0))) = "home" Then
                home = Trim(Mid(line, InStr(line, "=") + 1))
            End If
        End If
    Loop
    cfg.Close
End If
interpreter = fs.BuildPath(home, "pythonw.exe")
If home = "" Or Not fs.FileExists(interpreter) Then
    MsgBox "Brave Python muhiti topilmadi. .venv sozlamalarini tekshiring.", 16, "Brave"
    WScript.Quit 1
End If
sh.CurrentDirectory = root
Set env = sh.Environment("Process")
' CPython recognizes this launcher path and loads the existing virtual env.
' Calling the real GUI interpreter avoids uv's console redirector.
env("__PYVENV_LAUNCHER__") = fs.BuildPath(root, ".venv\Scripts\pythonw.exe")
sh.Run Chr(34) & interpreter & Chr(34) & " -u " & Chr(34) & fs.BuildPath(root, "launch_brave.pyw") & Chr(34), 1, False
