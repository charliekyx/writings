#!/usr/bin/env bash
# 从 my_to_usd 根目录编排采集流水线（Docker / GCE cron 入口）。
# 用法: 在 my_to_usd 下: bash research_modules/docker_entry.sh
# 线上定时：见 research_modules/crontab.example（建议每日 2 次 UTC 1,9）。
# 本地说明：见 research_modules/LOCAL_RUN.txt
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# docker run -e / --env-file 在进脚本前已注入变量；若再 source 镜像内的 .env，会覆盖注入值。
# 先记下启动前已设置的 STRICT_AUTO（例如宿主 STRICT_AUTO=0），source 后再恢复。
if [[ -v STRICT_AUTO ]]; then
  _STRICT_AUTO_FROM_RUNTIME="${STRICT_AUTO}"
fi
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT}/.env"
  set +a
fi
if [[ -v _STRICT_AUTO_FROM_RUNTIME ]]; then
  export STRICT_AUTO="${_STRICT_AUTO_FROM_RUNTIME}"
  unset _STRICT_AUTO_FROM_RUNTIME
fi

export STRICT_AUTO="${STRICT_AUTO:-1}"
PY=python3

run() {
  echo "=== $* ==="
  "$PY" "$@" || return $?
}

# M1: 有 token 用 API，否则 scrape（STRICT 下 scrape 失败不会回落 manual）
if [[ -n "${WISE_API_TOKEN:-}" ]]; then
  run research_modules/m1_wise/collect.py --mode api
else
  echo "[WARN] WISE_API_TOKEN unset; using scrape mode"
  run research_modules/m1_wise/collect.py --mode scrape
fi

# M2 与 M1 同批对比
run research_modules/m2_instarem/collect.py --mode auto

# M3：TT 牌价 + 手续费均从官网解析（见 m3_bank_tt/fee_scrape.py）
# 本地/不可达 Maybank 时可 SKIP_M3_MAYBANK=1，避免长时间 Playwright 超时
if [[ "${SKIP_M3_MAYBANK:-}" == "1" ]]; then
  echo "[SKIP] m3_bank_tt maybank (SKIP_M3_MAYBANK=1)"
else
  run research_modules/m3_bank_tt/collect.py --mode scrape --bank maybank
fi
run research_modules/m3_bank_tt/collect.py --mode scrape --bank cimb

# M4：SG Hop 从 CIMB / HSBC 官网费用页动态抓取
run research_modules/m4_sg_hop/collect.py --mode scrape --bank cimb
run research_modules/m4_sg_hop/collect.py --mode scrape --bank hsbc

run research_modules/m5_bnm_policy/collect.py

# Reddit 舆情/关键词：不需要与汇率同频时可 SKIP_M7=1
if [[ "${SKIP_M7:-}" == "1" ]]; then
  echo "[SKIP] m7_reddit (SKIP_M7=1)"
else
  run research_modules/m7_reddit/collect.py
fi

# Revolut 对部分机房 IP 返回 403；GCP 上可设 SKIP_M8=1 跳过，或配代理 / 后续 Playwright
if [[ "${SKIP_M8:-}" == "1" ]]; then
  echo "[SKIP] m8_revolut (SKIP_M8=1)"
else
  run research_modules/m8_revolut/collect.py
fi
run research_modules/m9_ibkr_funding/collect.py
run research_modules/m10_public_rates/collect.py

# 下游分析图表（各模块内已引用 data/）
for mod in m1_wise m2_instarem m3_bank_tt m4_sg_hop m5_bnm_policy; do
  run research_modules/${mod}/clean.py 2>/dev/null || true
done
if [[ "${SKIP_M7:-}" != "1" ]]; then
  run research_modules/m7_reddit/clean.py 2>/dev/null || true
fi
run research_modules/m1_wise/analyze.py
run research_modules/m1_wise/chart.py
run research_modules/m2_instarem/analyze.py
run research_modules/m2_instarem/chart.py
run research_modules/m3_bank_tt/analyze.py
run research_modules/m3_bank_tt/chart.py
run research_modules/m5_bnm_policy/analyze.py
run research_modules/m5_bnm_policy/chart.py
if [[ "${SKIP_M7:-}" != "1" ]]; then
  run research_modules/m7_reddit/analyze.py
  run research_modules/m7_reddit/chart.py
fi

run research_modules/m6_tn_cost/collect.py
run research_modules/m6_tn_cost/analyze.py
run research_modules/m6_tn_cost/chart.py

run research_modules/m4_sg_hop/analyze.py
run research_modules/m4_sg_hop/chart.py

run research_modules/write_manifest.py

echo "Done. data/ and charts/ under ${ROOT}"
