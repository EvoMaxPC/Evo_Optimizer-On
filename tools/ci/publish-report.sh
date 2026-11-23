#!/usr/bin/env bash
# publish-report.sh — publica artefactos de CI en la rama huérfana `ci-report`.
#
# Uso: publish-report.sh <directorio> <etiqueta> <estado-del-job>
#   <directorio>        directorio con los ficheros a publicar (se copia entero)
#   <etiqueta>          nombre corto, p.ej. windows-latest / ubuntu-latest
#   <estado-del-job>    success | failure | cancelled | ... (texto libre saneado)
#
# Diseño (ver docs/AGENT_CONTRACT.md §4 y docs/reports/paso1.md):
#   * NUNCA force-push. Los commits se acumulan como ancestros.
#   * Copia a  runs/${GITHUB_RUN_ID}-<etiqueta>/  y  latest/<etiqueta>/
#   * Escribe meta.json con sha, run id, runner, imagen, fecha, estado.
#   * Reintento con `git pull --rebase` ante rechazo (hasta 5 intentos).
#   * Retención: conserva los 30 directorios runs/* más recientes.
#   * Trunca ficheros > 200 KB conservando cabeza y cola con marca visible.
#   * Redacta valores de variables cuyo nombre contenga TOKEN, SECRET o KEY.
#
# Variables de entorno (todas opcionales, con defaults para test local):
#   GITHUB_RUN_ID, GITHUB_SHA, GITHUB_RUN_ATTEMPT, RUNNER_NAME, RUNNER_OS,
#   RUNNER_IMAGE, GITHUB_REPOSITORY, CI_REPORT_REMOTE, CI_REPORT_BRANCH,
#   CI_REPORT_WORK, CI_REPORT_MAX_RUNS, CI_REPORT_MAX_BYTES, GIT_AUTHOR_*
set -uo pipefail

MAX_ATTEMPTS=5
MAX_BYTES_DEFAULT=${CI_REPORT_MAX_BYTES:-204800}          # 200 KB
MAX_RUNS_DEFAULT=${CI_REPORT_MAX_RUNS:-30}
HEAD_KEEP_DEFAULT=${CI_REPORT_HEAD_BYTES:-60000}
TAIL_KEEP_DEFAULT=${CI_REPORT_TAIL_BYTES:-60000}
BRANCH=${CI_REPORT_BRANCH:-ci-report}

log() { printf '[publish-report] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-2}"
}

# --- saneado de nombres ---------------------------------------------------
sanitize() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '-' | sed -e 's/-\{2,\}/-/g' -e 's/^-//' -e 's/-$//' | cut -c1-80
}

abs_path() { (cd "$1" 2>/dev/null && pwd -P); }

# --- redacción de secretos ----------------------------------------------
# Recorre el árbol de trabajo y sustituye, LITERALMENTE, los valores de las
# variables de entorno sensibles por ***REDACTED***.
redact_tree() {
  local root="$1" name value report
  report=$(mktemp)
  while IFS= read -r name; do
    case "$name" in
      GITHUB_TOKEN|GITHUB_*TOKEN*|*TOKEN*|*SECRET*|*KEY*|AWS_*|ACTIONS_*KEY*) ;;
    esac
    [ -n "$name" ] || continue
    value="${!name-}"
    # ignora vacíos y valores demasiado cortos/genéricos para no destrozar ficheros
    [ "${#value}" -ge 8 ] || continue
    grep -rlF -- "$value" "$root" 2>/dev/null | while IFS= read -r f; do
      printf '%s\n' "$f"
    done >>"$report"
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      VALUE="$value" perl -0pi -e 's/\Q$ENV{VALUE}\E/***REDACTED***/g' "$f" 2>/dev/null \
        || sed -i "s|$value|***REDACTED***|g" "$f" 2>/dev/null || true
      log "redactado $name en ${f#"$root"/}"
    done <"$report"
    : >"$report"
  done < <(compgen -e)
  rm -f "$report"
}

# --- truncado -------------------------------------------------------------
truncate_tree() {
  local root="$1" max="$2" head keep_tail f size h t tmp
  while IFS= read -r -d '' f; do
    size=$(wc -c <"$f" | tr -d ' ')
    [ "$size" -gt "$max" ] || continue
    head=${CI_REPORT_HEAD_BYTES:-$HEAD_KEEP_DEFAULT}
    keep_tail=${CI_REPORT_TAIL_BYTES:-$TAIL_KEEP_DEFAULT}
    tmp="$f.trunc.tmp"
    {
      head -c "$head" "$f"
      printf '\n\n... [TRUNCADO POR publish-report.sh: fichero de %s bytes, se conservan %s de cabeza y %s de cola; original no publicado] ...\n\n' "$size" "$head" "$keep_tail"
      tail -c "$keep_tail" "$f"
    } >"$tmp"
    mv "$tmp" "$f"
    log "truncado ${f#"$root"/} ($size -> $(wc -c <"$f" | tr -d ' ') bytes)"
  done < <(find "$root" -type f -print0)
}

# --- clonado / preparación de la rama huérfana ---------------------------
prepare_work_repo() {
  local remote="$1" work="$2"
  if [ -d "$work/.git" ]; then
    git -C "$work" remote set-url origin "$remote" 2>/dev/null || \
      git -C "$work" remote add origin "$remote"
  else
    rm -rf "$work"
    mkdir -p "$work"
    git -C "$work" init -q
    git -C "$work" remote add origin "$remote"
    git -C "$work" symbolic-ref HEAD "refs/heads/$BRANCH"
  fi
  git -C "$work" config user.name "${GIT_AUTHOR_NAME:-ci-report-bot}"
  git -C "$work" config user.email "${GIT_AUTHOR_EMAIL:-ci-report-bot@users.noreply.github.com}"
  git -C "$work" config advice.detachedHead false
  git -C "$work" config core.autocrlf false
}

# Trae la rama remota si existe. Devuelve 0 si existe, 1 si es la primera vez.
fetch_branch() {
  local work="$1"
  if git -C "$work" fetch --quiet --depth 1 origin "$BRANCH" 2>/dev/null; then
    git -C "$work" checkout -q -B "$BRANCH" FETCH_HEAD 2>/dev/null || {
      git -C "$work" reset -q --hard FETCH_HEAD; git -C "$work" symbolic-ref HEAD "refs/heads/$BRANCH"; }
    return 0
  fi
  return 1
}

# --- retención ------------------------------------------------------------
apply_retention() {
  local work="$1" keep="$2" list n
  [ -d "$work/runs" ] || return 0
  # más recientes primero: por nombre (GITHUB_RUN_ID monotónico) y luego mtime
  list=$(find "$work/runs" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null \
         | sort -r)
  n=$(printf '%s\n' "$list" | grep -c . || true)
  [ "${n:-0}" -gt "$keep" ] || return 0
  printf '%s\n' "$list" | tail -n +"$((keep + 1))" | while IFS= read -r d; do
    [ -n "$d" ] || continue
    rm -rf "$work/runs/$d"
    log "retención: eliminado runs/$d"
  done
}

# --- publicación ---------------------------------------------------------
main() {
  [ $# -eq 3 ] || usage 2
  local srcdir="$1" label="$2" status="$3"
  local src_abs
  src_abs=$(abs_path "$srcdir") || die "directorio origen no existe: $srcdir"
  [ -d "$src_abs" ] || die "no es un directorio: $srcdir"

  local run_id="${GITHUB_RUN_ID:-local-$(date -u +%Y%m%dT%H%M%SZ)}"
  local sha="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo unknown)}"
  local attempt="${GITHUB_RUN_ATTEMPT:-1}"
  local runner="${RUNNER_NAME:-$(hostname 2>/dev/null || echo unknown)}"
  local runner_os="${RUNNER_OS:-$(uname -s 2>/dev/null || echo unknown)}"
  local image="${RUNNER_IMAGE:-${ImageOS:-unknown}}"
  local repo_slug="${GITHUB_REPOSITORY:-EvoMaxPC/Evo_Optimizer-On}"
  local remote="${CI_REPORT_REMOTE:-}"
  local work="${CI_REPORT_WORK:-${TMPDIR:-/tmp}/ci-report-work}"
  local max_runs="${CI_REPORT_MAX_RUNS:-$MAX_RUNS_DEFAULT}"
  local max_bytes="${CI_REPORT_MAX_BYTES:-$MAX_BYTES_DEFAULT}"

  label=$(sanitize "$label"); [ -n "$label" ] || label=sin-etiqueta

  if [ -z "$remote" ]; then
    if [ -n "${GITHUB_TOKEN-}" ] && [ -n "${GITHUB_REPOSITORY-}" ]; then
      remote="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
    else
      remote=$(git config --get remote.origin.url 2>/dev/null) \
        || die "sin CI_REPORT_REMOTE y sin remote.origin; define CI_REPORT_REMOTE"
    fi
  fi

  # Enmascara credenciales en el log.
  log "remoto: $(printf '%s' "$remote" | sed -E 's#//[^@]*@#//***@#')"
  log "run_id=$run_id etiqueta=$label estado=$status intento=$attempt"
  log "work=$work rama=$BRANCH retención=$max_runs truncado>${max_bytes}B"

  local staging
  staging=$(mktemp -d)
  trap 'rm -rf "$staging"' EXIT

  # 1) copia a staging (no tocamos el origen original del usuario)
  local run_dir="runs/${run_id}-${label}"
  mkdir -p "$staging/$run_dir"
  cp -a "$src_abs/." "$staging/$run_dir/" || die "no se pudo copiar $src_abs"
  redact_tree "$staging"
  truncate_tree "$staging" "$max_bytes"

  # meta.json
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  cat >"$staging/$run_dir/meta.json" <<JSON
{
  "schema": 1,
  "label": "$label",
  "status": "$status",
  "run_id": "$run_id",
  "run_attempt": "$attempt",
  "sha": "$sha",
  "repository": "$repo_slug",
  "runner_name": "$runner",
  "runner_os": "$runner_os",
  "runner_image": "$image",
  "generated_utc": "$ts",
  "ref": "${GITHUB_REF:-}",
  "event": "${GITHUB_EVENT_NAME:-local}",
  "files": $(find "$staging/$run_dir" -type f | wc -l | tr -d ' ')
}
JSON

  # 2) prepara repo de trabajo
  prepare_work_repo "$remote" "$work"

  local attempt_n=1
  while :; do
    local first_time=0
    if ! fetch_branch "$work"; then
      first_time=1
      git -C "$work" symbolic-ref HEAD "refs/heads/$BRANCH"
      # limpia el índice por si quedó de una ejecución previa
      rm -rf "$work"/runs "$work"/latest
    fi

    # 3) aplica contenido al árbol de trabajo
    mkdir -p "$work/$run_dir"
    cp -a "$staging/$run_dir/." "$work/$run_dir/"
    mkdir -p "$work/latest/$label"
    rm -rf "$work/latest/$label"
    mkdir -p "$work/latest/$label"
    cp -a "$staging/$run_dir/." "$work/latest/$label/"
    apply_retention "$work" "$max_runs"

    git -C "$work" add -A
    if git -C "$work" diff --cached --quiet; then
      log "sin cambios respecto a la rama; nada que publicar"
      return 0
    fi
    git -C "$work" commit -q -m "ci-report: ${label} ${status} (run ${run_id}, attempt ${attempt_n})"

    if git -C "$work" push --quiet origin "HEAD:refs/heads/$BRANCH" 2>"$staging/push.err"; then
      log "publicado: $run_dir (primer envío=$first_time, intento=$attempt_n)"
      git -C "$work" log -1 --format='[publish-report] commit %h %s'
      return 0
    fi

    log "push rechazado (intento $attempt_n/$MAX_ATTEMPTS): $(tr -d '\n' <"$staging/push.err" | cut -c1-300)"
    if [ "$attempt_n" -ge "$MAX_ATTEMPTS" ]; then
      die "no se pudo publicar tras $MAX_ATTEMPTS intentos"
    fi
    attempt_n=$((attempt_n + 1))

    # 4) rebase sobre el remoto y reintento
    if fetch_branch "$work" >/dev/null 2>&1; then
      if ! git -C "$work" pull --rebase --quiet origin "$BRANCH" 2>"$staging/rebase.err"; then
        log "rebase con conflicto: $(tr -d '\n' <"$staging/rebase.err" | cut -c1-300)"
        git -C "$work" rebase --abort 2>/dev/null || true
        die "conflicto de rebase irrecuperable en runs/$run_dir"
      fi
    else
      log "la rama remota desapareció; reintentando como primera publicación"
      git -C "$work" reset -q --soft HEAD~1 2>/dev/null || true
    fi
    sleep $((attempt_n * 2))
  done
}

main "$@"
