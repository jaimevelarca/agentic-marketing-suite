# Agentic Marketing Suite — Hackathon Video Demonstration Guide

> **Maximum Allowed Duration:** 4 minutes (240 seconds). Target Duration: 3 minutes 45 seconds (225s).  
> **Platform Requirements:** Publicly visible on YouTube or Vimeo, in English (or with English subtitles).  
> **Mandatory Visual Evidence:** Must demonstrate the backend running on Google Cloud (Cloud Run, Vertex AI, Firestore, `.run.app` URL).

---

## 1. Pre-Recording Preparation Checklist

Open the following tabs in a dedicated Google Chrome window (1920x1080 resolution, 100% zoom):

- [ ] **Tab 1 — GitHub Repository:**  
  URL: `https://github.com/jaimevelarca/agentic-marketing-suite`  
  *Pre-scroll to:* System Architecture Mermaid Diagram in `README.md`.
- [ ] **Tab 2 — Cloud Run Review Console (Live Prod):**  
  URL: `https://console-m6hls6q6ua-uc.a.run.app/corridas/nueva/`  
  *Ready with:* Client onboarding form with `acme_global.json` pre-selected.
- [ ] **Tab 3 — Active Pipeline Session:**  
  URL: `https://console-m6hls6q6ua-uc.a.run.app/corridas/<session_id>/`  
  *Ready with:* A live run showing the 19 agents across 6 layers, with Layer 2 paused at the emerald `#1ebe82` gate.
- [ ] **Tab 4 — Interactive Deliverable Review:**  
  URL: `https://console-m6hls6q6ua-uc.a.run.app/clientes/acme-global/bloques/active_strategy/`  
  *Ready with:* Deliverable cards, showing strategic thesis, KPI contracts, and the emerald `#1ebe82` approve button.
- [ ] **Tab 5 — Compiled 9-Act Presentation Deck:**  
  URL: `https://console-m6hls6q6ua-uc.a.run.app/propuestas/acme-global/presentacion/`  
  *Ready with:* Fullscreen interactive HTML slide deck with metric counters and 2x2 positioning quadrant.
- [ ] **Tab 6 — Google Cloud Console (Cloud Run Dashboard):**  
  URL: `https://console.cloud.google.com/run?project=agentic-marketing-suite-prod`  
  *Showing:* Service `console` and Job `suite-orchestrator` in `us-central1`.
- [ ] **Tab 7 — Google Cloud Console (Firestore Studio):**  
  URL: `https://console.cloud.google.com/firestore/databases/-default-/data/panel?project=agentic-marketing-suite-prod`  
  *Showing:* Collection `clients/acme-global/blocks/`.
- [ ] **Terminal (Clean Window):**  
  *Ready with command:* `uv run --all-extras pytest -q` (shows 335 passed).

---

## 2. Second-by-Second Shot List & Voiceover Script

### Act 1: The Problem & System Architecture (0:00 – 0:45 | 45s)
- **Screen:** Tab 1 (GitHub README & Mermaid Architecture Diagram).
- **Visual Cue:** Mouse circles the 6 layers and the Gemini 3.7 / ADK 2.x nodes in the diagram.
- **Voiceover (English):**
  > *"Welcome to the Agentic Marketing Suite, an institutional fleet of 19 autonomous AI agents built on Google Cloud for the All Things Agentic Hackathon, competing in the Fortified Enterprise Fleet category.*  
  > *Digital marketing today is fragmented across isolated silos: market research, 90-day strategy, 4-week content calendars, multimodal copy, visual assets, and paid media distribution.*  
  > *Rather than a simple conversational chatbot, we built an asynchronous enterprise fleet. It is orchestrated via Google ADK 2.x Graph Workflows, powered by Gemini 3.7 Flash and Vertex AI, persisted in Firestore Native, and strictly governed by sacred `#1ebe82` Human Financial Gates."*

---

### Act 2: Live Console & Asynchronous Execution (0:45 – 1:35 | 50s)
- **Screen:** Tab 2 (`/corridas/nueva/`) → Switch to Tab 3 (`/corridas/<session_id>/`).
- **Visual Cue:** Show the drag-and-drop onboarding wizard with `acme_global.json`. Click start. Switch to the session view showing the 19 agents updating in real-time.
- **Voiceover (English):**
  > *"Here is our review console running live on Google Cloud Run behind Direct Identity-Aware Proxy. An enterprise operator onboards a client through our structured wizard.*  
  > *Behind the scenes, a Cloud Run Job triggers our ADK 2.x graph workflow. Layer 1 executes Business Diagnostics, Audience Intelligence, and Competitive Radar, extracting brand USPs and Ideal Customer Profiles.*  
  > *Notice that each agent’s output is a strictly typed memory block, streamed directly to Firestore Native. The system runs asynchronously without blocking active user sessions."*

---

### Act 3: The Sacred `#1ebe82` Human Gate & In-Place Editing (1:35 – 2:25 | 50s)
- **Screen:** Tab 3 (Session pause) → Switch to Tab 4 (Deliverable card `/bloques/active_strategy/`).
- **Visual Cue:** Zoom in on the emerald `#1ebe82` pause banner. Click into the deliverable card. Click `Edit`, modify a KPI target number or copy phrase, save, and click the prominent `#1ebe82` **"Aprobar Bloque"** button.
- **Voiceover (English):**
  > *"Now, witness our sacred #1ebe82 Human Gate in action.*  
  > *True enterprise automation requires zero blind spend. When the Strategy Orchestrator finishes, the ADK 2.x workflow raises a native RequestInput interrupt, cleanly suspending execution without burning idle compute.*  
  > *In the review console, operators review visual deliverable cards rather than raw JSON. I can inspect audience segments, edit strategic copy in-place, and click the emerald `#1ebe82` approval button.*  
  > *Instantly, the gate updates in Firestore, and our ADK orchestrator automatically resumes downstream execution—recalculating all subsequent production layers with the human-approved adjustments."*

---

### Act 4: Multimodal Production & FastMCP Gateway (2:25 – 3:15 | 50s)
- **Screen:** Switch to Tab 5 (Interactive 9-Act HTML Deck) → Switch to IDE showing `model_armor.py` and `financial_gate.py`.
- **Visual Cue:** Flip through the 9-Act interactive slides with interactive metrics. Briefly show FastMCP tool definitions and Model Armor code.
- **Voiceover (English):**
  > *"Downstream, Layer 4 Production generates copy assets, visual creative specs via Gemini 3.1 Flash Image, landing pages, and email nurture flows.*  
  > *With one click, the suite compiles this interactive 9-act HTML presentation deck and executive PDF report directly from Firestore memory.*  
  > *For external distribution, our FastMCP gateway connects to Meta Ads and Resend Email. It is guarded by our Human Financial Authorization Gate—which rejects any API call exceeding confirmed client budget ceilings—and Model Armor powered by Google Gemma, which intercepts prompt injections and redacts sensitive PII before execution."*

---

### Act 5: Google Cloud Proof & Serverless Economics (3:15 – 3:55 | 40s)
- **Screen:** Switch to Tab 6 (Cloud Run Dashboard) → Tab 7 (Firestore Console) → Terminal.
- **Visual Cue:** Show `console` running on `.run.app` with `cpu_idle: true`. Show Firestore collections. Switch to terminal and run `uv run --all-extras pytest -q` showing 335 tests green.
- **Voiceover (English):**
  > *"Everything you see is deployed on Google Cloud via Pulumi IaC. Here is our Cloud Run service with request-based billing: when idle, it scales to zero for $0.00 compute spend.*  
  > *Here is our Firestore Native Memory Bank maintaining multi-week state across sessions, and Vertex AI logs running Gemini 3.7 Flash.*  
  > *Finally, our offline hermetic test suite runs 335 unit tests in under 5 seconds, guaranteeing 100% reliability.*  
  > *Agentic Marketing Suite proves that autonomous, multi-agent enterprise fleets are here today on Google Cloud. Thank you!"*

---

## 3. Video Metadata (Ready to Copy into YouTube)

### Title
```
Agentic Marketing Suite — Autonomous 19-Agent Fleet on Google Cloud & Gemini Enterprise
```

### Description
```
Submission for the All Things Agentic Hackathon (Devpost)
Category: Fortified Enterprise Fleet (also excelling in Taskmaster)

Agentic Marketing Suite is an institutional, 19-agent autonomous marketing engine running on Google Cloud. Orchestrated via Google ADK 2.x Graph Workflows and powered by Gemini 3.7 Flash, it automates the full digital marketing lifecycle—from market intelligence to 90-day strategy, 4-week editorial calendars, multimodal creative production, and live distribution—governed by sacred #1ebe82 Human Financial Gates and Model Armor powered by Google Gemma.

🔗 Live Hosted URL: https://console-m6hls6q6ua-uc.a.run.app
📂 GitHub Repository: https://github.com/jaimevelarca/agentic-marketing-suite
📖 Medium Technical Deep-Dive: https://medium.com/@jaimevelarca/how-we-built-an-institutional-19-agent-marketing-fleet-on-google-cloud-gemini-enterprise

Timestamps:
0:00 - Introduction & 19-Agent Architecture
0:45 - Google Cloud Run Console & Asynchronous Execution
1:35 - The Sacred #1ebe82 Human Gate & In-Place Editing
2:25 - Multimodal Creative, 9-Act Decks & FastMCP
3:15 - Google Cloud Backend Proof & Serverless Economics

Built with:
• Google ADK 2.x (DAG Graph Workflows)
• Gemini 3.7 Flash, Gemini 3.5 Flash-Lite, Gemini 3.1 Pro, Gemini 3.1 Flash Image
• Google Gemma (Model Armor Security)
• Google Cloud Run (Serverless, $0 idle compute)
• Firestore Native (Multi-Week Memory Bank)
• Direct Cloud Run IAP (Google Workspace OIDC)
• Pulumi IaC (Python)

#AllThingsAgentic #GeminiEnterprise #GoogleCloud #AIagents #BuildWithAI #VertexAI
```

### Tags
```
AllThingsAgentic, GeminiEnterprise, GoogleCloud, CloudRun, VertexAI, Gemini3.7, GoogleADK, AIAgents, MultiAgent, Python, Pulumi, Firestore, EnterpriseAI, FastMCP, Gemma
```
