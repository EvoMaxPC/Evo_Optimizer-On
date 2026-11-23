# Reconocimiento: AtlasOS

Fuente: `inventory/upstream/atlas.files.tsv` (SHA fijado `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`).

**1550 ficheros** en el árbol. Comando:
```bash
git -C /tmp/upstream/atlas ls-tree -r -l --full-tree HEAD | wc -l
tail -n +2 inventory/upstream/atlas.files.tsv | wc -l
```

## Ficheros por extensión

Comando: `cut -f4 inventory/upstream/atlas.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`

| ext | ficheros | % |
|---|---:|---:|
| `ps1` | 372 | 24.0% |
| `rs` | 326 | 21.0% |
| `psd1` | 298 | 19.2% |
| `cmd` | 188 | 12.1% |
| `md` | 67 | 4.3% |
| `(sin extensión)` | 51 | 3.3% |
| `url` | 45 | 2.9% |
| `json` | 28 | 1.8% |
| `yml` | 24 | 1.5% |
| `png` | 20 | 1.3% |
| `psm1` | 20 | 1.3% |
| `ftl` | 15 | 1.0% |
| `reg` | 11 | 0.7% |
| `toml` | 10 | 0.6% |
| `theme` | 7 | 0.5% |
| `yaml` | 6 | 0.4% |
| `svg` | 6 | 0.4% |
| `txt` | 5 | 0.3% |
| `lock` | 5 | 0.3% |
| `ico` | 5 | 0.3% |
| `exe` | 4 | 0.3% |
| `lnk` | 4 | 0.3% |
| `cab` | 4 | 0.3% |
| `orig` | 3 | 0.2% |
| `xml` | 3 | 0.2% |
| `sh` | 3 | 0.2% |
| `vbs` | 3 | 0.2% |
| `zip` | 3 | 0.2% |
| `rc` | 2 | 0.1% |
| `hlsl` | 2 | 0.1% |
| `patch` | 2 | 0.1% |
| `jsonc` | 1 | 0.1% |
| `ini` | 1 | 0.1% |
| `sha256` | 1 | 0.1% |
| `gif` | 1 | 0.1% |
| `jpg` | 1 | 0.1% |
| `cs` | 1 | 0.1% |
| `container` | 1 | 0.1% |
| `example` | 1 | 0.1% |
| **total** | **1550** | 100% |

## Ficheros por directorio de primer nivel

Comando: `cut -f5 inventory/upstream/atlas.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`

| top_dir | ficheros | % |
|---|---:|---:|
| `package` | 842 | 54.3% |
| `app` | 451 | 29.1% |
| `tests` | 124 | 8.0% |
| `tools` | 33 | 2.1% |
| `.github` | 31 | 2.0% |
| `services` | 28 | 1.8% |
| `docs` | 24 | 1.5% |
| `.` | 12 | 0.8% |
| `.vscode` | 3 | 0.2% |
| `.zed` | 2 | 0.1% |
| **total** | **1550** | 100% |

## Tests Pester

Comando: `awk -F'\t' '$1 ~ /^tests\// && $4=="ps1"' inventory/upstream/atlas.files.tsv | wc -l`

- `.ps1` bajo `tests/`: **109**

## Contraste con el reconocimiento previo

| magnitud | previo | medido | coincide |
|---|---:|---:|:---:|
| `.ps1` | 372 | 372 | sí |
| `.cmd` | 188 | 188 | sí |
| `.reg` | 11 | 11 | sí |
| `.yml` | 24 | 24 | sí |
| `.yaml` | 6 | 6 | sí |
| `tests/*.ps1 (Pester)` | 109 | 109 | sí |

