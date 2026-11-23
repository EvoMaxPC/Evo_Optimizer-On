#!/usr/bin/env bash
# tests/ci/test_publish_report.sh — pruebas del canal ci-report con remotO bare local.
# (a) primera publicación crea la rama
# (b) segunda publicación conserva el primer commit como ancestro (no force-push)
# (c) dos publicaciones concurrentes terminan ambas con éxito
# (d) con 35 runs quedan 30 (retención)
# (e) truncado de ficheros > 200 KB con marca visible
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO_ROOT=$(cd "$HERE/../.." && pwd -P)
PUB="$REPO_ROOT/tools/ci/publish-report.sh"
SANDBOX=$(mktemp -d /tmp/ci-report-test.XXXXXX)
REMOTE="$SANDBOX/origin.git"
BRANCH=ci-report
PASS=0; FAIL=0

cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$*"; }
hdr()  { printf '\n=== %s ===\n' "$*"; }

# ejecuta publish-report con entorno aislado
pub() { # pub <srcdir> <label> <status> <run_id> [work]
  local src="$1" label="$2" status="$3" run="$4" work="${5:-$SANDBOX/work}"
  GITHUB_RUN_ID="$run" GITHUB_SHA="deadbeefcafe" GITHUB_RUN_ATTEMPT=1 \
  RUNNER_NAME=test-runner RUNNER_OS=Linux RUNNER_IMAGE=local \
  GITHUB_REPOSITORY=test/repo GITHUB_REF=refs/heads/main GITHUB_EVENT_NAME=push \
  CI_REPORT_REMOTE="$REMOTE" CI_REPORT_WORK="$work" \
  GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid \
  bash "$PUB" "$src" "$label" "$status"
}

git init -q --bare --initial-branch=main "$REMOTE"
mkdir -p "$SANDBOX/src1" "$SANDBOX/src2"
echo "hola mundo" >"$SANDBOX/src1/a.txt"
echo "segunda ronda" >"$SANDBOX/src2/b.txt"

hdr "(a) primera publicación crea la rama"
pub "$SANDBOX/src1" windows-latest success 1001 >"$SANDBOX/a.log" 2>&1
rc=$?
if [ $rc -eq 0 ] && git --git-dir="$REMOTE" rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  ok "exit=0 y rama $BRANCH existe"
else
  bad "exit=$rc o rama ausente"; sed 's/^/    | /' "$SANDBOX/a.log"
fi
first_commit=$(git --git-dir="$REMOTE" rev-parse "$BRANCH" 2>/dev/null)
files=$(git --git-dir="$REMOTE" ls-tree -r --name-only "$BRANCH" 2>/dev/null)
printf '   commits: %s\n' "$(git --git-dir="$REMOTE" rev-list --count "$BRANCH" 2>/dev/null)"
printf '   rutas:\n'; printf '%s\n' "$files" | sed 's/^/     - /'
for want in "runs/1001-windows-latest/a.txt" "runs/1001-windows-latest/meta.json" \
            "latest/windows-latest/a.txt" "latest/windows-latest/meta.json"; do
  printf '%s\n' "$files" | grep -qx "$want" && ok "existe $want" || bad "falta $want"
done

hdr "(b) segunda publicación NO hace force-push (primer commit es ancestro)"
pub "$SANDBOX/src2" ubuntu-latest success 1002 >"$SANDBOX/b.log" 2>&1
rc=$?
second_commit=$(git --git-dir="$REMOTE" rev-parse "$BRANCH" 2>/dev/null)
if [ $rc -eq 0 ] && [ "$first_commit" != "$second_commit" ] &&
   git --git-dir="$REMOTE" merge-base --is-ancestor "$first_commit" "$second_commit" 2>/dev/null; then
  ok "ancestro confirmado: ${first_commit:0:8} -> ${second_commit:0:8}"
else
  bad "no es ancestro o falló el push (exit=$rc)"; sed 's/^/    | /' "$SANDBOX/b.log"
fi
printf '   commits totales: %s\n' "$(git --git-dir="$REMOTE" rev-list --count "$BRANCH" 2>/dev/null)"

hdr "(c) dos publicaciones concurrentes terminan con éxito"
mkdir -p "$SANDBOX/conc1" "$SANDBOX/conc2"
echo uno >"$SANDBOX/conc1/x.txt"; echo dos >"$SANDBOX/conc2/y.txt"
pub "$SANDBOX/conc1" windows-2022 success 2001 "$SANDBOX/w1" >"$SANDBOX/c1.log" 2>&1 &
p1=$!
pub "$SANDBOX/conc2" windows-2025 success 2002 "$SANDBOX/w2" >"$SANDBOX/c2.log" 2>&1 &
p2=$!
wait $p1; r1=$?
wait $p2; r2=$?
if [ $r1 -eq 0 ] && [ $r2 -eq 0 ]; then
  ok "ambas concurrentes exit=0"
else
  bad "concurrentes fallaron: r1=$r1 r2=$r2"
  sed 's/^/    | /' "$SANDBOX/c1.log"; sed 's/^/    | /' "$SANDBOX/c2.log"
fi
fb=$(git --git-dir="$REMOTE" ls-tree -r --name-only "$BRANCH")
for want in runs/2001-windows-2022/x.txt runs/2002-windows-2025/y.txt latest/windows-2022/x.txt latest/windows-2025/y.txt; do
  printf '%s\n' "$fb" | grep -qx "$want" && ok "presente $want" || bad "ausente $want"
done
r1c=$(git --git-dir="$REMOTE" rev-parse "$BRANCH")
git --git-dir="$REMOTE" merge-base --is-ancestor "$second_commit" "$r1c" 2>/dev/null \
  && ok "linealidad preservada tras concurrencia" || bad "la historia se rompió"

hdr "(d) retención: 35 runs -> 30"
for i in $(seq 3001 3031); do
  mkdir -p "$SANDBOX/ret$i"; echo "run $i" >"$SANDBOX/ret$i/r.txt"
  pub "$SANDBOX/ret$i" ubuntu-latest success "$i" >/dev/null 2>&1 || bad "falló run $i"
done
dirs=$(git --git-dir="$REMOTE" ls-tree --name-only "$BRANCH" runs/ 2>/dev/null | sed 's#runs/##')
n=$(printf '%s\n' "$dirs" | grep -c . || true)
if [ "$n" -eq 30 ]; then ok "quedan exactamente 30 runs (esperado 30)"; else bad "quedan $n runs"; fi
printf '   rangos: %s\n' "$(printf '%s\n' "$dirs" | sort | sed -n '1p;$p' | tr '\n' ' ')"
printf '%s\n' "$dirs" | grep -q '^3001-' && bad "el más antiguo (3001) debería haberse purgado" \
  || ok "el más antiguo fue purgado"
printf '%s\n' "$dirs" | grep -q '^3031-' && ok "el más reciente (3031) conservado" \
  || bad "falta el más reciente"

hdr "(e) truncado de ficheros > 200 KB"
mkdir -p "$SANDBOX/big"
python3 - "$SANDBOX/big/huge.log" <<'PY'
import sys
p = sys.argv[1]
with open(p, "w") as f:
    f.write("CABECERA-VISIBLE-12345\n")
    f.write("relleno\n" * 60000)          # ~480 KB
    f.write("COLA-VISIBLE-67890\n")
PY
orig_size=$(wc -c <"$SANDBOX/big/huge.log")
pub "$SANDBOX/big" windows-latest success 4001 "$SANDBOX/wbig" >"$SANDBOX/e.log" 2>&1
rc=$?
git --git-dir="$REMOTE" cat-file -p "$BRANCH:latest/windows-latest/huge.log" >"$SANDBOX/huge.out" 2>/dev/null
new_size=$(wc -c <"$SANDBOX/huge.out" 2>/dev/null || echo 0)
if [ $rc -eq 0 ] && [ "$new_size" -lt "$orig_size" ] && grep -q 'TRUNCADO POR publish-report.sh' "$SANDBOX/huge.out"; then
  ok "truncado: $orig_size -> $new_size bytes con marca"
else
  bad "truncado no aplicado (orig=$orig_size nuevo=$new_size)"; sed 's/^/    | /' "$SANDBOX/e.log"
fi
grep -q 'CABECERA-VISIBLE-12345' "$SANDBOX/huge.out" && ok "cabeza conservada" || bad "cabeza perdida"
grep -q 'COLA-VISIBLE-67890' "$SANDBOX/huge.out" && ok "cola conservada" || bad "cola perdida"

hdr "(f) redacción de secretos (extra)"
mkdir -p "$SANDBOX/sec"
export MY_FAKE_TOKEN="supersecretovalor123"; printf 'token=%s\n' "supersecretovalor123" >"$SANDBOX/sec/s.txt"
MY_FAKE_TOKEN="supersecretovalor123" pub "$SANDBOX/sec" ubuntu-latest success 5001 "$SANDBOX/wsec" >/dev/null 2>&1
git --git-dir="$REMOTE" cat-file -p "$BRANCH:latest/ubuntu-latest/s.txt" >"$SANDBOX/sec.out" 2>/dev/null
if grep -q 'supersecretovalor123' "$SANDBOX/sec.out"; then
  bad "secreto NO redactado: $(cat "$SANDBOX/sec.out")"
else
  ok "secreto redactado: $(cat "$SANDBOX/sec.out")"
fi

hdr "RESUMEN"
printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
printf 'commits en la rama: %s\n' "$(git --git-dir="$REMOTE" rev-list --count "$BRANCH")"
[ "$FAIL" -eq 0 ] || exit 1
