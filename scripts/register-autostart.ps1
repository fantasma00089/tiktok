# Registra o monitor para iniciar automaticamente no logon do Windows (Agendador de Tarefas).
$ErrorActionPreference = "Stop"
$script = (Resolve-Path "$PSScriptRoot\start.ps1").Path
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Background"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "TikTokRepostMonitor" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Tarefa 'TikTokRepostMonitor' registrada: o monitor iniciará no próximo logon."
