# Paso 2b — Revisión de la partición y sonda con patrones

Generado por `tools/ledger_extract/partition_review.py`. Solo informa: no se modificó ninguna regla de partición.

## winutil — tratamiento x directorio de primer nivel

| top_dir | extract | reference | exclude | total |
|---|---:|---:|---:|---:|
| `config` | 8 | 239 | 0 | 247 |
| `docs` | 0 | 209 | 0 | 209 |
| `functions` | 125 | 0 | 0 | 125 |
| `pester` | 66 | 0 | 0 | 66 |
| `.github` | 0 | 27 | 0 | 27 |
| `tools` | 0 | 15 | 0 | 15 |
| `.` | 3 | 5 | 3 | 11 |
| `scripts` | 2 | 0 | 0 | 2 |
| `lint` | 1 | 0 | 0 | 1 |
| `xaml` | 1 | 0 | 0 | 1 |
| **TOTAL** | **206** | **495** | **3** | **704** |

## winutil — comportamiento en `reference`

Ficheros con extensión de comportamiento en `reference`: **6**

| directorio de 1er nivel | ficheros |
|---|---:|
| `docs` | 3 |
| `tools` | 3 |

| directorio de 2º nivel | ficheros |
|---|---:|
| `docs/package-lock.json` | 1 |
| `docs/package.json` | 1 |
| `docs/tsconfig.json` | 1 |
| `tools/New-WinUtilIcon.ps1` | 1 |
| `tools/devdocs-generator.ps1` | 1 |
| `tools/title-screen` | 1 |

**A REVISAR** (comportamiento en reference fuera de `tests/`, `.github/`, `docs/`, `tools/`, `services/`): **0**

_Ninguno._

## atlas — tratamiento x directorio de primer nivel

| top_dir | extract | reference | exclude | total |
|---|---:|---:|---:|---:|
| `package` | 803 | 39 | 0 | 842 |
| `app` | 152 | 299 | 0 | 451 |
| `tests` | 124 | 0 | 0 | 124 |
| `tools` | 0 | 33 | 0 | 33 |
| `.github` | 0 | 31 | 0 | 31 |
| `services` | 0 | 28 | 0 | 28 |
| `docs` | 0 | 24 | 0 | 24 |
| `.` | 3 | 6 | 3 | 12 |
| `.vscode` | 0 | 3 | 0 | 3 |
| `.zed` | 0 | 2 | 0 | 2 |
| **TOTAL** | **1082** | **465** | **3** | **1550** |

## atlas — comportamiento en `reference`

Ficheros con extensión de comportamiento en `reference`: **235**

| directorio de 1er nivel | ficheros |
|---|---:|
| `app` | 194 |
| `tools` | 19 |
| `services` | 14 |
| `.vscode` | 3 |
| `.github` | 2 |
| `.zed` | 2 |
| `.` | 1 |

| directorio de 2º nivel | ficheros |
|---|---:|
| `app/vendor` | 189 |
| `services/reports` | 8 |
| `tools/dev` | 8 |
| `services/reports-mcp` | 6 |
| `tools/build` | 5 |
| `tools/timer` | 3 |
| `.github/linters` | 2 |
| `app/licenses` | 2 |
| `.vscode/extensions.json` | 1 |
| `.vscode/launch.json` | 1 |
| `.vscode/settings.json` | 1 |
| `.zed/settings.json` | 1 |
| `.zed/tasks.json` | 1 |
| `app/build.rs` | 1 |
| `app/examples` | 1 |

**A REVISAR** (comportamiento en reference fuera de `tests/`, `.github/`, `docs/`, `tools/`, `services/`): **189**

| ruta | ext | bytes |
|---|---|---:|
| `app/vendor/accesskit_windows/.cargo_vcs_info.json` | json | 110 |
| `app/vendor/accesskit_windows/Cargo.toml` | toml | 1973 |
| `app/vendor/accesskit_windows/src/adapter.rs` | rs | 26726 |
| `app/vendor/accesskit_windows/src/context.rs` | rs | 3062 |
| `app/vendor/accesskit_windows/src/filters.rs` | rs | 356 |
| `app/vendor/accesskit_windows/src/lib.rs` | rs | 501 |
| `app/vendor/accesskit_windows/src/node.rs` | rs | 59164 |
| `app/vendor/accesskit_windows/src/subclass.rs` | rs | 6721 |
| `app/vendor/accesskit_windows/src/tests/mod.rs` | rs | 11724 |
| `app/vendor/accesskit_windows/src/tests/simple.rs` | rs | 6907 |
| `app/vendor/accesskit_windows/src/tests/subclassed.rs` | rs | 5483 |
| `app/vendor/accesskit_windows/src/text.rs` | rs | 22508 |
| `app/vendor/accesskit_windows/src/util.rs` | rs | 14687 |
| `app/vendor/accesskit_windows/src/window_handle.rs` | rs | 753 |
| `app/vendor/gpui-pre-windows/Cargo.toml` | toml | 5490 |
| `app/vendor/gpui-pre-windows/build.rs` | rs | 9271 |
| `app/vendor/gpui-pre-windows/prebuilt/shaders_bytes.rs` | rs | 443445 |
| `app/vendor/gpui-pre-windows/src/clipboard.rs` | rs | 13208 |
| `app/vendor/gpui-pre-windows/src/destination_list.rs` | rs | 7044 |
| `app/vendor/gpui-pre-windows/src/dialog.rs` | rs | 11442 |
| `app/vendor/gpui-pre-windows/src/direct_manipulation.rs` | rs | 12185 |
| `app/vendor/gpui-pre-windows/src/direct_write.rs` | rs | 75912 |
| `app/vendor/gpui-pre-windows/src/directx_atlas.rs` | rs | 14420 |
| `app/vendor/gpui-pre-windows/src/directx_devices.rs` | rs | 6143 |
| `app/vendor/gpui-pre-windows/src/directx_renderer.rs` | rs | 72988 |
| `app/vendor/gpui-pre-windows/src/dispatcher.rs` | rs | 7052 |
| `app/vendor/gpui-pre-windows/src/display.rs` | rs | 7569 |
| `app/vendor/gpui-pre-windows/src/events.rs` | rs | 67367 |
| `app/vendor/gpui-pre-windows/src/gpui_windows.rs` | rs | 952 |
| `app/vendor/gpui-pre-windows/src/keyboard.rs` | rs | 11243 |
| `app/vendor/gpui-pre-windows/src/platform.rs` | rs | 72022 |
| `app/vendor/gpui-pre-windows/src/system_notifications.rs` | rs | 7614 |
| `app/vendor/gpui-pre-windows/src/system_settings.rs` | rs | 2551 |
| `app/vendor/gpui-pre-windows/src/util.rs` | rs | 5638 |
| `app/vendor/gpui-pre-windows/src/vsync.rs` | rs | 4038 |
| `app/vendor/gpui-pre-windows/src/window.rs` | rs | 62238 |
| `app/vendor/gpui-pre-windows/src/wrapper.rs` | rs | 940 |
| `app/vendor/gpui-pre/Cargo.toml` | toml | 13164 |
| `app/vendor/gpui-pre/benches/focus_cleanup.rs` | rs | 4486 |
| `app/vendor/gpui-pre/build.rs` | rs | 2057 |
| `app/vendor/gpui-pre/examples/a11y.rs` | rs | 10681 |
| `app/vendor/gpui-pre/examples/active_state_bug.rs` | rs | 1404 |
| `app/vendor/gpui-pre/examples/anchor.rs` | rs | 7854 |
| `app/vendor/gpui-pre/examples/animation.rs` | rs | 18713 |
| `app/vendor/gpui-pre/examples/data_table.rs` | rs | 17006 |
| `app/vendor/gpui-pre/examples/drag_drop.rs` | rs | 4604 |
| `app/vendor/gpui-pre/examples/example_support/fonts.rs` | rs | 1540 |
| `app/vendor/gpui-pre/examples/focus_visible.rs` | rs | 8808 |
| `app/vendor/gpui-pre/examples/gif_viewer.rs` | rs | 1458 |
| `app/vendor/gpui-pre/examples/gradient.rs` | rs | 10370 |
| `app/vendor/gpui-pre/examples/grid_layout.rs` | rs | 3234 |
| `app/vendor/gpui-pre/examples/hello_world.rs` | rs | 3906 |
| `app/vendor/gpui-pre/examples/image/image.rs` | rs | 7222 |
| `app/vendor/gpui-pre/examples/image_gallery.rs` | rs | 9973 |
| `app/vendor/gpui-pre/examples/image_loading.rs` | rs | 8522 |
| `app/vendor/gpui-pre/examples/input.rs` | rs | 29952 |
| `app/vendor/gpui-pre/examples/layer_shell.rs` | rs | 3319 |
| `app/vendor/gpui-pre/examples/list_example.rs` | rs | 5945 |
| `app/vendor/gpui-pre/examples/mouse_pressure.rs` | rs | 2290 |
| `app/vendor/gpui-pre/examples/move_entity_between_windows.rs` | rs | 5198 |
| `app/vendor/gpui-pre/examples/on_window_close_quit.rs` | rs | 2815 |
| `app/vendor/gpui-pre/examples/opacity.rs` | rs | 6617 |
| `app/vendor/gpui-pre/examples/ownership_post.rs` | rs | 1295 |
| `app/vendor/gpui-pre/examples/painting.rs` | rs | 18867 |
| `app/vendor/gpui-pre/examples/paths_bench.rs` | rs | 3453 |
| `app/vendor/gpui-pre/examples/pattern.rs` | rs | 4370 |
| `app/vendor/gpui-pre/examples/popover.rs` | rs | 7132 |
| `app/vendor/gpui-pre/examples/scrollable.rs` | rs | 2444 |
| `app/vendor/gpui-pre/examples/set_menus.rs` | rs | 3545 |
| `app/vendor/gpui-pre/examples/shadow.rs` | rs | 28153 |
| `app/vendor/gpui-pre/examples/svg/svg.rs` | rs | 2936 |
| `app/vendor/gpui-pre/examples/svg_animation.rs` | rs | 7699 |
| `app/vendor/gpui-pre/examples/system_notifications.rs` | rs | 5749 |
| `app/vendor/gpui-pre/examples/tab_stop.rs` | rs | 7349 |
| `app/vendor/gpui-pre/examples/testing.rs` | rs | 19719 |
| `app/vendor/gpui-pre/examples/text.rs` | rs | 13730 |
| `app/vendor/gpui-pre/examples/text_layout.rs` | rs | 3683 |
| `app/vendor/gpui-pre/examples/text_wrapper.rs` | rs | 4866 |
| `app/vendor/gpui-pre/examples/toggle_headless.rs` | rs | 10913 |
| `app/vendor/gpui-pre/examples/tree.rs` | rs | 1873 |
| `app/vendor/gpui-pre/examples/uniform_list.rs` | rs | 2029 |
| `app/vendor/gpui-pre/examples/view_example/example_editor.rs` | rs | 17521 |
| `app/vendor/gpui-pre/examples/view_example/example_input.rs` | rs | 3889 |
| `app/vendor/gpui-pre/examples/view_example/example_tests.rs` | rs | 4424 |
| `app/vendor/gpui-pre/examples/view_example/example_text_area.rs` | rs | 3758 |
| `app/vendor/gpui-pre/examples/view_example/view_example_main.rs` | rs | 5859 |
| `app/vendor/gpui-pre/examples/window.rs` | rs | 12003 |
| `app/vendor/gpui-pre/examples/window_movable.rs` | rs | 3679 |
| `app/vendor/gpui-pre/examples/window_positioning.rs` | rs | 7946 |
| `app/vendor/gpui-pre/examples/window_shadow.rs` | rs | 11336 |
| `app/vendor/gpui-pre/src/_accessibility.rs` | rs | 11011 |
| `app/vendor/gpui-pre/src/_ownership_and_data_flow.rs` | rs | 7413 |
| `app/vendor/gpui-pre/src/action.rs` | rs | 16133 |
| `app/vendor/gpui-pre/src/app.rs` | rs | 148217 |
| `app/vendor/gpui-pre/src/app/async_context.rs` | rs | 17718 |
| `app/vendor/gpui-pre/src/app/bench_context.rs` | rs | 61401 |
| `app/vendor/gpui-pre/src/app/context.rs` | rs | 32009 |
| `app/vendor/gpui-pre/src/app/entity_map.rs` | rs | 46261 |
| `app/vendor/gpui-pre/src/app/headless_app_context.rs` | rs | 9461 |
| `app/vendor/gpui-pre/src/app/test_app.rs` | rs | 20127 |
| `app/vendor/gpui-pre/src/app/test_context.rs` | rs | 52245 |
| `app/vendor/gpui-pre/src/app/visual_test_context.rs` | rs | 16108 |
| `app/vendor/gpui-pre/src/arena.rs` | rs | 11567 |
| `app/vendor/gpui-pre/src/asset_cache.rs` | rs | 11806 |
| `app/vendor/gpui-pre/src/assets.rs` | rs | 3813 |
| `app/vendor/gpui-pre/src/bench.rs` | rs | 2823 |
| `app/vendor/gpui-pre/src/bounds_tree.rs` | rs | 17681 |
| `app/vendor/gpui-pre/src/color.rs` | rs | 32216 |
| `app/vendor/gpui-pre/src/colors.rs` | rs | 3339 |
| `app/vendor/gpui-pre/src/debug_overlay.rs` | rs | 15300 |
| `app/vendor/gpui-pre/src/element.rs` | rs | 36582 |
| `app/vendor/gpui-pre/src/elements/anchored.rs` | rs | 21228 |
| `app/vendor/gpui-pre/src/elements/animation.rs` | rs | 35892 |
| `app/vendor/gpui-pre/src/elements/canvas.rs` | rs | 2601 |
| `app/vendor/gpui-pre/src/elements/container_query.rs` | rs | 3629 |
| `app/vendor/gpui-pre/src/elements/deferred.rs` | rs | 10782 |
| `app/vendor/gpui-pre/src/elements/div.rs` | rs | 235074 |
| `app/vendor/gpui-pre/src/elements/image_cache.rs` | rs | 10514 |
| `app/vendor/gpui-pre/src/elements/img.rs` | rs | 32345 |
| `app/vendor/gpui-pre/src/elements/list.rs` | rs | 146359 |
| `app/vendor/gpui-pre/src/elements/mod.rs` | rs | 434 |
| `app/vendor/gpui-pre/src/elements/surface.rs` | rs | 3709 |
| `app/vendor/gpui-pre/src/elements/svg.rs` | rs | 24938 |
| `app/vendor/gpui-pre/src/elements/text.rs` | rs | 46894 |
| `app/vendor/gpui-pre/src/elements/uniform_list.rs` | rs | 36372 |
| `app/vendor/gpui-pre/src/executor.rs` | rs | 22556 |
| `app/vendor/gpui-pre/src/geometry.rs` | rs | 124378 |
| `app/vendor/gpui-pre/src/gestures.rs` | rs | 95953 |
| `app/vendor/gpui-pre/src/global.rs` | rs | 2542 |
| `app/vendor/gpui-pre/src/gpui.rs` | rs | 10213 |
| `app/vendor/gpui-pre/src/hot_reload.rs` | rs | 8807 |
| `app/vendor/gpui-pre/src/input.rs` | rs | 20122 |
| `app/vendor/gpui-pre/src/inspector.rs` | rs | 9580 |
| `app/vendor/gpui-pre/src/interactive.rs` | rs | 32794 |
| `app/vendor/gpui-pre/src/key_dispatch.rs` | rs | 82227 |
| `app/vendor/gpui-pre/src/keymap.rs` | rs | 43532 |
| `app/vendor/gpui-pre/src/keymap/binding.rs` | rs | 5614 |
| `app/vendor/gpui-pre/src/keymap/context.rs` | rs | 32637 |
| `app/vendor/gpui-pre/src/path_builder.rs` | rs | 18672 |
| `app/vendor/gpui-pre/src/path_winding.rs` | rs | 30375 |
| `app/vendor/gpui-pre/src/platform.rs` | rs | 143994 |
| `app/vendor/gpui-pre/src/platform/app_menu.rs` | rs | 11423 |
| `app/vendor/gpui-pre/src/platform/keyboard.rs` | rs | 1225 |
| `app/vendor/gpui-pre/src/platform/keystroke.rs` | rs | 24712 |
| `app/vendor/gpui-pre/src/platform/layer_shell.rs` | rs | 2987 |
| `app/vendor/gpui-pre/src/platform/platform_info.rs` | rs | 1617 |
| `app/vendor/gpui-pre/src/platform/popup.rs` | rs | 5650 |
| `app/vendor/gpui-pre/src/platform/scap_screen_capture.rs` | rs | 11934 |
| `app/vendor/gpui-pre/src/platform/test.rs` | rs | 275 |
| `app/vendor/gpui-pre/src/platform/test/dispatcher.rs` | rs | 4204 |
| `app/vendor/gpui-pre/src/platform/test/display.rs` | rs | 1034 |
| `app/vendor/gpui-pre/src/platform/test/platform.rs` | rs | 28937 |
| `app/vendor/gpui-pre/src/platform/test/window.rs` | rs | 21158 |
| `app/vendor/gpui-pre/src/platform/threaded_dispatcher.rs` | rs | 26946 |
| `app/vendor/gpui-pre/src/platform/visual_test.rs` | rs | 8335 |
| `app/vendor/gpui-pre/src/platform_scheduler.rs` | rs | 16772 |
| `app/vendor/gpui-pre/src/prelude.rs` | rs | 489 |
| `app/vendor/gpui-pre/src/profiler.rs` | rs | 80263 |
| `app/vendor/gpui-pre/src/profiler/actions.rs` | rs | 6202 |
| `app/vendor/gpui-pre/src/profiler/hang.rs` | rs | 77937 |
| `app/vendor/gpui-pre/src/profiler/hang/monitor.rs` | rs | 4464 |
| `app/vendor/gpui-pre/src/profiler/journal.rs` | rs | 134837 |
| `app/vendor/gpui-pre/src/queue.rs` | rs | 16930 |
| `app/vendor/gpui-pre/src/randomized_element_tree.rs` | rs | 77501 |
| `app/vendor/gpui-pre/src/scene.rs` | rs | 42882 |
| `app/vendor/gpui-pre/src/seeds.rs` | rs | 2408 |
| `app/vendor/gpui-pre/src/shared_uri.rs` | rs | 627 |
| `app/vendor/gpui-pre/src/spring.rs` | rs | 27610 |
| `app/vendor/gpui-pre/src/style.rs` | rs | 54256 |
| `app/vendor/gpui-pre/src/styled.rs` | rs | 32990 |
| `app/vendor/gpui-pre/src/subscription.rs` | rs | 18083 |
| `app/vendor/gpui-pre/src/svg_renderer.rs` | rs | 30926 |
| `app/vendor/gpui-pre/src/tab_stop.rs` | rs | 16353 |
| `app/vendor/gpui-pre/src/taffy.rs` | rs | 28698 |
| `app/vendor/gpui-pre/src/test.rs` | rs | 6111 |
| `app/vendor/gpui-pre/src/text_system.rs` | rs | 48196 |
| `app/vendor/gpui-pre/src/text_system/complex_script_breaks.rs` | rs | 2564 |
| `app/vendor/gpui-pre/src/text_system/font_fallbacks.rs` | rs | 635 |
| `app/vendor/gpui-pre/src/text_system/font_features.rs` | rs | 5065 |
| `app/vendor/gpui-pre/src/text_system/line.rs` | rs | 70330 |
| `app/vendor/gpui-pre/src/text_system/line_layout.rs` | rs | 37387 |
| `app/vendor/gpui-pre/src/text_system/line_wrapper.rs` | rs | 73109 |
| `app/vendor/gpui-pre/src/util.rs` | rs | 8167 |
| `app/vendor/gpui-pre/src/view.rs` | rs | 23399 |
| `app/vendor/gpui-pre/src/window.rs` | rs | 429381 |
| `app/vendor/gpui-pre/src/window/a11y.rs` | rs | 35579 |
| `app/vendor/gpui-pre/src/window/a11y/debug.rs` | rs | 11527 |
| `app/vendor/gpui-pre/src/window/prompts.rs` | rs | 6719 |
| `app/vendor/gpui-pre/tests/action_macros.rs` | rs | 1285 |

## atlas — `tools/` y `services/` por subdirectorio

`tools/` — **33 ficheros**:

| subdirectorio | ficheros | tratamientos | bytes |
|---|---:|---|---:|
| `build/` | 5 | reference=5 | 77092 |
| `dev/` | 9 | reference=9 | 162141 |
| `lab/` | 1 | reference=1 | 33110 |
| `native/` | 1 | reference=1 | 6747 |
| `release/` | 5 | reference=5 | 19255 |
| `sxsc/` | 5 | reference=5 | 47977 |
| `timer/` | 7 | reference=7 | 15154 |

`services/` — **28 ficheros**:

| subdirectorio | ficheros | tratamientos | bytes |
|---|---:|---|---:|
| `reports-mcp/` | 9 | reference=9 | 115468 |
| `reports/` | 19 | reference=19 | 204176 |

## winutil — `tools/`, `scripts/`, `docs/`

`tools/` — **15 ficheros**:

| subdirectorio | ficheros | tratamientos | bytes |
|---|---:|---|---:|
| `(raíz)` | 4 | reference=4 | 56702 |
| `title-screen/` | 11 | reference=11 | 65598 |

`scripts/` — **2 ficheros**:

| subdirectorio | ficheros | tratamientos | bytes |
|---|---:|---|---:|
| `(raíz)` | 2 | extract=2 | 17847 |

`docs/` — **209 ficheros**:

| subdirectorio | ficheros | tratamientos | bytes |
|---|---:|---|---:|
| `(raíz)` | 9 | reference=9 | 266899 |
| `public/` | 3 | reference=3 | 74803 |
| `src/` | 197 | reference=197 | 2771634 |

## Corrección del paso 4b (T0f)

Tras el paso 3b el valor vigente era **201**. En el paso 4b se revisó cada
fichero que quedaba y se decidió **por escrito**, con `reason` explícito en
`inventory/partition/atlas.yml`:

| decisión | ficheros | tratamiento |
|---|---:|---|
| `package/atlas.json` es configuración del paquete | 1 | **extract** (regla `package/**/*.json`) |
| `app/build.rs`, `app/examples/`, `app/rustfmt.toml`, `app/licenses/`, `.vscode/`, `.zed/`, `lychee.toml` | 9 | reference, con `reason` marcado `[paso 4b]` |

Con eso, `partition_review.py` ya no marca esos 9: una regla con motivo
`[paso 4b]` cuenta como revisada (antes la heurística solo miraba prefijos de
ruta y podía marcar para siempre lo ya decidido).

**Conteos vigentes**: `extract=1082  reference=465  exclude=3`, 0 sin
clasificar, 0 reglas muertas, 0 excludes sobre comportamiento, `VEREDICTO: OK`.

**A REVISAR = 189**, todos `app/vendor/**` (código Rust de terceros
vendorizado, ya declarado como reference en el paso 2b). No queda ninguna
categoría "sueltos".

Nota: al añadir `package/**/*.json` la regla más específica
`package/Executables/**/*.json` quedó **muerta** y el checker lo detectó
(`reglas muertas: 1`, `VEREDICTO: FALLA`); se eliminó y volvió a `OK`.
