# FCAS排盘引擎修复 - VPS部署步骤
# 2026-04-05

## 修复内容
1. 节气计算: 2026硬编码 → ephem天文算法(任意年份)
2. 九星旋转: 线性宫序[1-9] → 外环序[1,8,3,4,9,2,7,6]
3. 天盘天干: 整体偏移 → 星带地盘干走
4. 八门/八神: 线性宫序 → 外环序

## 验证状态
- 九星旋转: 10组app截图 × 8宫 = 80/80 全部通过 ✓
- 天盘天干: 规则确认(星带原位地盘干) ✓
- 暗干计算: 2组验证全部通过 ✓

## 文件说明
- fcas_engine_v2_fixed.py  → 修复后的完整引擎(替换原文件)
- paipan_core.py           → 独立排盘核心模块(参考/备用)
- fix_paipan.py            → 自动修复脚本(可重复执行)

## VPS操作步骤

### 方法A: 直接替换(推荐)

```bash
# 1. SSH到VPS
ssh root@45.63.99.97

# 2. 备份原文件
cd /root/fcas
cp fcas_engine_v2.py fcas_engine_v2.py.bak.$(date +%Y%m%d)

# 3. 从本地上传修复后的文件
# (在本地终端执行)
scp ~/Downloads/fcas_engine_v2_fixed.py root@45.63.99.97:/root/fcas/fcas_engine_v2_fixed.py

# 4. 在VPS上替换
ssh root@45.63.99.97
cd /root/fcas
cp fcas_engine_v2_fixed.py fcas_engine_v2.py

# 5. 安装ephem(如果还没装)
pip install ephem --break-system-packages

# 6. 修复import路径(VPS用fcas_mcp)
sed -i 's/from fcas_engine import/from fcas_mcp import/' fcas_engine_v2.py

# 7. 测试
python3 -c "from fcas_engine_v2 import paipan; print('OK')"

# 8. 重启daily_scan
# (如果crontab调用的是fcas_engine_v2.py, 不需要额外操作)
```

### 方法B: 用修复脚本

```bash
# 1. 上传修复脚本到VPS
scp ~/Downloads/fix_paipan.py root@45.63.99.97:/root/fcas/

# 2. 在VPS上执行
ssh root@45.63.99.97
cd /root/fcas
pip install ephem --break-system-packages
python3 fix_paipan.py fcas_engine_v2.py fcas_engine_v2_fixed.py

# 3. 备份并替换
cp fcas_engine_v2.py fcas_engine_v2.py.bak
cp fcas_engine_v2_fixed.py fcas_engine_v2.py

# 4. 测试
python3 -c "from fcas_engine_v2 import paipan; print('OK')"
```

### 本地同步

```bash
# 同步到本地
cd ~/Desktop/fcas
cp fcas_engine_v2.py fcas_engine_v2.py.bak
scp root@45.63.99.97:/root/fcas/fcas_engine_v2.py .
```

## 修复后待做
1. [ ] 用app排10个测试用例重新验证引擎输出
2. [ ] 精确实现八门旋转(值使加时支)
3. [ ] 实现拆补局的精确符头判断
4. [ ] 重跑天时层回测(v5c日干财爻法)
5. [ ] 推送GitHub
