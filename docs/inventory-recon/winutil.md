# Reconocimiento: WinUtil

Fuente: `inventory/upstream/winutil.files.tsv` (SHA fijado `70c23c80641d7370532af2f619b2842658600842`).

**704 ficheros** en el árbol. Comando:
```bash
git -C /tmp/upstream/winutil ls-tree -r -l --full-tree HEAD | wc -l
tail -n +2 inventory/upstream/winutil.files.tsv | wc -l
```

## Ficheros por extensión

Comando: `cut -f4 inventory/upstream/winutil.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`

| ext | ficheros | % |
|---|---:|---:|
| `png` | 258 | 36.6% |
| `ps1` | 197 | 28.0% |
| `mdx` | 116 | 16.5% |
| `jsx` | 18 | 2.6% |
| `astro` | 16 | 2.3% |
| `yaml` | 15 | 2.1% |
| `md` | 14 | 2.0% |
| `json` | 12 | 1.7% |
| `svg` | 11 | 1.6% |
| `css` | 10 | 1.4% |
| `(sin extensión)` | 8 | 1.1% |
| `py` | 7 | 1.0% |
| `js` | 6 | 0.9% |
| `yml` | 5 | 0.7% |
| `cjs` | 2 | 0.3% |
| `ts` | 2 | 0.3% |
| `mjs` | 1 | 0.1% |
| `txt` | 1 | 0.1% |
| `bat` | 1 | 0.1% |
| `xml` | 1 | 0.1% |
| `toml` | 1 | 0.1% |
| `lock` | 1 | 0.1% |
| `xaml` | 1 | 0.1% |
| **total** | **704** | 100% |

## Ficheros por directorio de primer nivel

Comando: `cut -f5 inventory/upstream/winutil.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`

| top_dir | ficheros | % |
|---|---:|---:|
| `config` | 247 | 35.1% |
| `docs` | 209 | 29.7% |
| `functions` | 125 | 17.8% |
| `pester` | 66 | 9.4% |
| `.github` | 27 | 3.8% |
| `tools` | 15 | 2.1% |
| `.` | 11 | 1.6% |
| `scripts` | 2 | 0.3% |
| `lint` | 1 | 0.1% |
| `xaml` | 1 | 0.1% |
| **total** | **704** | 100% |

## Scripts PowerShell

Comando: `awk -F'\t' '$4=="ps1"' inventory/upstream/winutil.files.tsv | wc -l`

- `.ps1` totales: **197**
- `functions/public/*.ps1`: **35**
- `functions/private/*.ps1`: **90**
- otros `.ps1` (raíz, scripts/, tools/, pester/): **72**

## Claves de `config/*.json`

Carga tolerante: `encoding='utf-8-sig'` y `json.loads(..., strict=False)`.
Comando: `python3 -c "import json;print(len(json.loads(open('config/tweaks.json',encoding='utf-8-sig').read(),strict=False)))"`

| fichero | claves primer nivel |
|---|---:|
| `applications.json` | 239 |
| `appnavigation.json` | 11 |
| `appx.json` | 34 |
| `dns.json` | 8 |
| `feature.json` | 33 |
| `preset.json` | 4 |
| `themes.json` | 3 |
| `tweaks.json` | 69 |

## Contraste con el reconocimiento previo

| magnitud | previo | medido | coincide |
|---|---:|---:|:---:|
| `applications.json` | 239 | 239 | sí |
| `tweaks.json` | 69 | 69 | sí |
| `feature.json` | 33 | 33 | sí |
| `appx.json` | 34 | 34 | sí |
| `themes.json` | 3 | 3 | sí |
| `preset.json` | 4 | 4 | sí |
| `appnavigation.json` | 11 | 11 | sí |
| `dns.json` | 8 | 8 | sí |
| `ps1 total` | 197 | 197 | sí |
| `functions/public ps1` | 35 | 35 | sí |
| `functions/private ps1` | 90 | 90 | sí |

