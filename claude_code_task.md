# FCAS Daily Scan v4.0 — 三层交叉信号整合任务

## 背景
FCAS daily_scan.py 当前是v3.0，已有天时v6+六亲v2两层。现在需要整合第三层——人事层（Opus API判断C1-C6），实现三层交叉信号输出。

## 任务目标
将 daily_scan.py 从 v3.0 升级到 v4.0，新增：
1. Tushare数据获取模块（evidence_pack构建）
2. 人事层Opus API调用（C1-C6判断 → h_label → h_direction）
3. 三层交叉信号查表（天时×人事×六亲 → 分级标签）
4. 输出格式更新 + API失败graceful fallback

## 详细步骤

### Step 1: 读取现有代码
先读这些文件，理解现有架构：
- `~/Desktop/自主项目/fcas/daily_scan.py` (当前v3.0)
- `~/Desktop/自主项目/fcas/backtest_587w.py` (重点看380-520行：evidence_pack构建 + system prompt + API调用)
- `~/Desktop/自主项目/fcas/cross_validate_3layer_results.json` (只看combo_stats部分)
- `~/Desktop/自主项目/fcas/.env` (确认有ANTHROPIC_API_KEY)

### Step 2: 创建 `fetch_tushare.py` — Tushare数据获取模块
```python
# 功能：获取指定标的最近N周的周频数据，构建evidence_pack
# Tushare token从.env读取：TUSHARE_TOKEN=47c200afe3a46dbe8713e776571cdfd7fa715cb025880ff6c4d98d5b
# 
# 接口：
#   def build_evidence_pack(stock_code: str, stock_name: str, now: datetime) -> dict
#     返回格式必须和 backtest_587w.py 中构建的evidence_pack一致
#     （先看backtest_587w.py:380-446确认字段）
#
# 数据来源：
#   - pro.weekly() 获取周线（OHLCV）
#   - pro.daily_basic() 获取换手率等（如果积分够）
#   - 如果某接口积分不够，用可用接口的数据构建近似pack
#
# 注意：
#   - stock_code格式转换：FCAS用 "000651.SZ" 但Tushare也用这个格式，无需转换
#   - 获取最近8-12周数据即可（evidence_pack不需要太长历史）
#   - 加入缓存：同一天同一标的只调一次Tushare（避免H4频率重复调用）
```

### Step 3: 创建 `assess_renshi.py` — 人事层评估模块
```python
# 功能：调用Opus API评估C1-C6，返回人事层标签
#
# 核心逻辑（从backtest_587w.py复现）：
#   1. 构建system prompt（要求评估C1-C6六个二进制标准，纯JSON输出）
#   2. 构建user message（包含evidence_pack数据）
#   3. 调用anthropic.Anthropic() client
#   4. 解析返回的C1-C6（每个0或1）
#   5. 用signal_map映射：
#      signal_map = {0:"ADVERSE", 1:"ADVERSE", 2:"CAUTIOUS", 3:"MIXED",
#                    4:"FAVORABLE", 5:"STRONGLY_FAVORABLE", 6:"STRONGLY_FAVORABLE"}
#      ones = sum(c1,c2,c3,c4,c5,c6)
#      h_label = signal_map[ones]
#   6. h_direction映射：
#      H_FAV: FAVORABLE, STRONGLY_FAVORABLE
#      H_NEU: MIXED  
#      H_ADV: CAUTIOUS, ADVERSE
#
# 接口：
#   def assess_stock_renshi(stock_code, stock_name, evidence_pack, model="claude-sonnet-4-20250514") -> dict
#     返回: {'h_label': str, 'h_direction': str, 'c_values': dict, 'ones': int}
#     model默认Sonnet（省钱），可通过环境变量FCAS_RENSHI_MODEL覆盖
#
# IMPORTANT: system prompt和user message格式必须精确复现backtest_587w.py:453-494的逻辑
# 不要自己发明prompt，从backtest_587w.py复制
#
# 错误处理：
#   - API调用失败 → 返回 {'h_label': 'MIXED', 'h_direction': 'H_NEU', 'error': str}
#   - JSON解析失败 → 同上
#   - 超时30秒 → 同上
```

### Step 4: 修改 `daily_scan.py` → v4.0
在现有v3.0基础上修改，不要重写：

#### 4a. 新增import
```python
from fetch_tushare import build_evidence_pack
from assess_renshi import assess_stock_renshi
```

#### 4b. 新增三层交叉组合表
从 cross_validate_3layer_results.json 的 combo_stats 中提取 N>=30 的组合：

```python
# 三层交叉信号表（N>=30的可靠组合，按13W回报分级）
# 数据来源：cross_validate_3layer_results.json [VERIFIED]
CROSS_3LAYER = {
    # PRIME级（13W >= 4.0%）
    'T_FAV×H_NEU×L_ADV':  {'grade': 'PRIME',    'r13w': 4.767, 'n': 43},
    'T_FAV×H_FAV×L_ADV':  {'grade': 'PRIME',    'r13w': 4.499, 'n': 63},
    # STRONG级（13W 3.0-4.0%）
    'T_FAV×H_NEU×L_FAV':  {'grade': 'STRONG',   'r13w': 3.838, 'n': 180},
    'T_NEU×H_FAV×L_FAV':  {'grade': 'STRONG',   'r13w': 3.705, 'n': 850},
    'T_FAV×H_FAV×L_NEU':  {'grade': 'STRONG',   'r13w': 3.454, 'n': 80},
    'T_ADV×H_NEU×L_FAV':  {'grade': 'STRONG',   'r13w': 3.305, 'n': 264},
    'T_FAV×H_NEU×L_NEU':  {'grade': 'STRONG',   'r13w': 3.202, 'n': 34},
    'T_ADV×H_FAV×L_FAV':  {'grade': 'STRONG',   'r13w': 3.111, 'n': 417},
    # MODERATE级（13W 2.0-3.0%）
    'T_ADV×H_FAV×L_NEU':  {'grade': 'MODERATE', 'r13w': 2.852, 'n': 110},
    'T_NEU×H_FAV×L_NEU':  {'grade': 'MODERATE', 'r13w': 2.734, 'n': 239},
    'T_NEU×H_NEU×L_ADV':  {'grade': 'MODERATE', 'r13w': 2.106, 'n': 207},
    # WEAK级（13W 1.0-2.0%）
    'T_NEU×H_NEU×L_FAV':  {'grade': 'WEAK',     'r13w': 1.992, 'n': 552},
    'T_NEU×H_NEU×L_NEU':  {'grade': 'WEAK',     'r13w': 1.646, 'n': 169},
    'T_ADV×H_NEU×L_ADV':  {'grade': 'WEAK',     'r13w': 1.500, 'n': 75},
    'T_NEU×H_FAV×L_ADV':  {'grade': 'WEAK',     'r13w': 1.451, 'n': 265},
    # FLAT级（13W < 1.0%）
    'T_FAV×H_FAV×L_FAV':  {'grade': 'FLAT',     'r13w': 0.515, 'n': 237},
    'T_ADV×H_FAV×L_ADV':  {'grade': 'FLAT',     'r13w': 0.491, 'n': 93},
    'T_ADV×H_NEU×L_NEU':  {'grade': 'FLAT',     'r13w': 0.488, 'n': 76},
}

CROSS_3LAYER_TAG = {
    'PRIME':    '⚡⚡ PRIME',
    'STRONG':   '⚡ STRONG', 
    'MODERATE': 'MODERATE',
    'WEAK':     'WEAK',
    'FLAT':     'FLAT',
    'UNKNOWN':  '—',
}
```

#### 4c. 新增函数 get_3layer_cross_signal()
```python
def get_3layer_cross_signal(t_dir, h_dir, l_dir):
    """查三层交叉信号表，返回(grade, combo_key, r13w)"""
    # t_dir: 'FAV'/'ADV'/'NEU' (from _tianshi_direction)
    # h_dir: 'H_FAV'/'H_ADV'/'H_NEU' (from assess_renshi)  
    # l_dir: 'FAV'/'UNFAV'/'NEU' (from _liuqin_direction)
    
    # 统一方向标签格式
    t = f"T_{t_dir}"
    h = h_dir  # 已经是H_FAV/H_NEU/H_ADV格式
    # l_dir的UNFAV需要映射为ADV（和三层交叉验证中的L_ADV对应）
    l_map = {'FAV': 'L_FAV', 'UNFAV': 'L_ADV', 'NEU': 'L_NEU'}
    l = l_map.get(l_dir, 'L_NEU')
    
    combo_key = f"{t}×{h}×{l}"
    info = CROSS_3LAYER.get(combo_key)
    if info:
        return info['grade'], combo_key, info['r13w']
    return 'UNKNOWN', combo_key, None
```

#### 4d. 修改 run_qimen_scan() — 在per-stock循环中加入人事层
在六亲评估之后、交叉信号之前，新增：

```python
# 人事层评估（per-stock, Opus/Sonnet API）
evidence_pack = build_evidence_pack(sc, cfg['name'], now)
if evidence_pack and not evidence_pack.get('error'):
    renshi_r = assess_stock_renshi(sc, cfg['name'], evidence_pack)
else:
    renshi_r = {'h_label': 'MIXED', 'h_direction': 'H_NEU', 'error': 'no data'}

h_label = renshi_r['h_label']
h_direction = renshi_r['h_direction']
renshi_error = renshi_r.get('error')

# 三层交叉信号（天时×人事×六亲）
t_dir = _tianshi_direction(assessment)
l_dir = _liuqin_direction(liuqin_label)
cross3_grade, cross3_combo, cross3_r13w = get_3layer_cross_signal(t_dir, h_direction, l_dir)
```

保留现有的天时×六亲两层交叉信号作为备用。

#### 4e. 更新 stock_results.append() 
新增字段：
```python
'h_label': h_label,
'h_direction': h_direction,
'renshi_error': renshi_error,
'cross3_grade': cross3_grade,
'cross3_combo': cross3_combo,
'cross3_r13w': cross3_r13w,
```

#### 4f. 更新 format_output() — 显示三层信号
在每个标的的输出块中，六亲行之后新增：
```python
# 人事层 + 三层交叉
h_tag = sr.get('h_label', 'MIXED')
c3_grade = CROSS_3LAYER_TAG.get(sr.get('cross3_grade', 'UNKNOWN'), '—')
c3_combo = sr.get('cross3_combo', '')
if sr.get('renshi_error'):
    lines.append(f"[{h_tag}?] H-layer unavailable | ×{cross}")
else:
    lines.append(f"[{h_tag}] | 3L:{c3_grade} ({c3_combo})")

# PRIME信号突出显示
if sr.get('cross3_grade') == 'PRIME':
    r13w = sr.get('cross3_r13w', 0)
    lines.append(f"⚡⚡ PRIME 3-layer signal. Historical 13W: +{r13w:.1f}%")
elif sr.get('cross3_grade') == 'STRONG':
    r13w = sr.get('cross3_r13w', 0)
    lines.append(f"⚡ Strong 3-layer signal. Historical 13W: +{r13w:.1f}%")
```

#### 4g. 更新 save_history() — 记录人事层
在history record中新增：
```python
'h_label': sr.get('h_label', 'MIXED'),
'cross3_grade': sr.get('cross3_grade', 'UNKNOWN'),
'cross3_combo': sr.get('cross3_combo', ''),
```

#### 4h. 更新版本号和docstring
v3.0 → v4.0，在docstring中记录变更。

### Step 5: 测试
```bash
cd ~/Desktop/自主项目/fcas/
python3 -c "from fetch_tushare import build_evidence_pack; from datetime import datetime; r = build_evidence_pack('000651.SZ', '格力电器', datetime.now()); print(r)"
```

```bash
python3 daily_scan.py
```

### Step 6: 部署到VPS
```bash
# 复制新文件
scp fetch_tushare.py assess_renshi.py root@45.63.99.97:~/fcas/

# 复制更新的daily_scan
scp daily_scan.py root@45.63.99.97:~/fcas/

# VPS上安装tushare
ssh root@45.63.99.97 "pip3 install tushare --break-system-packages"

# VPS上加TUSHARE_TOKEN到.env
ssh root@45.63.99.97 "echo 'TUSHARE_TOKEN=47c200afe3a46dbe8713e776571cdfd7fa715cb025880ff6c4d98d5b' >> ~/fcas/.env"

# VPS上的import路径修正
ssh root@45.63.99.97 "cd ~/fcas && sed -i 's/from fcas_engine_v2 import/from fcas_mcp import/' fetch_tushare.py assess_renshi.py"

# 测试
ssh root@45.63.99.97 "cd ~/fcas && python3 daily_scan.py"
```

## 关键约束

1. **evidence_pack格式必须精确复现backtest_587w.py** — 先读380-446行，不要猜
2. **system prompt必须精确复现backtest_587w.py:453-494** — 复制，不要改写
3. **signal_map硬编码** — ones count决定标签，不是Claude自己判断
4. **API失败不能阻塞扫描** — 人事层失败时退回两层交叉（天时×六亲），正常输出
5. **Tushare缓存** — 同一天同一标的只调一次（dict缓存即可）
6. **中石油(601857.SH)六亲排除** — 已有liuqin_exclude逻辑，不要改动
7. **CROSS_3LAYER表的数据全部来自cross_validate_3layer_results.json** — 不要修改数值

## .env需要的变量
```
ANTHROPIC_API_KEY=已有
TUSHARE_TOKEN=47c200afe3a46dbe8713e776571cdfd7fa715cb025880ff6c4d98d5b
FCAS_RENSHI_MODEL=claude-sonnet-4-20250514  # 可选，默认Sonnet
TELEGRAM_BOT_TOKEN=已有
TELEGRAM_CHAT_ID=已有
```
