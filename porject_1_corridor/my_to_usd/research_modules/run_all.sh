#!/usr/bin/env bash
# run_all.sh
# ──────────
# 按正确顺序运行所有 research 模块。
# M1：有 WISE_API_TOKEN 时建议 export 后用 api 模式（见 docker_entry.sh）。
# M2 auto + STRICT_AUTO=1 时失败即退出；M3 scrape 需 MAYBANK_WIRE_FEE_MYR 等环境变量。
# M4：--mode json + M4_CONFIG_JSON；M5–M7、m8–m10 见各 collect.py。
#
# 用法:
#   cd research_modules/
#   bash run_all.sh            # 运行所有可自动化的模块
#   bash run_all.sh m1         # 只运行 M1
#   bash run_all.sh m6 m7      # 只运行 M6 和 M7

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'  # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

run_module() {
    local module=$1
    local step=$2
    shift 2
    info "Running $module/$step.py $* ..."
    python "$module/$step.py" "$@" && info "  ✓ Done" || warn "  ! $module/$step.py returned error"
}

# ── 判断要运行的模块 ────────────────────────────────────────────
TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS=("m1" "m6" "m7")   # 默认只运行不需要手动输入的模块
fi

for target in "${TARGETS[@]}"; do
    case "$target" in
        m1)
            info "=== M1: Wise (api if WISE_API_TOKEN else scrape) ==="
            if [[ -n "${WISE_API_TOKEN:-}" ]]; then
              run_module m1_wise collect --mode api
            else
              run_module m1_wise collect
            fi
            run_module m1_wise clean
            run_module m1_wise analyze
            run_module m1_wise chart
            ;;
        m2)
            warn "=== M2: Instarem (requires manual input) ==="
            warn "  Run manually: python m2_instarem/collect.py --mode manual"
            warn "  Then: python m2_instarem/clean.py && python m2_instarem/analyze.py && python m2_instarem/chart.py"
            ;;
        m3)
            warn "=== M3: Bank TT (requires manual input) ==="
            warn "  Run manually: python m3_bank_tt/collect.py --mode manual --bank maybank"
            ;;
        m4)
            info "=== M4: SG Hop (scrape official pages) ==="
            run_module m4_sg_hop collect --mode scrape --bank cimb
            run_module m4_sg_hop collect --mode scrape --bank hsbc
            run_module m4_sg_hop clean
            run_module m4_sg_hop analyze
            run_module m4_sg_hop chart
            ;;
        m5)
            info "=== M5: BNM Policy ==="
            run_module m5_bnm_policy collect
            run_module m5_bnm_policy clean
            run_module m5_bnm_policy analyze
            run_module m5_bnm_policy chart
            ;;
        m6)
            info "=== M6: T+N Opportunity Cost (no external data) ==="
            run_module m6_tn_cost collect
            run_module m6_tn_cost analyze
            run_module m6_tn_cost chart
            ;;
        m7)
            info "=== M7: Reddit Trend ==="
            if [[ "${SKIP_M7_COLLECT:-}" == "1" ]]; then
              warn "  SKIP_M7_COLLECT=1 — only clean/analyze/chart"
              run_module m7_reddit clean
            else
              run_module m7_reddit collect
              run_module m7_reddit clean
            fi
            run_module m7_reddit analyze
            run_module m7_reddit chart
            ;;
        m8)
            info "=== M8: Revolut help pages ==="
            run_module m8_revolut collect
            ;;
        m9)
            info "=== M9: IBKR funding reference ==="
            run_module m9_ibkr_funding collect
            ;;
        m10)
            info "=== M10: Merchantrade / BigPay pages ==="
            run_module m10_public_rates collect
            ;;
        *)
            error "Unknown module: $target. Use m1..m10"
            ;;
    esac
done

info ""
info "Done. Charts saved in: ../charts/"
info "Data saved in: ../data/"
