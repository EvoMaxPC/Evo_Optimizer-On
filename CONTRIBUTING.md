# Contribuir a EVO CLEAN

Breve. Lo normativo está en `docs/AGENT_CONTRACT.md`.

## Reglas

1. Trabaja en la rama asignada. **No** hagas merge a `main` sin aprobación.
2. **Conventional Commits**: `feat:`, `fix:`, `docs:`, `ci:`, `test:`, `chore:`.
3. Toda decisión de arquitectura va a `docs/adr/NNNN-titulo.md` (breve:
   contexto, decisión, consecuencias). Copiar código de upstream **exige** ADR.
4. Nada de datos inventados: lo no comprobado se marca **NO VERIFICADO**.
5. Ventanas soportadas y builds viven en `catalog/windows-releases.json`.
   Un build desconocido **no** es compatible.

## Envío

* Antes de pushear: `bash tests/ci/test_publish_report.sh` (debe dar 0 FAIL).
* El workflow `probe` se dispara solo con cambios en `.github/workflows/probe.yml`
  o `tools/ci/**`.
* Los artefactos de CI **no** se guardan en el árbol de la rama de trabajo:
  van a la rama huérfana `ci-report`.
