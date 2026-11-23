# Runner: ***REDACTED***

| Campo | Valor |
|---|---|
| OSCaption | Microsoft Windows Server 2022 Datacenter |
| ProductName(reg) | Windows Server 2022 Datacenter |
| EditionID | ServerDatacenter |
| InstallationType | Server |
| CurrentBuildNumber | 20348 |
| UBR | 5870 |
| DisplayVersion | 21H2 |
| Version(OS) | 10.0.20348 |
| BuildNumber(OS) | 20348 |
| PROCESSOR_ARCHITECTURE | AMD64 |
| PROCESSOR_ARCHITEW6432 |  |
| RUNNER_NAME | ***REDACTED*** |
| RUNNER_OS | Windows |
| RUNNER_ARCH | X64 |
| ImageOS | win22 |
| ImageVersion | ***REDACTED*** |

**Clasificacion: SERVER (no objetivo EVO)**

- InstallationType crudo: `Server`
- ProductName crudo: `Windows Server 2022 Datacenter`

## Herramientas

- pwsh: EXISTE (***REDACTED***\PowerShell\7\pwsh.exe)
- powershell (este shell): 5.1.20348.5773
- dotnet --list-sdks:
  - `8.0.134 [***REDACTED***\dotnet\sdk]`
  - `8.0.206 [***REDACTED***\dotnet\sdk]`
  - `8.0.319 [***REDACTED***\dotnet\sdk]`
  - `8.0.428 [***REDACTED***\dotnet\sdk]`
  - `9.0.124 [***REDACTED***\dotnet\sdk]`
  - `9.0.205 [***REDACTED***\dotnet\sdk]`
  - `9.0.321 [***REDACTED***\dotnet\sdk]`
  - `10.0.115 [***REDACTED***\dotnet\sdk]`
  - `10.0.204 [***REDACTED***\dotnet\sdk]`
  - `10.0.303 [***REDACTED***\dotnet\sdk]`
  - `10.0.404 [***REDACTED***\dotnet\sdk]`
  - `11.0.100 [***REDACTED***\dotnet\sdk]`
## Shell de usuario y AppX

- explorer.exe: CORRIENDO (1 proceso/s, pid 4552)
- procesos fuera de sesion 0: 29
- AppX instalados (Get-AppxPackage): 32
- Microsoft.WindowsStore: AUSENTE

## Servicios

| Servicio | Estado | TipoInicio |
|---|---|---|
| WSearch | Stopped | Disabled |
| SysMain | Stopped | Disabled |
| DiagTrack | Stopped | Disabled |
| wuauserv | Stopped | Disabled |
| BthServ | Stopped | Manual |
| Spooler | Running | Auto |

## powercfg / bcdedit

- powercfg /list (exit=0):
```

Existing Power Schemes (* Active)
-----------------------------------
Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance) *
Power Scheme GUID: a1841308-3541-4fab-bc81-f71556f20b4a  (Power saver)
```
- bcdedit /enum (exit=0):
```

Windows Boot Manager
--------------------
identifier              {bootmgr}
device                  partition=\Device\HarddiskVolume3
path                    \EFI\Microsoft\Boot\bootmgfw.efi
description             Windows Boot Manager
locale                  en-US
inherit                 {globalsettings}
bootshutdowndisabled    Yes
default                 {current}
resumeobject            {22bb874b-d05d-11f1-9b3c-3833c5d5f0f0}
displayorder            {current}
toolsdisplayorder       {memdiag}
timeout                 30

Windows Boot Loader
-------------------
identifier              {current}
device                  partition=C:
path                    \Windows\system32\winload.efi
description             Windows Server
locale                  en-US
inherit                 {bootloadersettings}
recoveryenabled         No
testsigning             Yes
isolatedcontext         Yes
allowedinmemorysettings 0x15000075
osdevice                partition=C:
systemroot              \Windows
resumeobject            {22bb874b-d05d-11f1-9b3c-3833c5d5f0f0}
nx                      OptOut
bootstatuspolicy        IgnoreAllFailures
hypervisorlaunchtype    Auto
hypervisorschedulertype Root
ems                     Yes
```

- Tareas programadas: 163
- Estado Ready: 62

---
generado: 2026-11-23T21:05:57Z sha=***REDACTED*** run=***REDACTED***
