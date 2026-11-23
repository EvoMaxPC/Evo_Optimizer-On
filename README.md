# EVO CLEAN

Optimizador **exclusivo para Windows** (10 22H2 · 11 23H2/24H2/25H2/26H2),
C# / .NET 10 LTS (`net10.0-windows`) con UI WPF. Licencia **GPL-3.0**.

> Estado: **Paso 1** — estructura, contrato, licencias, fijación de upstream y
> canal de informes CI. Todavía no hay código de producto.

## Documentos que mandan

| Fichero | Qué es |
|---|---|
| `docs/AGENT_CONTRACT.md` | Contrato de trabajo y requisitos maestros (REQ-000…006). **Se lee al inicio de cada capa.** |
| `docs/requirements/INVENTARIO_USUARIO.md` | Inventario del responsable (17 secciones). **Pendiente de recibir.** |
| `inventory/upstream.lock.json` | SHAs fijados de WinUtil y AtlasOS. |
| `THIRD_PARTY_NOTICES.md` | Atribuciones (MIT de WinUtil, GPL-3.0 de AtlasOS). |
| `docs/reports/` | Informes por paso, con evidencias literales. |
| `docs/adr/` | Decisiones de arquitectura. |

## Herramientas

```bash
# 1. Reproduce las fuentes fijadas en /tmp/upstream (verifica SHA, idempotente)
python3 tools/ledger_extract/fetch_upstream.py

# 2. Pruebas del canal ci-report (crea un remoto bare local, no toca GitHub)
bash tests/ci/test_publish_report.sh

# 3. Publicar artefactos de CI en la rama huérfana ci-report
bash tools/ci/publish-report.sh <directorio> <etiqueta> <estado>
```

## Leer resultados de CI

El CDN de logs (`results-receiver.actions.githubusercontent.com`) está bloqueado
para el agente. Método estándar:

```bash
git fetch origin ci-report
git show FETCH_HEAD:latest/<etiqueta>/runner-matrix.md
```

## Entorno

El agente trabaja en Linux **sin .NET ni PowerShell**. Todo build o test de
.NET/PowerShell ocurre en GitHub Actions (`.github/workflows/probe.yml`).
Los runners hosted de Windows son **Server** (salvo `windows-11-arm`): sirven
para compilar, no para validar AppX/Store/Explorer.
