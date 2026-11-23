# Runner: windows-11-arm

| Campo | Valor |
|---|---|
| OSCaption | Microsoft Windows 11 Enterprise |
| ProductName(reg) | Windows 10 Enterprise |
| EditionID | Enterprise |
| InstallationType | Client |
| CurrentBuildNumber | 26200 |
| UBR | 9974 |
| DisplayVersion | 25H2 |
| Version(OS) | 10.0.26200 |
| BuildNumber(OS) | 26200 |
| PROCESSOR_ARCHITECTURE | ARM64 |
| PROCESSOR_ARCHITEW6432 |  |
| RUNNER_NAME | GitHub Actions 1000000795 |
| RUNNER_OS | Windows |
| RUNNER_ARCH | ARM64 |
| ImageOS | win11-vs2026-arm64 |
| ImageVersion | 20261115.219.1 |

**Clasificacion: CLIENTE (objetivo EVO)**

- InstallationType crudo: `Client`
- ProductName crudo: `Windows 10 Enterprise`

## Herramientas

- pwsh: EXISTE (C:\Program Files\PowerShell\7\pwsh.exe)
- powershell (este shell): 5.1.26100.9974
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
## Shell de usuario y AppX

- explorer.exe: CORRIENDO (1 proceso/s, pid 7772)
- procesos fuera de sesion 0: 39
- AppX instalados (Get-AppxPackage): 101
- Microsoft.WindowsStore: PRESENTE (22609.1401.13.0)

## Servicios

| Servicio | Estado | TipoInicio |
|---|---|---|
| WSearch | Running | Auto |
| SysMain | Running | Auto |
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
Power Scheme GUID: e9a42b02-d5df-448d-aa00-03f14749eb61  (Ultimate Performance)
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
default                 {current}
resumeobject            {f14e4e9d-dc40-11f1-92fb-7ced8de0f73f}
displayorder            {current}
timeout                 30

Windows Boot Loader
-------------------
identifier              {current}
device                  partition=C:
path                    \Windows\system32\winload.efi
description             Windows 11
locale                  en-US
inherit                 {bootloadersettings}
recoverysequence        {f14e4ea1-dc40-11f1-92fb-7ced8de0f73f}
recoveryenabled         No
testsigning             Yes
isolatedcontext         Yes
allowedinmemorysettings 0x15000075
osdevice                partition=C:
systemroot              \Windows
resumeobject            {f14e4e9d-dc40-11f1-92fb-7ced8de0f73f}
nx                      OptIn
bootmenupolicy          Standard
bootstatuspolicy        IgnoreAllFailures
hypervisorlaunchtype    Auto
hypervisorschedulertype Root
ems                     Yes
```

- Tareas programadas: 253
- Estado Ready: 167

---
generado: 2026-11-23T21:14:45Z sha=49bfc3fd4747492d5f5eb686fa8ac3939b90b26b run=45267030334
