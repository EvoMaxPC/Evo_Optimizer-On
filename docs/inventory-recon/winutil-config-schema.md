# Esquema real de `config/*.json` de WinUtil

Generado por `tools/ledger_extract/config_schema.py` sobre el clon en el SHA `70c23c80641d7370532af2f619b2842658600842`.

Carga: `encoding='utf-8-sig'` + `json.loads(..., strict=False)`.

Comando:
```bash
python3 tools/ledger_extract/config_schema.py
```

## Resumen

| fichero | tipo raíz | claves nivel 1 | campos por entrada |
|---|---|---:|---|
| `applications.json` | object | 239 | 8 |
| `appnavigation.json` | object | 11 | 7 |
| `appx.json` | object | 34 | 6 |
| `dns.json` | object | 8 | 6 |
| `feature.json` | object | 33 | 10 |
| `preset.json` | object | 4 | 1 |
| `themes.json` | object | 3 | 89 |
| `tweaks.json` | object | 69 | 14 |

## `applications.json` — 239 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `category` | 239 | `str`×239 |
| `content` | 239 | `str`×239 |
| `description` | 239 | `str`×239 |
| `link` | 239 | `str`×239 |
| `winget` | 239 | `str`×239 |
| `foss` | 238 | `bool`×238 |
| `choco` | 236 | `str`×236 |
| `_comment` | 1 | `str`×1 |

## `appnavigation.json` — 11 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `Content` | 11 | `str`×11 |
| `Category` | 11 | `str`×11 |
| `Type` | 11 | `str`×11 |
| `Order` | 11 | `str`×11 |
| `Description` | 11 | `str`×11 |
| `GroupName` | 2 | `str`×2 |
| `Checked` | 2 | `bool`×2 |

## `appx.json` — 34 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `Category` | 34 | `str`×34 |
| `Content` | 34 | `str`×34 |
| `Description` | 34 | `str`×34 |
| `Panel` | 34 | `str`×34 |
| `PackageId` | 34 | `str`×34 |
| `StoreId` | 31 | `str`×31 |

## `dns.json` — 8 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `Primary` | 8 | `str`×8 |
| `Secondary` | 8 | `str`×8 |
| `Primary6` | 8 | `str`×8 |
| `Secondary6` | 8 | `str`×8 |
| `DohTemplate` | 8 | `str`×8 |
| `BenchmarkEligible` | 2 | `bool`×2 |

## `feature.json` — 33 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `Content` | 33 | `str`×33 |
| `category` | 33 | `str`×33 |
| `panel` | 33 | `str`×33 |
| `link` | 33 | `str`×33 |
| `Type` | 24 | `str`×24 |
| `ButtonWidth` | 24 | `str`×24 |
| `InvokeScript` | 21 | `list[str]`×18, `list[]`×3 |
| `Description` | 10 | `str`×10 |
| `function` | 10 | `str`×10 |
| `feature` | 9 | `list[str]`×6, `list[]`×3 |

## `preset.json` — 4 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `(valor escalar)` | 4 | `list[str]`×4 |

## `themes.json` — 3 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `AppIconShadowColor` | 2 | `str`×2 |
| `AppIconShadowOpacity` | 2 | `str`×2 |
| `AppInstallUnselectedColor` | 2 | `str`×2 |
| `AppInstallHighlightedColor` | 2 | `str`×2 |
| `AppInstallSelectedColor` | 2 | `str`×2 |
| `ComboBoxForegroundColor` | 2 | `str`×2 |
| `ComboBoxBackgroundColor` | 2 | `str`×2 |
| `LabelboxForegroundColor` | 2 | `str`×2 |
| `MainForegroundColor` | 2 | `str`×2 |
| `MainBackgroundColor` | 2 | `str`×2 |
| `MainGradientTopColor` | 2 | `str`×2 |
| `MainGradientBottomColor` | 2 | `str`×2 |
| `SurfaceBackgroundColor` | 2 | `str`×2 |
| `LabelBackgroundColor` | 2 | `str`×2 |
| `LinkForegroundColor` | 2 | `str`×2 |
| `LinkHoverForegroundColor` | 2 | `str`×2 |
| `ScrollBarBackgroundColor` | 2 | `str`×2 |
| `ScrollBarHoverColor` | 2 | `str`×2 |
| `ScrollBarDraggingColor` | 2 | `str`×2 |
| `ProgressBarForegroundColor` | 2 | `str`×2 |
| `ProgressBarErrorColor` | 2 | `str`×2 |
| `ProgressBarWarningColor` | 2 | `str`×2 |
| `ProgressBarBackgroundColor` | 2 | `str`×2 |
| `ButtonInstallBackgroundColor` | 2 | `str`×2 |
| `ButtonTweaksBackgroundColor` | 2 | `str`×2 |
| `ButtonConfigBackgroundColor` | 2 | `str`×2 |
| `ButtonUpdatesBackgroundColor` | 2 | `str`×2 |
| `ButtonWin11ISOBackgroundColor` | 2 | `str`×2 |
| `ButtonAppxBackgroundColor` | 2 | `str`×2 |
| `ButtonInstallForegroundColor` | 2 | `str`×2 |
| `ButtonTweaksForegroundColor` | 2 | `str`×2 |
| `ButtonConfigForegroundColor` | 2 | `str`×2 |
| `ButtonUpdatesForegroundColor` | 2 | `str`×2 |
| `ButtonWin11ISOForegroundColor` | 2 | `str`×2 |
| `ButtonAppxForegroundColor` | 2 | `str`×2 |
| `ButtonBackgroundColor` | 2 | `str`×2 |
| `ButtonBackgroundPressedColor` | 2 | `str`×2 |
| `ButtonBackgroundMouseoverColor` | 2 | `str`×2 |
| `ButtonBackgroundSelectedColor` | 2 | `str`×2 |
| `ButtonForegroundColor` | 2 | `str`×2 |
| `ToggleButtonOnColor` | 2 | `str`×2 |
| `ToggleButtonOffColor` | 2 | `str`×2 |
| `ToolTipBackgroundColor` | 2 | `str`×2 |
| `BorderColor` | 2 | `str`×2 |
| `BorderOpacity` | 2 | `str`×2 |
| `AppEntryWidth` | 1 | `str`×1 |
| `AppEntryFontSize` | 1 | `str`×1 |
| `AppEntryIconSize` | 1 | `str`×1 |
| `AppEntryMargin` | 1 | `str`×1 |
| `AppEntryBorderThickness` | 1 | `str`×1 |
| `CustomDialogFontSize` | 1 | `str`×1 |
| `CustomDialogFontSizeHeader` | 1 | `str`×1 |
| `CustomDialogLogoSize` | 1 | `str`×1 |
| `CustomDialogWidth` | 1 | `str`×1 |
| `CustomDialogHeight` | 1 | `str`×1 |
| `FontSize` | 1 | `str`×1 |
| `FontFamily` | 1 | `str`×1 |
| `HeaderFontSize` | 1 | `str`×1 |
| `Win11StepTitleFontSize` | 1 | `str`×1 |
| `Win11StepHeroFontSize` | 1 | `str`×1 |
| `Win11LogFontFamily` | 1 | `str`×1 |
| `HeaderFontFamily` | 1 | `str`×1 |
| `CheckBoxBulletDecoratorSize` | 1 | `str`×1 |
| `CheckBoxMargin` | 1 | `str`×1 |
| `TabContentMargin` | 1 | `str`×1 |
| `TabButtonFontSize` | 1 | `str`×1 |
| `TabButtonWidth` | 1 | `str`×1 |
| `TabButtonHeight` | 1 | `str`×1 |
| `TabRowHeightInPixels` | 1 | `str`×1 |
| `ToolTipWidth` | 1 | `str`×1 |
| `IconFontSize` | 1 | `str`×1 |
| `IconButtonSize` | 1 | `str`×1 |
| `SettingsIconFontSize` | 1 | `str`×1 |
| `CloseIconFontSize` | 1 | `str`×1 |
| `GroupBorderBackgroundColor` | 1 | `str`×1 |
| `ButtonFontSize` | 1 | `str`×1 |
| `ButtonFontFamily` | 1 | `str`×1 |
| `ButtonWidth` | 1 | `str`×1 |
| `ButtonHeight` | 1 | `str`×1 |
| `ConfigTabButtonFontSize` | 1 | `str`×1 |
| `ConfigUpdateButtonFontSize` | 1 | `str`×1 |
| `SearchBarWidth` | 1 | `str`×1 |
| `SearchBarHeight` | 1 | `str`×1 |
| `SearchBarTextBoxFontSize` | 1 | `str`×1 |
| `SearchBarClearButtonFontSize` | 1 | `str`×1 |
| `CheckboxMouseOverColor` | 1 | `str`×1 |
| `ButtonBorderThickness` | 1 | `str`×1 |
| `ButtonMargin` | 1 | `str`×1 |
| `ButtonCornerRadius` | 1 | `str`×1 |

## `tweaks.json` — 69 claves de nivel 1

| campo | frecuencia | tipos observados |
|---|---:|---|
| `Content` | 69 | `str`×69 |
| `category` | 69 | `str`×69 |
| `panel` | 69 | `str`×69 |
| `link` | 69 | `str`×69 |
| `Description` | 66 | `str`×66 |
| `registry` | 50 | `list[object]`×50 |
| `Type` | 29 | `str`×29 |
| `InvokeScript` | 27 | `list[str]`×27 |
| `UndoScript` | 22 | `list[str]`×22 |
| `service` | 4 | `list[object]`×4 |
| `ComboItems` | 2 | `str`×2 |
| `ButtonWidth` | 2 | `str`×2 |
| `Checked` | 1 | `str`×1 |
| `ComboDescriptions` | 1 | `object`×1 |

<details><summary>Subcampos de objetos anidados</summary>

| subcampo | frecuencia | tipos |
|---|---:|---|
| `ComboDescriptions.Enabled` | 1 | `str`×1 |
| `ComboDescriptions.Disabled (Compatibility)` | 1 | `str`×1 |
| `ComboDescriptions.Fully Disabled` | 1 | `str`×1 |

</details>


