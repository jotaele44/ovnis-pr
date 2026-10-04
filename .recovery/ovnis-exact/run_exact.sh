#!/usr/bin/env bash
set -euo pipefail
ROOT="$RUNNER_TEMP/recovered"
ARCHIVE="$RUNNER_TEMP/ovnis_exact.tar.gz"
PAYLOAD=".recovery/ovnis-exact/payload"
EXPECTED_ARCHIVE_SHA="a4dfd632d94d0c9d22bfdc26b389ce4e7c0d76882117e8155dd7bd6fb3cacc18"
rm -rf "$ROOT"; mkdir -p "$ROOT"
cat "$PAYLOAD/chunk-000.b64" "$PAYLOAD/chunk-001.b64" "$PAYLOAD/chunk-002.b64" "$PAYLOAD/chunk-003.b64" "$PAYLOAD/chunk-004.b64" > "$RUNNER_TEMP/ovnis_exact.b64"
base64 -d "$RUNNER_TEMP/ovnis_exact.b64" > "$ARCHIVE"
echo "$EXPECTED_ARCHIVE_SHA  $ARCHIVE" | sha256sum -c -
tar -xzf "$ARCHIVE" -C "$ROOT"
python - <<'PY'
from pathlib import Path
import hashlib, os
root=Path(os.environ["RUNNER_TEMP"])/"recovered"
rows=[]
for p in sorted(root.rglob("*")):
    if p.is_file():
        d=p.read_bytes()
        rows.append(f"{hashlib.sha256(d).hexdigest()}  {len(d)}  {p.relative_to(root).as_posix()}")
if len(rows)!=407: raise SystemExit(f"expected 407 files, got {len(rows)}")
manifest=bytes([10]).join(row.encode() for row in rows)+bytes([10])
got=hashlib.sha256(manifest).hexdigest()
expected="faff332cca25a670534497f4d0f90da4dc4564ee82f23530a98d7da829b87ca0"
if got!=expected: raise SystemExit(f"member manifest hash mismatch: {got}")
(root/"recovery-member-manifest.txt").write_bytes(manifest)
print("EXACT_MEMBER_VERIFICATION=PASS")
print("RECOVERED_FILE_COUNT=407")
print(f"MEMBER_MANIFEST_SHA256={got}")
PY
cd "$ROOT"
cp package.json package.original.json
node - <<'NODE'
const fs=require("fs");
const p=JSON.parse(fs.readFileSync("package.json","utf8"));
const snap=JSON.parse(fs.readFileSync("static/__dev/dependencies.json","utf8"));
p.devDependencies=p.devDependencies||{};
for(const [k,v] of Object.entries(snap)){if(!(k in (p.dependencies||{}))&&!(k in p.devDependencies))p.devDependencies[k]=v;}
fs.writeFileSync("package.json",JSON.stringify(p,null,2)+"\n");
NODE
export NPM_CONFIG_LEGACY_PEER_DEPS=true
npm install --no-audit --no-fund --ignore-scripts
npm install --save-dev --no-audit --no-fund --ignore-scripts vitest@3.2.4 jsdom@26.1.0 @testing-library/dom@10.4.1
cp "$GITHUB_WORKSPACE/.recovery/ovnis-exact/recovery.vitest.config.mts" recovery.vitest.config.mts
cp "$GITHUB_WORKSPACE/.recovery/ovnis-exact/recovery.vitest.setup.mjs" recovery.vitest.setup.mjs
sha256sum package.original.json package.json package-lock.json recovery.vitest.config.mts recovery.vitest.setup.mjs recovery-member-manifest.txt > recovery-hashes.txt
node -v > recovery-environment.txt; npm -v >> recovery-environment.txt
find . -type f \( -name '*.spec.ts' -o -name '*.spec.tsx' \) -not -path './node_modules/*' -print | sed 's#^./##' | sort > recovery-spec-files.txt
count=$(wc -l < recovery-spec-files.txt | tr -d ' '); echo "RECOVERED_SPEC_FILE_COUNT=$count"; test "$count" = "67"
: > recovery-spec-classification.tsv
mapfile -t exec_specs < <(while read -r f; do
  if grep -Eq '(^|[^A-Za-z])(it|test)[[:space:]]*\(' "$f"; then printf '%s\tEXECUTABLE\n' "$f" >> recovery-spec-classification.tsv; printf '%s\n' "$f";
  else printf '%s\tEMPTY_SPEC_NONEXECUTABLE\n' "$f" >> recovery-spec-classification.tsv; fi
done < recovery-spec-files.txt)
set +e
npx vitest run --config recovery.vitest.config.mts --reporter=verbose "${exec_specs[@]}" 2>&1 | tee recovery-vitest.log
status=${PIPESTATUS[0]}
set -e
echo "$status" > recovery-test-exit.txt
exit 0
