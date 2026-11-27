# Informe ETAPA 6-B — Dejar todo en verde y obtener el .zip

## Estado inicial (HEAD a775156cb)

- dotnet-ci: rojo en ambos runners por MC3074 en `src/Evo.App/App.xaml(7,14)`: `ViewModelLocator` no existe en `clr-namespace:Evo.App`.
- ledger-verify: rojo porque el validador espera 9 proyectos y ahora hay 13 (Evo.Windows y Evo.App + sus tests, agregados en Etapas 4 y 5).
- release-exe: rojo (run 45987279908). El check-run "Publish exe win-x64" SÍ se creó, pero falló con exit code 1 en el paso `dotnet publish src/Evo.App` por el mismo MC3074 de App.xaml. Causa real: **compilación falla por XAML roto**, no YAML inválido.

## Arreglos aplicados (este push)

1. `src/Evo.App/App.xaml`: se removió `<local:ViewModelLocator x:Key="Locator" />` (clase inexistente).
2. `tools/dotnet_tools/validate_dotnet_structure.py`: EXPECTED_PROJECTS pasó de 9 a 13 proyectos (se agregaron Evo.Windows, Evo.App, Evo.Windows.Tests, Evo.App.Tests); ALLOWED_REFERENCES se extendió con Evo.Windows y Evo.App.
3. `tests/test_paso7.py`: `test_validador_reconoce_los_13_proyectos` y `test_validador_declara_los_13_proyectos_esperados` esperan 13; el conteo de csproj en sln espera 13.
4. `tests/test_paso6.py`: comentario actualizado a 13 proyectos.
5. `.github/workflows/release-exe.yml`: setup-dotnet usa `global-json-file: global.json`.

## Validación local

- `python3 tools/dotnet_tools/validate_dotnet_structure.py`: `estructura .NET: OK`, 13 proyectos.
- `python -m pytest tests/test_paso6.py tests/test_paso7.py -q`: `40 passed`.

## Queda por verificar en CI

- dotnet-ci push y PR: deberían pasar verde al compilar Evo.App sin el XAML roto.
- ledger-verify: debería pasar verde con el validador a 13 proyectos.
- release-exe: debería publicar `EvoClean-preview-win-x64.zip` con el .exe y `catalog/`.

FIN ETAPA 6-B (pendiente de resultados de CI)
