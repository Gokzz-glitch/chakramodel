<#
.SYNOPSIS
    Registers and manages the ChakraModel Daily Backup & Recovery Windows Scheduled Task.

.DESCRIPTION
    Configures a Windows Scheduled Task to execute M:\chakramodel\scripts\backup_sync.py
    upon system startup/logon with a 6-minute delay (PT6M).
    Enforces Administrator elevation for task registration while configuring the task to
    execute under the interactive user token (least privilege) to access mapped Google Drive
    volumes (I:\ and J:\) and user Downloads directories.

.PARAMETER TaskName
    Name of the scheduled task in Windows Task Scheduler. Default: "ChakraModelDailySync".

.PARAMETER PythonPath
    Path to Python executable. Automatically detected if omitted (prefers .venv, falls back to system Python).

.PARAMETER ScriptPath
    Path to the backup_sync.py script. Default: "M:\chakramodel\scripts\backup_sync.py".

.PARAMETER WorkingDir
    Working directory for script execution. Default: "M:\chakramodel".

.PARAMETER TriggerType
    Type of startup trigger: 'Logon' (recommended for laptop / mapped drives) or 'Boot'. Default: 'Logon'.

.PARAMETER DelayMinutes
    Delay after startup/logon before execution begins. Default: 6 (ISO 8601 duration PT6M).

.PARAMETER UseXml
    Switch to register directly from XML configuration file instead of programmatic cmdlets.

.PARAMETER XmlPath
    Path to XML configuration template if -UseXml is specified.

.PARAMETER Unregister
    Removes the existing scheduled task.

.PARAMETER Status
    Displays current registration status, last run time, and last result of the task.

.PARAMETER TestRun
    Immediately starts an on-demand test execution of the registered task.

.EXAMPLE
    .\setup_task_scheduler.ps1
    Registers the task with default 6-minute delay on Logon.

.EXAMPLE
    .\setup_task_scheduler.ps1 -Status
    Checks the status and last run result of the task.

.EXAMPLE
    .\setup_task_scheduler.ps1 -Unregister
    Unregisters and cleans up the task.
#>

[CmdletBinding()]
param(
    [string]$TaskName = "ChakraModelDailySync",
    [string]$PythonPath = "",
    [string]$ScriptPath = "M:\chakramodel\scripts\backup_sync.py",
    [string]$WorkingDir = "M:\chakramodel",
    [ValidateSet("Logon", "Boot")]
    [string]$TriggerType = "Logon",
    [int]$DelayMinutes = 6,
    [switch]$UseXml,
    [string]$XmlPath = "M:\chakramodel\scripts\task_scheduler_config.xml",
    [switch]$Unregister,
    [switch]$Status,
    [switch]$TestRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[ChakraModel Scheduler] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# --- 1. Status Query ---
if ($Status) {
    Write-Step "Checking status of scheduled task '$TaskName'..."
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existingTask) {
        Write-Warn "Task '$TaskName' is not registered."
        return
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "--------------------------------------------------" -ForegroundColor Gray
    Write-Host "Task Name:           $($existingTask.TaskName)"
    Write-Host "State:               $($existingTask.State)"
    Write-Host "Last Run Time:       $($info.LastRunTime)"
    Write-Host "Last Task Result:    $($info.LastTaskResult)"
    Write-Host "Next Run Time:       $($info.NextRunTime)"
    Write-Host "Missed Runs:         $($info.NumberOfMissedRuns)"
    Write-Host "Triggers:            $($existingTask.Triggers.CimClass.CimClassName -join ', ')"
    Write-Host "--------------------------------------------------" -ForegroundColor Gray
    return
}

# --- 2. Test Run ---
if ($TestRun) {
    Write-Step "Triggering immediate on-demand run of '$TaskName'..."
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existingTask) {
        Write-Err "Cannot test run: Task '$TaskName' is not registered."
        exit 1
    }
    Start-ScheduledTask -TaskName $TaskName
    Write-Success "Task '$TaskName' triggered successfully. Check M:\chakramodel\logs\backup_sync.log for output."
    return
}

# --- 3. Elevation Check ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warn "Registering/Unregistering a Windows Scheduled Task requires Administrator privileges."
    Write-Host "Relaunching elevated PowerShell prompt..." -ForegroundColor Yellow
    $scriptInvocation = $MyInvocation.MyCommand.Definition
    $boundArgs = @()
    foreach ($key in $PSBoundParameters.Keys) {
        $val = $PSBoundParameters[$key]
        if ($val -is [switch]) {
            if ($val) { $boundArgs += "-$key" }
        } else {
            $boundArgs += "-$key `"$val`""
        }
    }
    $argString = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptInvocation`" " + ($boundArgs -join " ")
    Start-Process powershell -Verb RunAs -ArgumentList $argString
    return
}

# --- 4. Unregister Task ---
if ($Unregister) {
    Write-Step "Unregistering scheduled task '$TaskName'..."
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Success "Task '$TaskName' successfully removed."
    } else {
        Write-Warn "Task '$TaskName' was not found. Nothing to remove."
    }
    return
}

# --- 5. Resolve Paths & Prerequisites ---
Write-Step "Validating paths and environment..."

# Resolve Python path
if (-not $PythonPath) {
    $venvPython = "M:\chakramodel\.venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonPath = $venvPython
        Write-Step "Using venv Python: $PythonPath"
    } else {
        $cmdPython = Get-Command python -ErrorAction SilentlyContinue
        if ($cmdPython) {
            $PythonPath = $cmdPython.Source
            Write-Step "Using system Python: $PythonPath"
        } else {
            $fallbackPython = "C:\Users\imgk3\AppData\Local\Programs\Python\Python311\python.exe"
            if (Test-Path $fallbackPython) {
                $PythonPath = $fallbackPython
                Write-Step "Using fallback Python: $PythonPath"
            } else {
                Write-Err "Could not locate python.exe. Please specify -PythonPath explicitly."
                exit 1
            }
        }
    }
}

if (-not (Test-Path $PythonPath)) {
    Write-Err "Python executable not found at: $PythonPath"
    exit 1
}

# Ensure logs directory exists
$logsDir = Join-Path $WorkingDir "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Step "Created logs directory: $logsDir"
}

# Delay string in ISO 8601 duration format (e.g. PT6M)
$delayDuration = "PT$($DelayMinutes)M"
Write-Step "Configured delay: $DelayMinutes minutes ($delayDuration)"

# --- 6. Task Registration ---
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($UseXml -and (Test-Path $XmlPath)) {
    Write-Step "Registering task from XML template: $XmlPath"
    
    [xml]$xmlDoc = Get-Content $XmlPath -Raw
    
    # Update dynamic values in XML
    $xmlDoc.Task.Actions.Exec.Command = $PythonPath
    $xmlDoc.Task.Actions.Exec.Arguments = "`"$ScriptPath`" --startup-task"
    $xmlDoc.Task.Actions.Exec.WorkingDirectory = $WorkingDir
    
    if ($TriggerType -eq "Boot") {
        # Replace LogonTrigger with BootTrigger
        $triggersNode = $xmlDoc.Task.Triggers
        $triggersNode.RemoveAll()
        $bootTrigger = $xmlDoc.CreateElement("BootTrigger", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $enabled = $xmlDoc.CreateElement("Enabled", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $enabled.InnerText = "true"
        $delay = $xmlDoc.CreateElement("Delay", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $delay.InnerText = $delayDuration
        $bootTrigger.AppendChild($enabled) | Out-Null
        $bootTrigger.AppendChild($delay) | Out-Null
        $triggersNode.AppendChild($bootTrigger) | Out-Null
    } else {
        $xmlDoc.Task.Triggers.LogonTrigger.Delay = $delayDuration
    }
    
    $tempXml = [System.IO.Path]::GetTempFileName() + ".xml"
    $xmlDoc.Save($tempXml)
    
    Register-ScheduledTask -Xml (Get-Content $tempXml -Raw) -TaskName $TaskName -Force | Out-Null
    Remove-Item $tempXml -Force -ErrorAction SilentlyContinue
    
} else {
    Write-Step "Building task configuration via ScheduledTasks cmdlets..."
    
    # Action: run python script with --startup-task
    $actionArgs = "`"$ScriptPath`" --startup-task"
    $action = New-ScheduledTaskAction -Execute $PythonPath -Argument $actionArgs -WorkingDirectory $WorkingDir
    
    # Trigger: Logon or Boot with PT6M delay
    if ($TriggerType -eq "Boot") {
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Delay = $delayDuration
    } else {
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
        $trigger.Delay = $delayDuration
    }
    
    # Settings: Laptop battery friendly, ignore new instances, 2h max runtime
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -StartWhenAvailable `
        -Priority 7
    
    # Principal: Interactive token under current user (least privilege, allows mapped drives)
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel LeastPrivilege
    
    # Unregister existing if present
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    
    # Register task
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "ChakraModel daily backup sync & downloads recovery ($TriggerType trigger, $DelayMinutes min delay, 06:00-11:00 window)."
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
}

Write-Success "Task '$TaskName' registered successfully!"
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Trigger:        $TriggerType (Delay: $DelayMinutes minutes)"
Write-Host "  Execution User: $currentUser"
Write-Host "  Python:         $PythonPath"
Write-Host "  Command:        $PythonPath `"$ScriptPath`" --startup-task"
Write-Host "  Working Dir:    $WorkingDir"
Write-Host "  Battery Run:    Enabled (will run on laptop battery)"
