#!/bin/bash
# 코드·기록 보안 점검: 비밀키(gitleaks, 전체 기록), 취약 패턴(semgrep), 의존성(npm audit) → 결과는 잠가서 저장
pip install -q cryptography semgrep >/dev/null 2>&1
W=/tmp/sec; mkdir -p $W/out
for r in woodenjoy-autopilot sisibibinote commonsense content-studio-template blog-template; do
  git clone -q "https://x-access-token:${GH_PAT}@github.com/kim-wasp/$r.git" $W/$r 2>/dev/null || echo "$r 복제 실패" >> $W/out/errors.txt
  [ -d $W/$r ] || continue
  docker run --rm -v $W/$r:/repo -v $W/out:/out zricethezav/gitleaks:latest git /repo --redact --no-banner -f json -r /out/gitleaks_$r.json >/dev/null 2>&1
  (cd $W/$r && semgrep scan --config p/secrets --config p/javascript --config p/python --config p/github-actions --json -q -o $W/out/semgrep_$r.json . >/dev/null 2>&1)
  for d in $(cd $W/$r && find . -name package.json -not -path "*/node_modules/*" -maxdepth 3); do
    dd=$(dirname $d); (cd $W/$r/$dd && npm install --package-lock-only --ignore-scripts --silent >/dev/null 2>&1; npm audit --json > $W/out/npmaudit_${r}_$(echo $dd | tr '/.' '__').json 2>/dev/null)
  done
done
(cd $W/out && tar czf /tmp/codeaudit.tgz .)
python3 tools/seal.py /tmp/codeaudit.tgz status/audit/code_audit.enc
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status/audit/code_audit.enc && git commit -qm "코드 보안 점검(잠금)" && git pull -q --rebase && git push -q
echo 끝
