On Error Resume Next
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = strPath & "\startup_log.txt"

Set logStream = fso.CreateTextFile(logFile, True)
logStream.WriteLine "Start Time: " & Now()
logStream.WriteLine "Script Path: " & strPath

' Check Python Environment
Set objExec = WshShell.Exec("python --version")
If Err.Number <> 0 Then
    logStream.WriteLine "Error: Python not found"
    MsgBox "Error: Python not found, please make sure Python is installed and added to PATH", 16, "Environment Error"
    WScript.Quit
End If
logStream.WriteLine "Python Version: " & objExec.StdOut.ReadAll

' Check Required Files
If Not fso.FileExists(strPath & "\app.py") Then
    logStream.WriteLine "Error: app.py not found"
    MsgBox "Error: app.py not found", 16, "Startup Error"
    WScript.Quit
End If

' Check requirements.txt
If fso.FileExists(strPath & "\requirements.txt") Then
    Set reqFile = fso.OpenTextFile(strPath & "\requirements.txt", 1)
    logStream.WriteLine "Checking Dependencies:"
    Do Until reqFile.AtEndOfStream
        logStream.WriteLine "- " & reqFile.ReadLine
    Loop
    reqFile.Close
End If

' Start Program
WshShell.CurrentDirectory = strPath
cmd = "python " & Chr(34) & strPath & "\app.py" & Chr(34)
logStream.WriteLine "Execute Command: " & cmd
WshShell.Run cmd, 1, false

If Err.Number <> 0 Then
    logStream.WriteLine "Error Code: " & Err.Number
    logStream.WriteLine "Error Description: " & Err.Description
    MsgBox "Startup Failed: " & Err.Description, 16, "Startup Error"
End If

' Wait for startup
WScript.Sleep 2000

logStream.WriteLine "Completion Time: " & Now()
logStream.Close