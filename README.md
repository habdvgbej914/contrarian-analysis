# Contrarian Opportunity Analysis System

**逆向机会分析系统**

An MCP Server that identifies structural mislocations between Form (what has crystallized) and Flow (what is circulating) in any domain — surfacing opportunities that mainstream narratives undervalue.

一个 MCP Server，识别任何领域中"形"与"流"之间的结构性错位——发现被主流叙事低估的机会。

---

## The Problem / 要解决的问题

Most opportunity analysis is linear: list pros and cons, weigh them, decide. This misses **structural dynamics** — situations where all the infrastructure exists but nobody is paying attention (undervalued), or where everyone is excited but nothing real has been built (bubble).

大多数机会分析是线性的：列优缺点、权衡、决策。这忽略了**结构性动态**——所有基础设施都在但没人关注（被低估），或者所有人都兴奋但没有真实产品（泡沫）。

This system detects exactly these mislocations.

## How It Works / 工作原理

### Three-Layer Structure / 三层结构

| Layer | What It Measures | Criteria |
|-------|-----------------|----------|
| **Environment** | Momentum — is the wind at your back? | C1: Trend alignment · C2: Energy state |
| **Participant** | Feasibility — can you actually do this? | C3: Incumbent fit · C4: Your sustainability |
| **Foundation** | Substance — is there something real here? | C5: Fundamentals · C6: Domain weight |

### Five Dimensions Per Criterion / 每条依据的五个维度

Each criterion is assessed across five dimensions — not weighted, analyzed as a unity:

| Dimension | Question |
|-----------|----------|
| **Origin** | Why does this exist? What root problem does it solve? |
| **Visibility** | How recognized is it by the outside world? |
| **Growth** | Is the opportunity space expanding or contracting? |
| **Constraint** | What barriers, regulations, or ceilings exist? |
| **Foundation** | What infrastructure and resources support it? |

### Binary Output → 64 Configurations / 二进制输出 → 64种情境

Each criterion outputs **1** (positive) or **0** (negative). Six bits = 64 possible configurations, each with distinct strategic implications.

### Core Detection: Form-Flow Mislocation / 核心检测：形流错位

| Pattern | What It Means | Action |
|---------|--------------|--------|
| **Form without Flow** | Real infrastructure, no attention | Classic undervalued opportunity |
| **Flow without Form** | Lots of buzz, nothing built | Validate before entering |
| **Both present** | Mainstream opportunity | Expect competition |
| **Neither present** | Dead zone | Walk away |

---

## Architecture / 架构

```
User: "Should I enter [domain]?"
         ↓
Claude (LLM) ← qualitative 5-dimension assessment
         ↓                per criterion
MCP Server  ← receives 6 binary judgments
         ↓
┌─────────────────────────────┐
│     Analysis Engine         │
│  ┌───────────────────────┐  │
│  │ Layer Synthesis        │  │
│  │ (3 layers × 2 criteria)│  │
│  ├───────────────────────┤  │
│  │ Cross-Layer Matrix     │  │
│  │ (Momentum × Substance) │  │
│  ├───────────────────────┤  │
│  │ Mislocation Detection  │  │
│  │ (Form-Flow analysis)   │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
         ↓
Claude translates → Business recommendation
                    (no framework jargon)
```

**Key design decision:** Claude handles qualitative reasoning. The MCP Server handles structural computation. Reasoning and structure are separated.

---

## Quick Start / 快速开始

### Prerequisites

```bash
pip install mcp python-dotenv
```

### With Claude Code

```bash
cd contrarian-analysis
claude mcp add contrarian-analysis python3 contrarian_analysis_mcp.py
claude
```

Then ask:
```
用contrarian analysis框架分析一下"中国独立理财顾问的合规科技"
```

### With Claude Desktop

Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "contrarian-analysis": {
      "command": "python3",
      "args": ["/full/path/to/contrarian_analysis_mcp.py"]
    }
  }
}
```

---

## MCP Tools / 可用工具

| Tool | Description |
|------|-------------|
| `get_framework_guide()` | Returns complete framework structure |
| `quick_scan(domain, ...)` | Fast 6-bit scan — 6 boolean inputs, for rapid multi-domain screening |
| `deep_scan(domain, ...)` | Full 30-dimension analysis — 6 judgments + 30 assessments, records complete reasoning chain |
| `get_analysis_history()` | View all past results (quick + deep) with reasoning chain summaries |

### Example: Quick Scan

```python
quick_scan(
    domain="RegTech for Independent Financial Advisors in China",
    trend_aligned=True,          # C1: regulatory pressure increasing
    energy_accumulating=True,    # C2: quiet building, not retreating
    incumbents_misaligned=True,  # C3: big players selling trucks for deliveries
    can_sustain=True,            # C4: can survive dormancy
    fundamentals_solid=True,     # C5: demand is regulatory-driven, not narrative
    domain_heavy=True            # C6: knowledge barrier + trust barrier + integration barrier
)
```

Output:
```
Binary Code: 110011
Momentum: strong | Substance: solid
→ Best window. Feasibility layer decisive.
→ Highest feasibility. Incumbents misaligned and you can sustain.
→ Most stable. Solid fundamentals and heavy domain.
Form-Flow: no_mislocation_positive
```

---

## Project Structure / 项目结构

```
contrarian-analysis/
├── contrarian_analysis_mcp.py    # MCP Server (core)
├── analysis_history.json         # Analysis history (auto-generated)
├── docs/
│   └── framework_spec_v0.1.docx  # Full framework specification
├── README.md
├── .env                          # API keys (not committed)
└── .gitignore
```

---

## What This Demonstrates / 技术展示

- **MCP Server development** — tools, resources, and prompts following the Model Context Protocol
- **Structured AI reasoning** — a decision framework that goes beyond "list pros and cons"
- **LLM + deterministic logic separation** — qualitative judgment (LLM) × structural computation (code)
- **Binary combinatorial analysis** — 6-bit system producing 64 distinct strategic configurations
- **Bilingual operation** — native English and Chinese throughout

---

## Roadmap / 路线图

- [ ] LLM-powered per-criterion binary judgment (replace keyword matching)
- [ ] Web search integration for real-time domain research
- [ ] Historical trend tracking across multiple analyses of the same domain
- [ ] Comparative analysis mode (scan multiple domains simultaneously)
- [ ] Export analysis reports as PDF

---

## License

MIT