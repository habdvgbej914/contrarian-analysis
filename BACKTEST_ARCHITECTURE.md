# FCAS 115周回测架构设计

## 一、核心原则

**零后见之明**：第N周判断时，只能使用第N周开始日期之前已公开的数据。

---

## 二、两层架构

### 天时层（奇门引擎）
- 输入：第N周的起始日期 + 时辰（默认取该周一的辰时，即上午7-9点开盘时段）
- 处理：`fcas_mcp.py` 排盘 → 格局判断 → 旺衰 → 三层合成
- 输出：structural_diagnosis（FAVORABLE / ADVERSE / MIXED / NEUTRAL）+ 格局吉凶 + 应期窗口
- 特点：纯时间驱动，不看任何市场数据，4个标的在同一时间得到相同的天时判断

### 人事层（Claude API + 证据包）
- 输入：截止到第N周之前的所有可用数据（见下方数据可用性规则）
- 处理：Claude Opus 4.6 读取证据包 → 对每个标的独立做C1-C6二元判断 → 框架计算intent
- 输出：每个标的的C1-C6值 + 64卦配置 + intent assessment + 判断理由
- 特点：数据驱动，4个标的各自独立判断

### 两层合成
- 天时FAVORABLE + 人事FAVORABLE → **STRONG FAVORABLE**
- 天时FAVORABLE + 人事ADVERSE → **MIXED (天时顺/人事逆)**
- 天时ADVERSE + 人事FAVORABLE → **MIXED (天时逆/人事顺)**
- 天时ADVERSE + 人事ADVERSE → **STRONG ADVERSE**
- 天时NEUTRAL/MIXED → 以人事层判断为主

---

## 三、数据可用性规则（防后见之明）

### 3.1 周度数据（T-0可用）
个股周度数据的每条记录代表该周**收盘**时的数据。

**规则**：第N周判断时，可用的最新周度数据是第N-1周（上一周收盘数据）。
第N周自身的数据在判断时尚未产生。

适用数据集：
- 个股周度：收盘价、涨跌幅、成交量、成交额、换手率、融资余额、北向持股
- 上海金周度价格
- 美元兑人民币中间价
- 北向资金周度
- 两市融资余额周度
- 主要指数周收盘价
- COMEX金期货

### 3.2 月度宏观数据（有发布滞后）
月度宏观数据不是月末当天就能看到的，有发布滞后。

**规则**：月度数据在下一个月的特定日期才公布。
判断日期 < 发布日期 → 该月数据不可用，退到上一个月。

| 数据 | 典型发布时间 | 规则 |
|------|-------------|------|
| 制造业PMI | 当月最后一天或次月1日 | M月PMI在M月31日/次月1日可用 |
| 非制造业PMI | 同上 | 同上 |
| CPI/PPI | 次月9-12日 | M月CPI在M+1月10日后可用 |
| 社融/M2 | 次月10-15日 | M月数据在M+1月12日后可用 |
| 半导体销售 | 滞后2个月 | M月数据在M+2月可用 |
| 集成电路产量 | 次月中旬 | M月数据在M+1月15日后可用 |
| 央行黄金储备 | 次月7日左右 | M月数据在M+1月7日后可用 |

**简化规则（保守）**：月度数据统一取滞后1个完整月。
即第N周如果在M月，可用的月度数据最新到M-1月。
例：2024年3月第2周 → 最新可用月度数据 = 2024年2月的PMI/CPI/PPI/社融/M2

### 3.3 季度财务数据（有披露滞后）
上市公司财报披露有法定时限：

| 报告期 | 法定披露截止 | 保守可用时间 |
|--------|-------------|-------------|
| Q1 一季报 | 4月30日 | 5月第1周起可用 |
| Q2 半年报 | 8月31日 | 9月第1周起可用 |
| Q3 三季报 | 10月31日 | 11月第1周起可用 |
| Q4 年报 | 次年4月30日 | 次年5月第1周起可用 |

**规则**：在可用时间之前，退到上一个已披露的报告期。
例：2024年7月某周 → 最新可用财报 = Q1 FY2024（4月底已披露）
例：2024年3月某周 → 最新可用财报 = Q3 FY2023（如果有的话，否则Q4 FY2023的年报要到2024年4月底才出）

**注意**：我们的季度数据从Q1 FY2024开始。这意味着2024年1-4月期间，没有可用的季度财务数据（Q1 FY2024还没披露）。这些周的证据包里不包含财务数据，这是正确的——模拟真实情况。

---

## 四、证据包模板

每次Claude API调用时，收到的证据包格式如下：

```
你是一个结构分析框架的判断引擎。
当前日期：{judgment_date}
分析标的：{stock_name}（{stock_code}）

请基于以下数据，对6条标准做二元判断（1=正面，0=负面）。

== 个股近期表现（周度数据，截至{latest_weekly_date}）==
最近4周收盘价：{prices}
最近4周涨跌幅：{returns}
最近4周成交量：{volumes}
最近4周换手率：{turnover}
最近4周融资余额：{margin}
最近4周北向持股：{northbound}
过去12周价格趋势：{trend_12w}
过去12周累计涨跌幅：{return_12w}

== 宏观环境（截至{latest_macro_date}可用数据）==
制造业PMI：{pmi_latest} （前值{pmi_prev}）
CPI同比：{cpi_latest}%  PPI同比：{ppi_latest}%
M2同比：{m2_latest}%
社融当月：{tsf_latest}亿
半导体销售同比：{semi_latest}%
集成电路产量同比：{ic_latest}%
央行黄金储备变动：{gold_reserve_change}

== 市场环境 ==
上海金价格：{shanghai_gold}
美元兑人民币：{usd_cny}
北向资金周度净流入：{northbound_flow}亿
两市融资余额：{margin_total}亿

== 公司财务（最新已披露报告：{latest_report_period}）==
营收：{revenue}亿  同比：{revenue_yoy}%
净利润：{net_profit}亿  同比：{profit_yoy}%
毛利率：{gross_margin}%
经营现金流：{cashflow}亿
研发费用：{rd}亿（占营收{rd_ratio}%）
资产负债率：{debt_ratio}%
PE_TTM：{pe}倍  PB：{pb}倍
机构持股：{institutional}%

== 6条判断标准 ==
C1 趋势方向：该标的是否与当前宏观趋势一致？
C2 能量状态：当下能量是在积蓄还是消散？（看资金流向、成交量变化、市场关注度）
C3 内部协调：公司/行业内部是否协调运行？（看财务健康、管理层执行力、产业链关系）
C4 个人持续力：普通投资者能否撑过波动期？（看波动率、流动性、持仓成本）
C5 生态支撑：周围生态系统是支撑还是排斥？（看产业政策、上下游关系、行业景气度）
C6 根基深浅：结构承载力、时间积累、根系深度？（看基本面质量、护城河、历史沉淀）

请严格基于上述数据判断，不要使用你自己的知识或对未来的预期。
你只能看到上述数据中显示的信息，不知道之后发生了什么。

输出JSON格式：
{
  "c1": 0或1, "c1_reason": "一句话理由",
  "c2": 0或1, "c2_reason": "一句话理由",
  "c3": 0或1, "c3_reason": "一句话理由",
  "c4": 0或1, "c4_reason": "一句话理由",
  "c5": 0或1, "c5_reason": "一句话理由",
  "c6": 0或1, "c6_reason": "一句话理由"
}
只输出JSON，不要其他内容。
```

---

## 五、回测流程

### 5.1 周度时间轴

数据范围：2024-01-12 至 2026-03-27（约115周）
但前N周可能缺少财务数据（Q1 FY2024要到2024年5月才可用）。
这些周仍然可以跑——证据包里只是没有财务部分，这是真实情况的模拟。

### 5.2 每周执行步骤

```
for week_idx, week_start_date in enumerate(all_weeks):
    
    # === 天时层 ===
    qimen_result = fcas_paipan(week_start_date, hour="辰")  # 周一辰时
    geju_result = fcas_geju(qimen_result)
    tianshi_diagnosis = synthesize_tianshi(geju_result)
    
    # === 人事层（每个标的独立）===
    for stock in [寒武纪, 山东黄金, 工业富联, 紫金矿业]:
        
        # 构建证据包（严格按数据可用性规则）
        evidence = build_evidence_pack(
            stock=stock,
            judgment_date=week_start_date,
            weekly_data=get_available_weekly(stock, week_start_date),
            macro_data=get_available_macro(week_start_date),
            quarterly_data=get_available_quarterly(stock, week_start_date)
        )
        
        # 调用Claude API
        c1_to_c6 = call_claude_api(evidence)
        
        # 框架计算
        binary_code = f"{c1_to_c6['c2']}{c1_to_c6['c1']}{c1_to_c6['c4']}{c1_to_c6['c3']}{c1_to_c6['c6']}{c1_to_c6['c5']}"
        renshi_result = fcas_analyze(binary_code)
        
        # === 两层合成 ===
        combined = combine_tianshi_renshi(tianshi_diagnosis, renshi_result)
        
        # === 记录 ===
        save_result(week_start_date, stock, tianshi_diagnosis, renshi_result, combined, c1_to_c6)
```

### 5.3 验证指标

判断完成后，用后续实际价格评估：
- 1周后收盘价 vs 判断周收盘价 → 1W return
- 4周后收盘价 → 1M return
- 13周后收盘价 → 3M return

**评价标准**：
不是简单的 FAVORABLE→涨 / ADVERSE→跌。

之前115周纯奇门回测已经发现：ADVERSE时期A股仍可能涨（整体牛市覆盖结构逆风）。

正确的评价方式：
1. **相对收益**：FAVORABLE周的平均收益 vs ADVERSE周的平均收益，前者应显著高于后者
2. **风险规避**：STRONG ADVERSE期间是否避开了最大的单周跌幅
3. **择时价值**：如果只在FAVORABLE周持仓、ADVERSE周空仓，相对于买入持有的超额收益
4. **个股区分度**：同一周内4个标的的人事层判断是否有差异（天时层相同，人事层应不同）

---

## 六、工程细节

### 6.1 API调用量
- 115周 × 4标的 = 460次Claude API调用
- 模型：Opus 4.6
- 估计成本：$30-50（取决于证据包大小）

### 6.2 断点续传
回测可能因API限流或网络问题中断。
每完成一周的4个标的判断，立即保存到JSON。
重启时从最后完成的周继续。

### 6.3 输出文件
```
backtest_115w_results.json  — 所有460条判断记录
backtest_115w_summary.json  — 汇总统计
backtest_115w_log.txt       — 运行日志
```

---

## 七、所需数据文件

### Batch 1（个股周度 + 宏观周度）— 需要确认位置
- 寒武纪周度 (115周)
- 山东黄金周度 (115周)
- 工业富联周度 (115周)
- 紫金矿业周度 (115周)
- 上海金周度 (117周)
- 美元兑人民币 (51条)
- 北向资金周度 (114条)
- 融资余额周度 (106条)
- COMEX金期货
- 主要指数周收盘价

### Batch 2（宏观月度 + 季度财务）— 已在本session完成
- CPI/PPI (26条月度)
- 半导体销售 (27条月度)
- 集成电路产量 (23条月度)
- 央行黄金储备 (26条月度)
- 制造业PMI (27条月度)
- 非制造业PMI分项 (27条月度)
- 社融 (26条月度)
- M2 (26条月度)
- 工业富联季度财务 (8季)
- 紫金矿业季度财务 (8季)
- 寒武纪季度财务 (8季)
- 山东黄金季度财务 (8季)

---

## 八、下一步

1. 确认Batch 1数据文件位置（你Mac本地路径）
2. 将Batch 1上传到本session，合并成统一数据结构
3. 编写回测脚本 `backtest_115w.py`
4. 先跑1周×1标的做冒烟测试
5. 确认prompt质量后，跑完整115周×4标的
