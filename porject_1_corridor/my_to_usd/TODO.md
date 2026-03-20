# Research TODO — MYR→IBKR 文章数据收集

> 更新时间: 2026-03-20  
> 目标: 将所有 `[ILLUSTRATIVE]` 数字替换为真实测量值，支撑文章每一条主张。

---

## M1 — Wise（主锚点）

- [ ] 核实并更新 `m1_wise/collect.py` 里的费用参数
  - 打开 https://wise.com/gb/pricing/send-money 查 MYR→USD 的实际费率
  - 更新 `WISE_FEE_FIXED_MYR` 和 `WISE_FEE_VARIABLE_PCT`
- [ ] 多时段采样（至少 3 次：亚洲盘 / 欧洲盘 / 美盘）
  ```bash
  python3 research_modules/m1_wise/collect.py --loop 3 --wait 3600
  ```
- [ ] 跑完整链路生成图表
  ```bash
  python3 research_modules/m1_wise/clean.py
  python3 research_modules/m1_wise/analyze.py
  python3 research_modules/m1_wise/chart.py
  ```
- [ ] 将 `data/m1_wise/summary.txt` 里的真实数字填入文章

---

## M2 — Instarem（竞品对比）

- [ ] 同一时段内查 Instarem 报价（与 M1 在 1 小时内完成）
  ```bash
  python3 research_modules/m2_instarem/collect.py --mode manual
  ```
- [ ] 跑 clean → analyze → chart
- [ ] 在文章中补充 Wise vs Instarem 的对比数字

---

## M3 — 银行 TT Baseline（Maybank / CIMB）

- [ ] 在银行官网查 MYR/USD TT Selling Rate（同一天记录）
  ```bash
  python3 research_modules/m3_bank_tt/collect.py --mode manual --bank maybank
  python3 research_modules/m3_bank_tt/collect.py --mode manual --bank cimb
  ```
- [ ] 确认 wire fee 数字（Maybank TT: RM 25？）
- [ ] 跑 clean → analyze → chart
- [ ] 确认文章中的 SHA 模式下中间行费用估算（$15–$35 range）

---

## M4 — SG Hop（CIMB / HSBC）

- [ ] 查阅 CIMB SG 的完整 Fee Schedule
  - 参考: https://www.cimb.com.sg/en/personal/banking/fees-and-charges.html
  - 确认 USD Wire 出境的 **OUR/SHA/BEN** 费控和具体金额
- [ ] 查阅 HSBC GlobalView 跨境费率
  - 参考: https://www.hsbc.com.sg/transfers/fees/
- [ ] 手动输入数据
  ```bash
  python3 research_modules/m4_sg_hop/collect.py --bank cimb
  python3 research_modules/m4_sg_hop/collect.py --bank hsbc
  ```
- [ ] 跑 clean → analyze → chart
- [ ] 确认"CIMB MY→CIMB SG MYR 跨境是否真的免费"（7 个 Reddit hit 已确认行为，但要找官方依据）

---

## M5 — BNM 外汇政策

- [ ] 下载最新 BNM Foreign Exchange Policy PDF
  ```bash
  python3 research_modules/m5_bnm_policy/collect.py
  ```
  （若自动下载失败，手动从 https://www.bnm.gov.my/foreign-exchange-policy 下载后用 `--local` 参数）
- [ ] 确认以下关键条文（有/无本地借贷）的居民汇出限额
- [ ] 跑 clean → analyze → chart（生成 Mermaid 决策图）
- [ ] 将决策图嵌入文章"合规"部分

---

## M6 — T+N 机会成本

- [ ] 在 M1–M4 数据收集完成后，重新跑 analyze + chart
  ```bash
  python3 research_modules/m6_tn_cost/collect.py
  python3 research_modules/m6_tn_cost/analyze.py
  python3 research_modules/m6_tn_cost/chart.py
  ```
- [ ] 将"Bank TT 4 天在途 ≈ RM X 隐性成本"这类数字写进文章

---

## M7 — Reddit 社区信号（已有基础）

- [ ] 如需补充最新帖子，重新抓取
  ```bash
  python3 research_modules/m7_reddit/collect.py
  ```
- [ ] 当前已有结论（可直接引用）:
  - Wise: 58 次提及（绝对领先）
  - PayPal: 6 次（需驳斥）
  - CIMB SG: 4 次（用户已验证行为）
  - Instarem: 0 次（内容 Gap = SEO 机会）

---

## 文章写作 TODO（数据收集完成后）

- [ ] 用真实数字替换所有 `[ILLUSTRATIVE]` 标注
- [ ] 补全 `Revolut` 小节（目前只有 meta 描述，不是正文）
- [ ] 统一全文写作姿态（正文 vs 备忘录混用问题）
- [ ] 确认 BNM FEK 限额数字，写入 TL;DR 或 Decision Guide
- [ ] 加入 IDEALPRO depth 说明（大额兑换滑点警告）
- [ ] 所有数字加上 timestamp（"截至 YYYY-MM-DD 测量"）

---

## 一键运行可自动化模块

```bash
cd /Users/wenyiyu/wenyi/writings/porject_1_corridor/my_to_usd
bash research_modules/run_all.sh m1 m6 m7
```
