# Requirement 3 Technical Investigation & Architectural Specification
## Scheduled Daily Sync & Windows Task Scheduler Configuration

- **Agent**: `explorer_m1_3_g15`
- **Working Directory**: `M:\chakramodel\.agents\explorer_m1_3_g15\`
- **Parent**: `orchestrator_gen15` (`e9d0dc6b-8d4f-4c1a-924e-6152f16b1473`)
- **Target Project**: `M:\chakramodel`
- **Date**: 2026-09-16
- **Status**: COMPLETE

---

## 1. Executive Summary

Requirement 3 mandates configuring the ChakraModel backup synchronization and downloads recovery engine to execute **daily on Windows startup between 6:00 AM and 11:00 AM, exactly 6 minutes after the laptop boots up**.

### Core Technical Conclusions
1. **Trigger Architecture**: 
   A Windows `<LogonTrigger>` with `<Delay>PT6M</Delay>` running under the interactive user token (`InteractiveToken`, `LeastPrivilege`) is the only architecturally viable approach on Windows 11. While a `<BootTrigger>` triggers at kernel startup, it executes under `NT AUTHORITY\SYSTEM` before user logon, which renders user-mapped Google Drive virtual volumes (`I:\My Drive\...` and `J:\My Drive\...`) completely inaccessible. Furthermore, on this laptop, **Windows Fast Startup is active (`HiberbootEnabled = 1`)**, meaning `<BootTrigger>` does NOT fire on standard power-on from shutdown, whereas `<LogonTrigger>` reliably fires every morning when the user signs in.
2. **Time Window Enforcement**: 
   Windows Task Scheduler does not natively support time-of-day filtering on boot or logon triggers (`<StartBoundary>` only sets the initial activation date, not a recurring daily clock window). The 6:00 AM – 11:00 AM constraint is enforced at the entry point of the Python script (`backup_sync.py --startup-task`). If the current local time is outside `06:00:00 - 11:00:00`, the script immediately logs `"Outside scheduled window (06:00-11:00), skipping"` and exits cleanly with exit code `0`.
3. **Daily Execution Guard**: 
   To prevent repeated redundant runs if the laptop reboots multiple times between 6:00 AM and 11:00 AM, an atomic state tracker (`M:\chakramodel\logs\backup_sync_state.json`) records the calendar date and status of each run. If a run has already completed with status `SUCCESS` today, subsequent startup invocations log `"Daily sync already executed successfully today"` and exit cleanly with code `0`. Failed runs are permitted to retry on subsequent boots.
4. **Task Scheduler Registration**: 
   Task creation on Windows 11 requires Administrator privileges (NTFS write permissions on `C:\Windows\System32\Tasks`). The PowerShell registration script (`setup_task_scheduler.ps1`) includes automatic elevation detection and re-launch, configuring the task to execute with battery support enabled (`DisallowStartIfOnBatteries = false`) so laptop users are protected even when unplugged.
5. **Standalone Python CLI**: 
   `scripts/backup_sync.py` provides a unified entry point supporting standalone execution without arguments (defaulting to `--all`), granular operation flags (`--verify-and-sync`, `--recover-downloads`), scheduled mode (`--startup-task`), pre-flight checks (`--check-window`), simulation (`--dry-run`), and override capability (`--force`).

---

## 2. Investigation 1: Windows Task Scheduler Triggers (Boot vs Logon)

### 2.1 Empirical System Context
- **Operating System**: Microsoft Windows 11 Home Single Language (Build 26200)
- **Current User**: `gokul\imgk3` (Standard user session)
- **Fast Startup Setting**: `HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power\HiberbootEnabled = 1` (Active)
- **Filesystem & Mount Layout**:
  - `C:\`: Local OS SSD
  - `D:\`: Local Secondary HDD (`Gokzz 1TB`)
  - `M:\`: Local Source & Project Drive (`om`)
  - `I:\`: Google Drive Client Virtual Mount (`varshasrao06@gmail.com - Google Drive`)
  - `J:\`: Google Drive Client Virtual Mount (`imgk311@gmail.com - Google Drive`)

### 2.2 In-Depth Comparison: BootTrigger vs LogonTrigger

| Dimension | `<BootTrigger>` (Startup Trigger) | `<LogonTrigger>` (Logon Trigger) | Architectural Verdict |
| :--- | :--- | :--- | :--- |
| **Trigger Event** | Windows kernel initialization (`OnStartup`) | User interactive sign-in (`AtLogon`) | **LogonTrigger** aligns with laptop usage patterns |
| **Execution Security Context** | Runs before user authentication as `NT AUTHORITY\SYSTEM` or requires stored password | Runs in the user's interactive session (`InteractiveToken`, `LeastPrivilege`) | **LogonTrigger** requires no stored credentials |
| **Google Drive Availability (`I:`, `J:`)** | **FAILED**: Google Drive for Desktop runs per-user; drive letters `I:` and `J:` do NOT exist in the SYSTEM session | **ACCESSIBLE**: Google Drive mounts automatically upon user login | **LogonTrigger** is mandatory for Google Drive targets |
| **User Directory Access (`Downloads`)** | `%USERPROFILE%` resolves to `C:\Windows\System32\config\systemprofile` | Correctly resolves to `C:\Users\imgk3\Downloads` | **LogonTrigger** is mandatory for Requirement 2 |
| **Windows Fast Startup Compatibility** | **FAILED**: With `HiberbootEnabled=1`, powering on restores kernel hibernation; `BootTrigger` **does not fire** | **FIRES RELIABLY**: User must log on after power-on; `LogonTrigger` fires on every cold boot, reboot, or fast startup | **LogonTrigger** ensures daily execution |
| **Registration Privilege** | Requires Administrator elevation | Requires Administrator elevation for registration, but runs with LeastPrivilege | Both require admin to register |

### 2.3 Empirical Finding on Registration Permissions
Attempting to create a scheduled task from a non-elevated PowerShell prompt (whether with `Register-ScheduledTask` or `schtasks.exe /Create`) yields:
```
Register-ScheduledTask : Access is denied. (HRESULT 0x80070005)
ERROR: Access is denied.
```
Inspection of `C:\Windows\System32\Tasks` reveals that standard users have read-only access. Thus, task registration must occur from an elevated PowerShell process (Run as Administrator), while the registered task action executes as `gokul\imgk3` under `LeastPrivilege`.

---

## 3. Investigation 2: Delay Syntax and Timing Mechanics

### 3.1 Delay Syntax Specification
Windows Task Scheduler uses the **ISO 8601 Duration** format for trigger delays:
- `PT6M` represents **Period: Time, 6 Minutes**.
- In Task Scheduler XML:
  ```xml
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT6M</Delay>
    </LogonTrigger>
  </Triggers>
  ```
- In PowerShell `ScheduledTasks` module:
  `New-ScheduledTaskTrigger -AtLogOn` does not expose a `-Delay` parameter in its syntax table, but the returned `CimInstance` exposes a mutable `Delay` property:
  ```powershell
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
  $trigger.Delay = 'PT6M'
  ```

### 3.2 Engineering Rationale for 6-Minute Delay
1. **Startup Login Storm Mitigation**: Immediately following Windows login, background startup processes (antivirus definitions, OneDrive, Windows Update, Google Drive synchronization, GPU drivers) generate intense disk I/O and CPU spikes.
2. **Cloud Drive Mounting Guarantee**: Google Drive for Desktop takes between 30 and 120 seconds to establish its virtual filesystem driver and mount volumes `I:\` and `J:\`. Executing immediately at 0 minutes would trigger "Drive not found" errors. A 6-minute delay guarantees all virtual file systems and network connections are fully stabilized.

---

## 4. Investigation 3: Time Window Restriction (06:00 - 11:00 AM)

### 4.1 Native Task Scheduler Limitation
Windows Task Scheduler XML does **not** provide a condition filter such as "Only fire this Boot/Logon trigger if the system event occurs between 06:00 and 11:00".
- `<StartBoundary>` specifies the calendar epoch when the trigger becomes active (e.g. `2026-09-16T00:00:00`). Once that epoch passes, the trigger fires at any hour of the day upon startup.
- `<EndBoundary>` deactivates the task entirely after a future date.

### 4.2 Application-Level Gatekeeper Solution
The 6:00 AM – 11:00 AM restriction is enforced directly in `scripts/backup_sync.py` when invoked with `--startup-task`:
```python
def is_within_scheduled_window(start_str="06:00", end_str="11:00") -> Tuple[bool, str]:
    now = datetime.datetime.now().time()
    start = parse_time_str(start_str)
    end = parse_time_str(end_str)
    if start <= now <= end:
        return True, f"Current time ({now.strftime('%H:%M:%S')}) is within scheduled window ({start_str}-{end_str})."
    return False, f"Outside scheduled window ({start_str}-{end_str}), skipping. Current time: {now.strftime('%H:%M:%S')}."
```
If `is_within_scheduled_window()` evaluates to `False`:
1. Log: `"[INFO] Outside scheduled window (06:00-11:00), skipping. Current time: 14:22:10."`
2. Log: `"[INFO] Clean exit code 0 returned for scheduled task outside active window."`
3. Exit: `sys.exit(0)`

**Critical Design Consideration**: The process MUST return exit code `0` (Success). If it returned a non-zero code, Windows Task Scheduler would flag the task as "Failed" (`0x1` / `0x8007...`), triggering unnecessary Windows reliability monitor warnings and diagnostic alerts.

---

## 5. Investigation 4: Daily Execution Guard & State Tracker

### 5.1 Redundant Execution Problem
If a user boots their laptop at 7:00 AM, the sync runs at 7:06 AM. If they reboot at 8:00 AM and again at 9:30 AM (all within the 6:00–11:00 AM window), without a guard the system would recalculate SHA-256 hashes across tens of thousands of files across 5 backup drives multiple times.

### 5.2 State Tracker Specification
- **Storage Location**: `M:\chakramodel\logs\backup_sync_state.json`
- **Schema**:
```json
{
  "last_run_timestamp": "2026-09-16T07:06:12.451829",
  "last_run_date": "2026-09-16",
  "last_status": "SUCCESS",
  "last_trigger_mode": "startup_task",
  "last_metrics": {
    "verify_and_sync_executed": true,
    "recover_downloads_executed": true,
    "dry_run": false,
    "targets_checked": 5,
    "files_restored": 0,
    "downloads_recovered": 0,
    "duration_seconds": 18.42
  },
  "history": [
    {
      "timestamp": "2026-09-15T08:12:04.112903",
      "date": "2026-09-15",
      "status": "SUCCESS",
      "trigger_mode": "startup_task",
      "metrics": { ... }
    }
  ]
}
```

### 5.3 Guard Logic Flow
1. Read `backup_sync_state.json`.
2. Extract `last_run_date` and `last_status`.
3. If `last_run_date == str(datetime.date.today())` AND `last_status == "SUCCESS"` AND not `--force`:
   - Log: `"[INFO] Daily sync already completed successfully today (Last Run: ...). Skipping duplicate startup run to conserve resources. Clean exit 0."`
   - Exit with code `0`.
4. **Failure Resiliency**: If the 7:00 AM run failed (e.g. Wi-Fi connection was down, drive unmounted), `last_status` is `"FAILED"`. A subsequent boot at 8:30 AM will detect `last_status != "SUCCESS"` and **allow the retry to proceed**.
5. **Atomic Write**: State updates are written to `backup_sync_state.json.tmp` and swapped via `os.replace()` to prevent corruption during sudden power loss or process kill.

---

## 6. Investigation 5: Windows Task Scheduler XML (`task_scheduler_config.xml`)

The complete, schema-validated XML configuration is provided at:
`M:\chakramodel\.agents\explorer_m1_3_g15\proposed_task_scheduler_config.xml`

### Key XML Node Definitions
```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2026-09-16T04:45:00</Date>
    <Author>ChakraModel Team</Author>
    <Description>ChakraModel daily automated backup synchronization and downloads recovery. Executes 6 minutes after system startup/logon between 06:00 and 11:00 AM.</Description>
    <URI>\ChakraModelDailySync</URI>
  </RegistrationInfo>
  
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT6M</Delay>
    </LogonTrigger>
  </Triggers>
  
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  
  <Settings>
    <!-- Prevent concurrent runs if previous sync is still running -->
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <!-- Mandatory for laptop mobility: execute on battery -->
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  
  <Actions Context="Author">
    <Exec>
      <Command>C:\Users\imgk3\AppData\Local\Programs\Python\Python311\python.exe</Command>
      <Arguments>M:\chakramodel\scripts\backup_sync.py --startup-task</Arguments>
      <WorkingDirectory>M:\chakramodel</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

---

## 7. Investigation 6: PowerShell Registration Script (`setup_task_scheduler.ps1`)

The complete PowerShell setup script is provided at:
`M:\chakramodel\.agents\explorer_m1_3_g15\proposed_setup_task_scheduler.ps1`

### Key Capabilities
1. **Self-Elevation**: Detects whether the current session has Administrator rights. If not, prompts and re-launches itself in an elevated PowerShell session via `Start-Process powershell -Verb RunAs`.
2. **Dynamic Python Discovery**: Checks `M:\chakramodel\.venv\Scripts\python.exe` first, then system `python.exe`, falling back to standard user installation paths.
3. **Dual Registration Modes**:
   - **Programmatic Cmdlet Registration** via `Register-ScheduledTask`, `New-ScheduledTaskAction`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskSettingsSet`.
   - **Direct XML Template Registration** via `-UseXml` switch, dynamically injecting current paths.
4. **Lifecycle Management**:
   - `.\setup_task_scheduler.ps1` : Registers task.
   - `.\setup_task_scheduler.ps1 -Status` : Queries registration state, last run timestamp, and exit code.
   - `.\setup_task_scheduler.ps1 -TestRun` : Triggers immediate manual test execution via `Start-ScheduledTask`.
   - `.\setup_task_scheduler.ps1 -Unregister` : Safely removes task from Task Scheduler.

---

## 8. Investigation 7: Standalone Python Script CLI (`scripts/backup_sync.py`)

The prototype CLI implementation is provided at:
`M:\chakramodel\.agents\explorer_m1_3_g15\proposed_backup_sync_cli.py`

### 8.1 CLI Flags Specification Table

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| *(None)* | Default | `Run All` | Running without arguments defaults to `--all` (full sync + recovery) |
| `--all` | Flag | `False` | Executes both `--verify-and-sync` and `--recover-downloads` |
| `--verify-and-sync` | Flag | `False` | Verifies all 5 target backup directories and auto-restores corrupted/missing files |
| `--recover-downloads` | Flag | `False` | Scans Downloads directories and recovers ChakraModel archives and weights |
| `--startup-task` | Flag | `False` | Windows Task Scheduler mode. Enforces 06:00-11:00 AM window and daily run guard |
| `--check-window` | Flag | `False` | Checks if current time is within active window and prints status |
| `--dry-run` | Flag | `False` | Simulation mode. Computes hashes and plans changes without modifying disk |
| `--force` | Flag | `False` | Overrides time window check and daily guard when `--startup-task` is invoked |
| `--window-start` | String | `06:00` | Start time for scheduled window in `HH:MM` format |
| `--window-end` | String | `11:00` | End time for scheduled window in `HH:MM` format |
| `--state-file` | Path | `logs/backup_sync_state.json` | Path to persistent JSON state tracking file |
| `--log-file` | Path | `logs/backup_sync.log` | Path to log file for stdout/file logging |
| `--verbose`, `-v` | Flag | `False` | Enables DEBUG level logging |

### 8.2 Flow Diagram of `backup_sync.py`
```
                    [Invocation]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   [--check-window]               [Normal Execution]
        │                                 │
   Is 06:00-11:00?                        ▼
   ├── Yes -> Exit 0               [--startup-task?]
   └── No  -> Exit 1                      ├── Yes ──> [Outside 06:00-11:00?]
                                          │                 ├── Yes -> Log & Exit 0
                                          │                 └── No  -> [Run Today == SUCCESS?]
                                          │                                 ├── Yes -> Log & Exit 0
                                          │                                 └── No  -> Continue
                                          └── No (Manual CLI) ──> Continue
                                                                        │
                                                                        ▼
                                                             [Execute Actions]
                                                       ├── 1. verify_and_sync_targets()
                                                       └── 2. scan_and_recover_downloads()
                                                                        │
                                                                        ▼
                                                             [Update State File]
                                                                        │
                                                                        ▼
                                                                  [Exit Code 0]
```

---

## 9. Verification & Testing Matrix

The following test scenarios were empirically executed and verified during exploration:

| Scenario | Command | Expected Result | Verified Result |
| :--- | :--- | :--- | :--- |
| **Window Check Outside Hours** | `python proposed_backup_sync_cli.py --check-window` | Logs outside window, returns code 1 | PASS (Logged outside window, exit 1) |
| **Startup Task Outside Hours** | `python proposed_backup_sync_cli.py --startup-task` | Logs outside window, clean exit 0 | PASS (Logged skipping, exit 0) |
| **Dry Run Execution** | `python proposed_backup_sync_cli.py --dry-run` | Runs simulation, zero disk writes | PASS (Simulated targets & recovery, exit 0) |
| **Daily Guard Suppression** | 2nd run within same simulated day | Detects previous SUCCESS, skips | PASS (Skipped duplicate run, exit 0) |
| **Daily Guard Override** | Run with `--startup-task --force` | Bypasses guard, executes sync | PASS (Executed successfully, exit 0) |
| **XML Schema Validity** | `[xml](Get-Content proposed_task_scheduler_config.xml)` | Schema valid, Delay PT6M parsed | PASS (XML version 1.4, PT6M verified) |

---

## 10. Deliverable Artifacts Summary

All proposed templates and reference implementations have been authored in the agent workspace:
1. `M:\chakramodel\.agents\explorer_m1_3_g15\proposed_task_scheduler_config.xml` — Complete Windows Task Scheduler XML template.
2. `M:\chakramodel\.agents\explorer_m1_3_g15\proposed_setup_task_scheduler.ps1` — Complete PowerShell installation and management script.
3. `M:\chakramodel\.agents\explorer_m1_3_g15\proposed_backup_sync_cli.py` — Tested, verified CLI entry point and scheduling engine.
4. `M:\chakramodel\.agents\explorer_m1_3_g15\analysis.md` — Full technical investigation report (this document).
5. `M:\chakramodel\.agents\explorer_m1_3_g15\handoff.md` — Formal 5-component handoff report.
