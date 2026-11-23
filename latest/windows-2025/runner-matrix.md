# Runner: windows-2025

| Campo | Valor |
|---|---|
| OSCaption | Microsoft Windows Server 2025 Datacenter |
| ProductName(reg) | Windows Server 2025 Datacenter |
| EditionID | ServerDatacenter |
| InstallationType | Server |
| CurrentBuildNumber | 26100 |
| UBR | 33828 |
| DisplayVersion | 24H2 |
| Version(OS) | 10.0.26100 |
| BuildNumber(OS) | 26100 |
| PROCESSOR_ARCHITECTURE | AMD64 |
| PROCESSOR_ARCHITEW6432 |  |
| RUNNER_NAME | GitHub Actions 1000000793 |
| RUNNER_OS | Windows |
| RUNNER_ARCH | X64 |
| ImageOS | win25-vs2026 |
| ImageVersion | 20261116.315.1 |

**Clasificacion: SERVER (no objetivo EVO)**

- InstallationType crudo: `Server`
- ProductName crudo: `Windows Server 2025 Datacenter`

## Herramientas

- pwsh: EXISTE (C:\Program Files\PowerShell\7\pwsh.exe)
- powershell (este shell): 5.1.26100.33822
- dotnet --list-sdks:
  - `8.0.134 [C:\Program Files\dotnet\sdk]`
  - `8.0.206 [C:\Program Files\dotnet\sdk]`
  - `8.0.319 [C:\Program Files\dotnet\sdk]`
  - `8.0.428 [C:\Program Files\dotnet\sdk]`
  - `9.0.124 [C:\Program Files\dotnet\sdk]`
  - `9.0.205 [C:\Program Files\dotnet\sdk]`
  - `9.0.321 [C:\Program Files\dotnet\sdk]`
  - `10.0.115 [C:\Program Files\dotnet\sdk]`
  - `10.0.204 [C:\Program Files\dotnet\sdk]`
  - `10.0.303 [C:\Program Files\dotnet\sdk]`
  - `10.0.404 [C:\Program Files\dotnet\sdk]`
  - `11.0.100 [C:\Program Files\dotnet\sdk]`
- winget: v1.29.380
- choco: 2.7.5
- git: git version 2.56.1.windows.1

## Shell de usuario y AppX

- explorer.exe: CORRIENDO (1 proceso/s, pid 1324)
- procesos fuera de sesion 0: 31
- AppX instalados (Get-AppxPackage): 57
- Microsoft.WindowsStore: AUSENTE

## Servicios

| Servicio | Estado | TipoInicio |
|---|---|---|
| WSearch | Stopped | Disabled |
| SysMain | Stopped | Disabled |
| DiagTrack | Stopped | Disabled |
| wuauserv | Running | Manual |
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
device                  partition=\Device\HarddiskVolume2
path                    \EFI\Microsoft\Boot\bootmgfw.efi
description             Windows Boot Manager
locale                  en-US
inherit                 {globalsettings}
bootshutdowndisabled    Yes
default                 {current}
resumeobject            {6019ac89-debe-11f1-aef6-3833c5d5ecc5}
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
recoverysequence        {6019ac8d-debe-11f1-aef6-3833c5d5ecc5}
displaymessageoverride  Recovery
recoveryenabled         No
testsigning             Yes
isolatedcontext         Yes
allowedinmemorysettings 0x15000075
osdevice                partition=C:
systemroot              \Windows
resumeobject            {6019ac89-debe-11f1-aef6-3833c5d5ecc5}
nx                      OptOut
bootstatuspolicy        IgnoreAllFailures
hypervisorlaunchtype    Auto
hypervisorschedulertype Root
ems                     Yes
```

- Tareas programadas: 210
- Estado Ready: 121

---
generado: 2026-11-23T21:11:25Z sha=49bfc3fd4747492d5f5eb686fa8ac3939b90b26b run=45267030334
