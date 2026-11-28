# Esquema del manifiesto de tweaks de Atlas

Medido en el pin `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`.
Fichero: `package/Executables/AtlasModules/Scripts/Tweaks/tweaks.manifest.psd1`
(267 líneas). Solo se transcriben **campos, tipos y contadores**; ningún cuerpo
de script.

## Contrato que declara el propio Atlas

`…/Atlas.Tweaks/Domain/Manifest.ps1:10-13`:

```powershell
$script:AtlasTweakCategoryKeys   = @('Name', 'ParentModes', 'Tweaks')
$script:AtlasTweakStandaloneKeys = @('Slug', 'ParentModes')
$script:AtlasTweakDisabledKeys   = @('Slug', 'Reason')
$script:AtlasTweakParentModes    = @('Fresh', 'Upgrade')
```

Es decir: hay **tres formas de entrada** y `ParentModes` solo admite `Fresh`
y `Upgrade`. El validador está en `Manifest.ps1:41` (`Test-AtlasTweakManifest`).

## Las tres formas

### 1. Dentro de una categoría (174 entradas, 94,5 %)

```powershell
Categories = @(
    @{
        Name        = 'networking'
        ParentModes = @('Fresh', 'Upgrade')
        Tweaks      = @(
            'atlas-network-settings'
            'shares/restrict-anonymous-access'
        )
    }
)
```

`tweaks.manifest.psd1:15-27`. Campos y tipos:

| campo | tipo | ejemplo | obligatorio |
|---|---|---|---|
| `Name` | string | `'networking'` | sí (validador: `Test-Slug`) |
| `ParentModes` | string[] con `Fresh`/`Upgrade` | `@('Fresh','Upgrade')` | sí |
| `Tweaks` | string[] de slugs **relativos a la categoría** | `'shares/restrict-anonymous-access'` | sí |

Ojo: `networking` y `performance` tienen el bloque `ParentModes` **dentro** de
los paréntesis exteriores de `@(`, así que un parser que corte `Tweaks = @(…)`
en el primer `)` pierde sus entradas. Es el fallo que tenía el paso 4d y que el
4e corrigió (74 slugs perdidos).

### 2. `Standalone` (3 entradas) — habilitadas fuera de una categoría

```powershell
Standalone = @(
    @{ Slug = 'qol/set-hidden-settings-pages'; ParentModes = @('Fresh') }
    @{ Slug = 'scripts/set-power-settings';    ParentModes = @('Fresh') }
    @{ Slug = 'qol/appearance/atlas-theme-upgrade'; ParentModes = @('Upgrade') }
)
```

`tweaks.manifest.psd1:245-254`. `Slug` ya lleva la ruta completa.

### 3. `Disabled` (5 entradas) — clasificadas, no aplicadas

```powershell
Disabled = @(
    @{ Slug = 'networking/disable-llmnr'; Reason = 'Preserves single-label home-LAN name resolution...' }
    ...
)
```

`tweaks.manifest.psd1:257-266`. Campos `Slug` (string) y `Reason` (string
libre). Los cinco: `networking/disable-llmnr`, `performance/disable-game-bar`,
`qol/explorer/disable-folders-this-pc`,
`qol/startup-shutdown/enable-verbose-messages`,
`qol/startup-shutdown/force-end-shutdown-apps`.

## Ejemplo con solo campos escalares

Entrada real de `Standalone` tal cual (escalares y un array de una cadena):

```
Slug = 'scripts/set-power-settings'
ParentModes = @('Fresh')
```

## Cómo se enumeran los `.psd1`

1. `Invoke-TweaksPhase.ps1:123` carga el manifiesto con
   `Get-AtlasTweakManifest -Path <tweaksRoot>\tweaks.manifest.psd1`.
2. `Manifest.ps1:26` compone esa ruta por defecto:
   `Join-Path (Get-AtlasContext).AtlasModulesPath 'Scripts\Tweaks\tweaks.manifest.psd1'`.
3. Para cada categoría se recorren sus `Tweaks` en orden; los `Standalone` van
   como pasos propios (`Invoke-TweaksPhase.ps1:119-148`).
4. `Manifest.ps1:351` enumera además todos los ficheros con
   `Get-ChildItem -LiteralPath $TweaksRoot -Filter '*.psd1' -Recurse -File`
   **solo para validar** que todo `.psd1` está clasificado.

## Cómo se resuelve un id a un fichero

`Manifest.ps1:181`:

```powershell
$definitionPath = Join-Path -Path $TweaksRoot -ChildPath (($Slug -replace '/', '\') + '.psd1')
```

Es decir: `id` + `.psd1`, con `/` → `\`, bajo `Scripts\Tweaks\`.
El slug no puede tener `\`, ni empezar o acabar en `/`, ni `..`, ni extensión
(`Test-Slug`, `Manifest.ps1:98-118`), y dentro de `Categories` debe empezar por
el nombre de su categoría — por eso el id completo es `<Name>/<slug>`.

## Carga real del `.psd1`

- `Invoke-TweaksPhase.ps1:130`: `Import-AtlasDataFile -LiteralPath $path`.
- `Data.ps1:16`: `Microsoft.PowerShell.Utility\Import-PowerShellDataFile -LiteralPath $LiteralPath`.
- `Invoke.ps1:238` (`Invoke-AtlasTweak`): aplica en orden
  **Registry → Services → ScheduledTasks → Toggle → Run → RemovePaths → Script**
  (documentado en su comentario de ayuda, líneas 230-237).

## Cifras medidas

```
entradas              : 182 (ids distintos 182, 0 duplicados)
enabled / disabled    : 177 / 5
por seccion           : Categories 174 | Standalone 3 | Disabled 5
parent_modes          : Fresh|Upgrade 174 | Fresh 2 | Upgrade 1 | (vacio) 5
sin .psd1             : 0
.psd1 en Tweaks/      : 183; 182 con entrada, 1 sin ella -> el propio
                        tweaks.manifest.psd1
```

Comando: `python3 tools/ledger_extract/extract_atlas_manifest.py --json`.

## Lo que NO se puede afirmar

- **NO VERIFICADO** el efecto de cada `.psd1`: aquí solo se mide la estructura
  del manifiesto y la resolución de rutas.
- El manifiesto **no menciona ningún `toggle_id` del catálogo** (0 de 91). La
  relación catálogo → `.psd1` sigue sin estar declarada en el pin.
