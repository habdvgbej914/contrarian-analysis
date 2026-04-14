# FCAS Cowork 文件夹指令

## 数据诚信规则（最高优先级）
不得编造、虚构、揣测任何数据、数字、统计结果。
所有数值必须来自实际运行的代码输出或文件内容。
违反必须标注"未验证"或"待计算"。

## 项目背景
FCAS（Force Configuration Analysis System）是一个结构状态诊断系统。
详见 PROJECT_INSTRUCTIONS.md。

## 当前任务：587周×8标的完整回测
1. 把 data/xlsx/ 中的37个Wind文件转成 data/json/ 标准化格式
2. 编写 backtest_587w.py（基于现有架构扩展）
3. 8标的：格力电器/中兴通讯/五粮液/恒瑞医药/招商银行/中国平安/中国石油/隆基绿能
4. Claude Opus API调用做C1-C6判断，证据包含周度+宏观+季度数据
5. 数据可用性：周度T-1，月度滞后1月，季度按法定披露时限
6. 支持 --resume 断点续传
7. 运行完后叠加天时层做交叉验证

## 关键约束
- 不使用 three_layer_judgment() 做天时评估
- 天时层用直符宫+直使宫的星门格局评分方法
- 所有输出用商业语言，不暴露玄学词汇
- API模型固定为 claude-opus-4-20250514
- ANTHROPIC_API_KEY 在 .env 文件中

## 文件说明
- fcas_mcp.py: 奇门排盘引擎（2848行）
- fcas_engine_v2.py: 核心引擎（从MCP分离）
- stock_positioning.py: 10标的个性化天时定位
- daily_scan.py: v2.1每日扫描器
- data/xlsx/: 37个Wind原始xlsx文件
- data/json/: 转换后的标准化JSON
