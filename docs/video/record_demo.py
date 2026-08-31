#!/usr/bin/env python3
"""
Autonomous demo recorder for the All Things Agentic hackathon video.

Drives the live IAP-protected console with Playwright, records one clean
1920x1080 clip per act, then muxes each clip against its voiceover track and
concatenates a master cut capped at MAX_TOTAL_SECONDS (3:19).

Usage
-----
  uv run --extra video python docs/video/record_demo.py plan
  uv run --extra video python docs/video/record_demo.py login
  uv run --extra video python docs/video/record_demo.py record [--acts 1,3] [--commit] [--headed]
  uv run --extra video python docs/video/record_demo.py assemble

`login` opens a real browser against a persistent Chrome profile so you can
complete the IAP / Google Workspace sign-in once by hand. Every later `record`
run reuses that profile unattended.

State safety
------------
By default the run is NON-MUTATING: it hovers and dwells on the pipeline-start
button, the in-place editor and the emerald "Aprobar Bloque" gate, but never
clicks them. Pass --commit to actually click them for the real take. Re-seed
afterwards with `uv run python docs/video/prepare_demo_data.py`.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIDEO_DIR = REPO / "docs" / "video"
AUDIO_DIR = VIDEO_DIR / "audio"
BUILD = VIDEO_DIR / "build"
CLIPS = BUILD / "clips"
PAGES = BUILD / "pages"
PROFILE = BUILD / "chrome-profile"
MASTER = BUILD / "agentic_marketing_suite_demo.mp4"

# ----------------------------------------------------------------------------
# Hard constraints
# ----------------------------------------------------------------------------
MAX_TOTAL_SECONDS = 199.0          # 3:19 hard cap
SAFETY_MARGIN = 0.60               # never plan right up to the cap; ffmpeg rounds
MAX_TAIL_PER_ACT = 2.0             # cap on the silent hold at the end of an act
FPS = 30
VIEWPORT = {"width": 1920, "height": 1080}

BASE = os.environ.get("DEMO_BASE_URL", "https://console-m6hls6q6ua-uc.a.run.app")
CLIENT_ID = os.environ.get("DEMO_CLIENT_ID", "acme-global")
BLOCK = os.environ.get("DEMO_BLOCK", "active_strategy")
SESSION_ID = os.environ.get("DEMO_SESSION_ID", "")
GH_REPO = "https://github.com/jaimevelarca/agentic-marketing-suite"
GCP_PROJECT = os.environ.get("DEMO_GCP_PROJECT", "agentic-marketing-suite-prod")
CHROME_APP = Path("/Applications/Google Chrome.app")

# The sacred #1ebe82 is reserved for human gates in any UI (see CLAUDE.md), so
# the synthetic cursor is deliberately neutral and must never use it.
CURSOR_FILL = "rgba(255,255,255,.28)"
CURSOR_RING = "#0f172a"


@dataclass
class Act:
    n: int
    key: str
    label: str
    audio: str
    audio_dur: float = 0.0
    tail: float = 0.0

    @property
    def target(self) -> float:
        return self.audio_dur + self.tail

    @property
    def clip(self) -> Path:
        return CLIPS / f"act{self.n}.webm"

    @property
    def muxed(self) -> Path:
        return BUILD / f"act{self.n}_muxed.mp4"


ACTS = [
    Act(1, "intro", "Architecture & the problem", "act1_intro.m4a"),
    Act(2, "onboarding", "Live console & async execution", "act2_onboarding.m4a"),
    Act(3, "human_gate", "The sacred #1ebe82 human gate", "act3_human_gate.m4a"),
    Act(4, "production", "Multimodal production & FastMCP", "act4_creative_production.m4a"),
    Act(5, "cloud", "Google Cloud proof & economics", "act5_cloud_proof.m4a"),
]


# ----------------------------------------------------------------------------
# Timeline planning
# ----------------------------------------------------------------------------
def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def mmss(s: float) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def plan() -> list[Act]:
    """Measure the voiceover tracks and distribute the leftover budget as tails."""
    for a in ACTS:
        p = AUDIO_DIR / a.audio
        if not p.exists():
            sys.exit(f"missing voiceover track: {p}")
        a.audio_dur = probe_duration(p)

    spoken = sum(a.audio_dur for a in ACTS)
    budget = MAX_TOTAL_SECONDS - SAFETY_MARGIN
    slack = budget - spoken
    if slack < 0:
        sys.exit(
            f"voiceover is {spoken:.1f}s, over the {budget:.1f}s planning budget by "
            f"{-slack:.1f}s — re-record or trim a track before recording video."
        )
    tail = min(MAX_TAIL_PER_ACT, slack / len(ACTS))
    for a in ACTS:
        a.tail = tail
    return ACTS


def print_plan(acts: list[Act]) -> None:
    print(f"\n  Budget {MAX_TOTAL_SECONDS:.0f}s ({mmss(MAX_TOTAL_SECONDS)})   fps {FPS}   "
          f"{VIEWPORT['width']}x{VIEWPORT['height']}\n")
    print(f"  {'':>5}  {'act':<34} {'voice':>7} {'tail':>6} {'clip':>7}")
    t = 0.0
    for a in acts:
        print(f"  {mmss(t):>5}  {a.n}. {a.label:<31} {a.audio_dur:6.1f}s {a.tail:5.2f}s {a.target:6.1f}s")
        t += a.target
    print(f"  {mmss(t):>5}  END                                          total {t:6.1f}s")
    print(f"         headroom under cap: {MAX_TOTAL_SECONDS - t:.1f}s\n")


# ----------------------------------------------------------------------------
# Browser plumbing
# ----------------------------------------------------------------------------
CURSOR_JS = """
(() => {
  const install = () => {
    if (!document.body || document.getElementById('__demo_cursor__')) return;
    const c = document.createElement('div');
    c.id = '__demo_cursor__';
    c.style.cssText = [
      'position:fixed','top:-100px','left:-100px','width:22px','height:22px',
      'border-radius:50%','background:__FILL__','border:2px solid __RING__',
      'box-shadow:0 0 0 2px rgba(255,255,255,.9),0 4px 12px rgba(0,0,0,.4)',
      'z-index:2147483647','pointer-events:none','transform:translate(-50%,-50%)',
      'transition:width .15s cubic-bezier(0.4, 0, 0.2, 1),height .15s cubic-bezier(0.4, 0, 0.2, 1),opacity .2s'
    ].join(';');
    document.documentElement.appendChild(c);
    const move = e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; };
    document.addEventListener('mousemove', move, true);
    document.addEventListener('mousedown', () => {
      c.style.width = '30px'; c.style.height = '30px';
    }, true);
    document.addEventListener('mouseup', () => {
      c.style.width = '22px'; c.style.height = '22px';
    }, true);
  };
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', install);
  else install();
  // re-install after client-side rerenders
  setInterval(install, 800);
})();
""".replace("__FILL__", CURSOR_FILL).replace("__RING__", CURSOR_RING)


class Pacer:
    """Absolute-offset pacing inside one act, so a slow page load doesn't cascade."""

    def __init__(self, act: Act):
        self.act = act
        self.t0 = time.monotonic()
        self.overruns: list[str] = []

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    async def mark(self, offset: float, note: str = "") -> None:
        delta = offset - self.elapsed
        if delta > 0:
            await asyncio.sleep(delta)
        elif delta < -0.75:
            msg = f"act{self.act.n} beat '{note or offset}' late by {-delta:.1f}s"
            self.overruns.append(msg)
            print(f"    ! {msg}")

    async def finish(self) -> None:
        await self.mark(self.act.target, "end")


async def glide(page, x: float, y: float, ms: float = 900) -> None:
    """Move the pointer along an eased path so the synthetic cursor reads as human."""
    steps = max(8, int(ms / 16))
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(ms / 1000 * 0.15)


async def first_visible(page, selectors: list[str], timeout: float = 2500):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:  # noqa: BLE001,S112 - a missing selector must never abort a take
            continue
    return None


async def glide_to(page, selectors: list[str], ms: float = 900, timeout: float = 2500):
    """Glide to the centre of the first visible match. Returns the locator or None."""
    loc = await first_visible(page, selectors, timeout)
    if loc is None:
        print(f"    · no match for {selectors[0]!r} — skipping cursor beat")
        return None
    try:
        box = await loc.bounding_box()
    except Exception:  # noqa: BLE001 - bounding_box races with re-render; skip the beat
        return None
    if not box:
        return None
    await glide(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, ms)
    return loc


async def scroll_to(page, selector: str) -> None:
    await page.evaluate(
        """(sel) => {
             const e = document.querySelector(sel);
             if (e) e.scrollIntoView({behavior:'smooth', block:'center'});
           }""",
        selector,
    )


async def wheel_scroll(page, total: int, ms: float = 1400) -> None:
    """Smooth wheel scroll, used where scrollIntoView would jump too abruptly."""
    steps = max(6, int(ms / 60))
    per = total / steps
    for _ in range(steps):
        await page.mouse.wheel(0, per)
        await asyncio.sleep(ms / 1000 / steps)


async def goto(page, url: str, wait: str = "load", timeout: float = 45000) -> None:
    try:
        await page.goto(url, wait_until=wait, timeout=timeout)
    except Exception as e:  # noqa: BLE001 - a slow prod page degrades, it does not abort
        print(f"    ! navigation to {url} degraded: {type(e).__name__}")


# ----------------------------------------------------------------------------
# Generated local pages (code view, terminal) — recordable, offline, no CDN
# ----------------------------------------------------------------------------
PAGE_CSS = """
*{box-sizing:border-box} html,body{margin:0;height:100%}
body{background:#0b1020;color:#e6edf3;font:15px/1.6 ui-monospace,'SF Mono',Menlo,monospace;
     padding:34px 44px;-webkit-font-smoothing:antialiased}
h1{font:600 15px/1 -apple-system,system-ui,sans-serif;color:#8b98a9;letter-spacing:.14em;
   text-transform:uppercase;margin:0 0 22px}
.file{background:#0f162b;border:1px solid #1e2a44;border-radius:10px;margin-bottom:22px;overflow:hidden}
.bar{background:#141d33;border-bottom:1px solid #1e2a44;padding:9px 16px;
     font:600 13px/1 -apple-system,system-ui,sans-serif;color:#9fb4d0;display:flex;gap:9px;align-items:center}
.dot{width:11px;height:11px;border-radius:50%;background:#2b3a57}
pre{margin:0;padding:16px 18px;overflow:hidden;font-size:14.5px;line-height:1.62;tab-size:4}
.ln{color:#3d4c6b;user-select:none;display:inline-block;width:3.2em;text-align:right;padding-right:1.4em}
.k{color:#ff7b9c}.s{color:#a5e075}.c{color:#5f6f8a;font-style:italic}.d{color:#7ee2d0}.n{color:#f4bf75}
.term{background:#04070f;border:1px solid #1e2a44;border-radius:10px;padding:20px 24px;font-size:16px}
.p{color:#1ebe82}.ok{color:#1ebe82;font-weight:700}.dim{color:#6b7a94}
"""

KEYWORDS = {"def", "class", "return", "if", "elif", "else", "for", "while", "import",
            "from", "raise", "try", "except", "with", "as", "not", "in", "and", "or",
            "None", "True", "False", "async", "await", "lambda", "yield", "assert"}


def highlight(line: str) -> str:
    """Deliberately small Python colouriser — enough to read as code on camera."""
    esc = html.escape(line)
    if esc.lstrip().startswith("#"):
        return f'<span class="c">{esc}</span>'
    out, buf = [], ""
    in_str, quote = False, ""
    i = 0
    while i < len(esc):
        ch = esc[i]
        if in_str:
            buf += ch
            if ch == quote:
                out.append(f'<span class="s">{buf}</span>')
                buf, in_str = "", False
            i += 1
            continue
        if ch in "\"'":
            if buf:
                out.append(_words(buf))
                buf = ""
            in_str, quote, buf = True, ch, ch
            i += 1
            continue
        buf += ch
        i += 1
    if buf:
        out.append(_words(buf) if not in_str else f'<span class="s">{buf}</span>')
    return "".join(out)


def _words(chunk: str) -> str:
    import re
    def sub(m):
        w = m.group(0)
        if w in KEYWORDS:
            return f'<span class="k">{w}</span>'
        if w.isdigit():
            return f'<span class="n">{w}</span>'
        return w
    chunk = re.sub(r"\b\w+\b", sub, chunk)
    return re.sub(r"(@\w+)", r'<span class="d">\1</span>', chunk)


def render_code_page(specs: list[tuple[Path, int, int]], out: Path, title: str) -> Path:
    blocks = []
    for path, start, end in specs:
        lines = path.read_text(encoding="utf-8").splitlines()[start - 1:end]
        body = "\n".join(
            f'<span class="ln">{start + i}</span>{highlight(l)}'
            for i, l in enumerate(lines)
        )
        rel = path.relative_to(REPO)
        blocks.append(
            f'<div class="file"><div class="bar"><span class="dot"></span>{rel}'
            f'<span style="margin-left:auto;color:#5f6f8a;font-weight:400">'
            f'lines {start}–{end}</span></div><pre>{body}</pre></div>'
        )
    out.write_text(
        f"<!doctype html><meta charset=utf-8><title>{title}</title>"
        f"<style>{PAGE_CSS}</style><h1>{title}</h1>" + "".join(blocks),
        encoding="utf-8",
    )
    return out


def render_terminal_page(cmd: str, output: str, out: Path) -> Path:
    """Render the real pytest output, with the warnings summary stripped.

    The raw tail is dominated by a DeprecationWarning block that buries the one
    line this act exists to show, so the summary is pulled out and headlined.
    """
    lines = [ln.rstrip() for ln in output.strip().splitlines()]
    summary = next((ln for ln in reversed(lines)
                    if " passed" in ln or " failed" in ln or " error" in ln), "")
    body = []
    for ln in lines:
        if not ln or ln is summary:
            continue
        if ln.lstrip().startswith(("=", "-")) or "warnings summary" in ln.lower():
            break
        body.append(ln)
    dots = "\n".join(html.escape(ln) for ln in body[:6])
    ok = "failed" not in summary and "error" not in summary
    out.write_text(
        f"<!doctype html><meta charset=utf-8><title>Hermetic test suite</title>"
        f"<style>{PAGE_CSS}"
        "body{display:grid;place-items:center;height:100vh;padding:0}"
        ".term{width:min(1500px,88vw);font-size:19px;line-height:1.75}"
        ".res{margin-top:1.1em;font-size:30px;font-weight:700}"
        "</style>"
        "<div><h1 style=\"text-align:center\">Offline hermetic test suite</h1>"
        f'<div class="term"><span class="p">agentic-marketing-suite \u276f</span> '
        f"{html.escape(cmd)}\n{dots}"
        f'<div class="res {"ok" if ok else "dim"}">{html.escape(summary)}</div></div></div>',
        encoding="utf-8",
    )
    return out


MERMAID_CDN = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"

# The README diagram is ~3:1, so fitting it whole into a 16:9 frame renders the
# node labels unreadably small. The page below gives it a camera instead: it
# renders at a legible scale and pans/zooms between named nodes on cue.
DIAGRAM_JS = """
// Geometry is measured ONCE, with the transition suppressed, into a lookup table.
// Measuring at call time races the in-flight CSS transition and pans the diagram
// clean off the stage.
window.__ready = false;
window.__nodes = {};
window.__nat = null;

window.__measure = () => {
  const cam = document.getElementById('cam');
  const svg = cam.querySelector('svg');
  if (!svg) return false;
  const prev = cam.style.transition;
  cam.style.transition = 'none';
  cam.style.transform = 'none';
  void cam.offsetWidth;                       // force synchronous reflow
  const b = svg.getBoundingClientRect();
  if (!b.width || !b.height) { cam.style.transition = prev; return false; }
  window.__nat = { w: b.width, h: b.height };
  const seen = svg.querySelectorAll('text, .nodeLabel, foreignObject div, foreignObject span');
  for (const t of seen) {
    const key = (t.textContent || '').trim();
    if (!key || key in window.__nodes) continue;
    const tb = t.getBoundingClientRect();
    if (!tb.width || !tb.height) continue;
    window.__nodes[key] = {
      cx: (tb.left + tb.width / 2 - b.left) / b.width,
      cy: (tb.top + tb.height / 2 - b.top) / b.height,
    };
  }
  cam.style.transition = prev;
  return true;
};

const apply = (cx, cy, k) => {
  const cam = document.getElementById('cam');
  const s = document.getElementById('stage').getBoundingClientRect();
  const w = window.__nat.w * k, h = window.__nat.h * k;
  cam.style.transformOrigin = '0 0';
  cam.style.transform =
    `translate(${s.width / 2 - cx * w}px, ${s.height / 2 - cy * h}px) scale(${k})`;
};

// The rendered graph is far wider than the stage, so zoom is expressed as a
// MULTIPLE of the fit-to-stage scale. An absolute scale here silently produced
// a 6x over-crop.
window.__fitScale = () => {
  const s = document.getElementById('stage').getBoundingClientRect();
  return Math.min((s.width - 60) / window.__nat.w,
                  (s.height - 60) / window.__nat.h);
};

window.focusNode = (needle, zoom) => {
  if (!window.__nat) return false;
  let hit = null;
  for (const key of Object.keys(window.__nodes)) {
    if (key.includes(needle)) { hit = window.__nodes[key]; break; }
  }
  if (!hit) return false;
  apply(hit.cx, hit.cy, window.__fitScale() * (zoom || 1));
  return true;
};

window.fitAll = () => {
  if (!window.__nat) return false;
  apply(0.5, 0.5, window.__fitScale());
  return true;
};
"""


def render_diagram_page(out: Path) -> Path:
    """Full-bleed, camera-driven re-render of the README's own Mermaid source.

    The checked-in exports/architecture_diagram.{png,svg} are stale — they predate
    the ADK 2.x graph and financial-gate nodes — so the diagram is rebuilt from
    README.md at record time and can never contradict the repo judges will open.
    """
    src = (VIDEO_DIR / "architecture.mmd").read_text(encoding="utf-8")
    out.write_text(
        "<!doctype html><meta charset=utf-8><title>System architecture</title>"
        "<style>html,body{margin:0;height:100%;background:#fbfbfa;overflow:hidden}"
        "#stage{position:fixed;inset:0;overflow:hidden}"
        "#cam{position:absolute;top:0;left:0;transition:transform 1.15s cubic-bezier(.4,0,.2,1)}"
        "#cam svg{max-width:none!important;height:auto}</style>"
        f'<div id="stage"><div id="cam"><pre class="mermaid">{html.escape(src)}</pre></div></div>'
        f'<script src="{MERMAID_CDN}"></script>'
        "<script>mermaid.initialize({startOnLoad:true,theme:'base',"
        "flowchart:{useMaxWidth:false,htmlLabels:true},"
        "themeVariables:{fontSize:'18px',fontFamily:'-apple-system,system-ui,sans-serif'}});"
        f"</script><script>{DIAGRAM_JS}</script>"
        "<script>const wait=setInterval(()=>{if(document.querySelector('#cam svg')"
        "&& window.__measure()){clearInterval(wait);window.fitAll();"
        "window.__ready=true;}},120);</script>",
        encoding="utf-8",
    )
    return out


async def open_diagram(page) -> None:
    await goto(page, render_diagram_page(PAGES / "arch.html").as_uri())
    try:
        await page.wait_for_function("() => window.__ready === true", timeout=25000)
    except Exception as e:  # noqa: BLE001 - fall through with whatever rendered
        print(f"    ! diagram render slow: {type(e).__name__}")


async def focus_node(page, needle: str | None, zoom: float = 3.4) -> None:
    """zoom is a multiple of the fit-to-stage scale, not an absolute scale."""
    ok = await page.evaluate(
        "([n, k]) => n === null ? window.fitAll() : window.focusNode(n, k)",
        [needle, zoom],
    )
    if not ok:
        print(f"    · diagram node {needle!r} not found — camera held")


# ----------------------------------------------------------------------------
# The five acts
# ----------------------------------------------------------------------------
async def act1(page, act: Act, opts) -> None:
    """0:00 — the public repo, the six-layer chain, then the architecture diagram.

    The README's Mermaid renders inside a cross-origin viewscreen iframe at ~11px
    type, which is illegible at 1080p, so the diagram beat uses a full-bleed local
    re-render of that same Mermaid source. --act1-source github stays on GitHub
    throughout and reaches the nodes through the iframe instead.
    """
    p = Pacer(act)
    on_github = opts.act1_source in ("hybrid", "github")

    if on_github:
        await goto(page, GH_REPO, wait="domcontentloaded")
        if await first_visible(page, ["article.markdown-body"], timeout=8000) is None:
            print("    ! README unreachable — falling back to the local diagram")
            on_github = False

    if not on_github:
        await open_diagram(page)

    await p.mark(4.0, "repo header")

    if on_github:
        # the badge row states the stack in type that survives YouTube compression
        for i, badge in enumerate(["img[alt*='Google ADK']", "img[alt*='Gemini']",
                                   "img[alt*='Firestore']", "img[alt*='Tests']"]):
            await glide_to(page, [badge], ms=460, timeout=900)
            await p.mark(4.0 + 7.0 * (i + 1) / 4, f"badge {i+1}")

        # the six-layer / 19-agent table — this is the "isolated silos" beat
        await scroll_to(page, "#user-content-3-the-6-layer--19-agent-value-chain, h2")
        for i, name in enumerate(["Market Intelligence", "Strategic Synthesis",
                                  "Content Planning", "Creative Factory",
                                  "Distribution & Ops", "Analytics & Feedback"]):
            loc = await glide_to(page, [f"text=/Layer {i+1}: {name}/"], ms=430, timeout=900)
            if loc is not None and i in (0, 5):
                await loc.scroll_into_view_if_needed()
            await p.mark(11.0 + 15.0 * (i + 1) / 6, f"layer {i+1}")

        # hand off to the legible diagram for the stack beats
        await open_diagram(page)

    await focus_node(page, None)                       # establishing overview
    await p.mark(27.0, "diagram framed")

    # the stack, in the order the voiceover names it — the camera does the work,
    # so the labels stay legible after YouTube's compression
    for i, node in enumerate(["ADK 2.x Graph Workflow",
                              "Gemini 3.7 Flash",
                              "Vertex AI Reasoning Engine",
                              "Firestore Native"]):
        await focus_node(page, node, 3.4)
        await p.mark(27.0 + 11.0 * (i + 1) / 4, f"stack node {i+1}")

    # rest on the sacred gate and hold dead still into the cut
    await focus_node(page, "Human Financial Authorization Gate", 3.6)
    await p.finish()


async def act2(page, act: Act, opts) -> None:
    """0:45 — onboarding wizard, then the live session view.

    The file lane has no submit of its own: handleFileSelect() parses the JSON
    into #id_inputs and mirrors it into the visual wizard, and the run is started
    from the JSON lane. Targeting a submit inside #mode-file (as this originally
    did) matches nothing and burns the act's timing budget on lookup timeouts.
    """
    p = Pacer(act)
    await goto(page, f"{BASE}/corridas/nueva/")
    await p.mark(3.0, "wizard loaded")

    # file lane → attach the pre-compiled fixture
    tab = await glide_to(page, ["button.wizard-tab:has-text('Cargar Archivo')"], ms=700)
    if tab is not None:
        await tab.click()
    await p.mark(6.0, "file lane open")

    fixture = REPO / "suite" / "inputs" / "acme_global.json"
    try:
        await page.locator("#fileInput").set_input_files(str(fixture))
        print(f"    · injected {fixture.name}")
    except Exception as e:  # noqa: BLE001
        print(f"    ! could not attach fixture: {type(e).__name__}")
    # syncJsonToFields() switches straight back to the wizard lane, which hides
    # #mode-file and its confirmation chip — so the populated wizard IS the
    # confirmation, and it reads better than the chip would have.
    await glide_to(page, ["#wiz_company_name"], ms=700, timeout=4000)
    await p.mark(11.0, "company name populated")
    await glide_to(page, ["#wiz_client_id"], ms=600, timeout=1500)
    await p.mark(14.0, "client slug populated")

    # JSON lane holds the real start button
    jtab = await glide_to(page, ["button.wizard-tab:has-text('Editor JSON')"], ms=600)
    if jtab is not None:
        await jtab.click()
    await p.mark(17.0, "payload shown")

    start = await glide_to(page, ["#mode-json button[type=submit]"], ms=800, timeout=2500)
    await p.mark(19.5, "on start button")
    if opts.commit and start is not None:
        await start.click()
        await page.wait_for_load_state("load", timeout=90000)
        print("    · pipeline start CLICKED (--commit)")
    else:
        print("    · start button hovered only (dry mode)")
    await p.mark(21.5, "post-start")

    # the session view: 19 agents across 6 layers. After a --commit start the
    # console has already redirected to the run it just created; jumping to a
    # pre-seeded id here would film the wrong session.
    started_here = "/corridas/run-" in page.url
    session = opts.session_id or SESSION_ID
    if session and not started_here and f"/corridas/{session}" not in page.url:
        await goto(page, f"{BASE}/corridas/{session}/")
    if started_here:
        print(f"    · staying on the run just started: {page.url.rstrip('/').rsplit('/', 1)[-1]}")
    await p.mark(24.5, "session view")

    # #live-indicator and .progress-fill only render while status == "en curso";
    # on a paused run neither exists, so key off whichever banner is present.
    for sel in ["#live-indicator", ".progress-fill", ".run-banner"]:
        if await page.locator(sel).count():
            await glide_to(page, [sel], ms=650, timeout=1200)
            break
    await p.mark(27.0, "run state")

    cards = page.locator(".layer-card")
    n = min(await cards.count(), 3)
    tail_start, tail_end = 27.0, act.target - 2.0
    for i in range(n):
        await cards.nth(i).scroll_into_view_if_needed()
        await p.mark(tail_start + (tail_end - tail_start) * (i + 1) / max(n, 1), f"layer card {i+1}")
    await p.finish()


async def act3(page, act: Act, opts) -> None:
    """1:21 — the emerald #1ebe82 binding gate, in-place editing, approval.

    The strategy card renders one .card-box (the growth thesis) and no
    .segment-grid — audience segments live in a different block — so the beats
    key off the gate chip, the 2.1 agent header and the thesis itself.
    """
    p = Pacer(act)
    session = opts.session_id or SESSION_ID
    if session:
        await goto(page, f"{BASE}/corridas/{session}/")
    await scroll_to(page, ".run-banner")
    await p.mark(3.0, "pause banner")

    # the paused banner — the "zero blind spend" beat
    await glide_to(page, [".run-banner.pausa"], ms=900, timeout=2500)
    await p.mark(9.0, "banner dwell")

    await goto(page, f"{BASE}/clientes/{CLIENT_ID}/bloques/{BLOCK}/"
                     + (f"?volver={session}" if session else ""))
    await p.mark(12.5, "deliverable card")

    # gate state, then which agent produced it
    await glide_to(page, [".chip:has-text('Compuerta')", ".chip"], ms=650, timeout=2000)
    await p.mark(16.0, "gate chip")
    await glide_to(page, ["text=/Orquestador de Estrategia/", "text=/Agente 2.1/"],
                   ms=650, timeout=2000)
    await p.mark(19.0, "agent 2.1 header")

    # the growth thesis — visual card, not raw JSON
    await scroll_to(page, ".card-box")
    await glide_to(page, [".card-title", ".card-box"], ms=700, timeout=2000)
    await p.mark(24.0, "growth thesis")

    # in-place editing
    edit = await glide_to(page, ["button[onclick*='toggleEditSection']"], ms=750)
    if edit is not None:
        await edit.click()
        await p.mark(27.0, "editor open")
        nota = page.locator("#edit_nota")
        if await nota.count():
            await nota.scroll_into_view_if_needed()
            await nota.click()
            await nota.type("Meta de ROI ajustada por el operador", delay=45)
    await p.mark(31.5, "edit typed")

    if opts.commit:
        save = await glide_to(page, ["button[name=action][value=save]"], ms=650)
        if save is not None:
            await save.click()
            await page.wait_for_load_state("load", timeout=45000)
            print("    · block edit SAVED (--commit)")
            # the save redirect drops ?volver=, so the approve that follows would
            # bounce to the dashboard (which lists every client) instead of back
            # to the run. Re-attach it so the act ends on the resuming session.
            if session:
                await goto(page, f"{BASE}/clientes/{CLIENT_ID}/bloques/{BLOCK}/"
                                 f"?volver={session}")
    await p.mark(35.0, "saved")

    # the sacred gate itself
    if await page.locator("#edit-section").count():
        await page.evaluate(
            "() => { const e = document.getElementById('edit-section');"
            " if (e) e.style.display = 'none'; }"
        )
    approve = await glide_to(page, ["button[name=decision][value=approved]",
                                    ".btn-aprobar"], ms=900, timeout=3000)
    await p.mark(37.5, "on approve button")
    if opts.commit and approve is not None:
        await approve.click()
        await page.wait_for_load_state("load", timeout=45000)
        print("    · gate APPROVED (--commit) — orchestrator resumes downstream")
    else:
        print("    · approve button hovered only (dry mode)")
    await p.finish()


async def act4(page, act: Act, opts) -> None:
    """2:04 — the 9-act deck, then the FastMCP gate + Model Armor source."""
    p = Pacer(act)
    await goto(page, f"{BASE}/propuestas/{CLIENT_ID}/deck/")
    await p.mark(3.5, "deck loaded")

    # flip through the nine acts, weighted so the metric slides breathe
    deck_end = act.target * 0.62
    span = deck_end - 3.5
    for i in range(9):
        await scroll_to(page, f"#acto-{i}")
        await p.mark(3.5 + span * (i + 1) / 9, f"acto-{i}")

    armor = REPO / "suite" / "security" / "model_armor.py"
    gate = REPO / "suite" / "distribution" / "financial_gate.py"
    page_path = render_code_page(
        [(gate, 1, 34), (armor, 1, 30)],
        PAGES / "code.html",
        "FastMCP gateway · financial authorisation + Model Armor",
    )
    await goto(page, page_path.as_uri())
    await p.mark(deck_end + 4.0, "code view")
    await wheel_scroll(page, 320, 1200)
    await p.finish()


def _run_suite() -> str:
    out = subprocess.run(
        ["uv", "run", "--all-extras", "pytest", "-q"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    return out.stdout or out.stderr


async def act5(page, act: Act, opts) -> None:
    """2:45 — Cloud Run, Firestore, and the hermetic test suite."""
    p = Pacer(act)
    # Kick the suite off now and let it run against the Cloud Console beats;
    # running it inline would block the event loop and wreck the act's pacing.
    suite = asyncio.create_task(asyncio.to_thread(_run_suite))
    await goto(page,
               f"https://console.cloud.google.com/run?project={GCP_PROJECT}",
               wait="domcontentloaded", timeout=60000)
    await p.mark(9.0, "cloud run dashboard")
    await glide_to(page, ["text=/console/", "text=/us-central1/"], ms=800, timeout=2500)
    await p.mark(14.0, "service row")

    await goto(page,
               "https://console.cloud.google.com/firestore/databases/-default-/data/panel/"
               f"clients/{CLIENT_ID}/blocks?project={GCP_PROJECT}",
               wait="domcontentloaded", timeout=60000)
    await p.mark(24.0, "firestore studio")
    await glide_to(page, ["text=/active_strategy/", f"text=/{CLIENT_ID}/",
                          "text=/clients/"], ms=800, timeout=3000)
    await p.mark(28.0, "collections")

    report = await suite
    term = render_terminal_page("uv run --all-extras pytest -q", report, PAGES / "term.html")
    summary = (report.strip().splitlines() or ["<no output>"])[-1]
    print(f"    · test suite: {summary}")
    await goto(page, term.as_uri())
    await p.finish()


ACT_FNS = {1: act1, 2: act2, 3: act3, 4: act4, 5: act5}


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
async def scrape_panel(page) -> list[dict]:
    """Read the console dashboard: every run, its client, and whether it is paused."""
    await goto(page, f"{BASE}/")
    if "accounts.google.com" in page.url:
        return []
    await first_visible(page, ["table", "tbody tr"], timeout=8000)
    return await page.evaluate(
        r"""() => [...document.querySelectorAll('tbody tr')].map(tr => {
             const a = tr.querySelector("a[href*='/corridas/']");
             if (!a) return null;
             const chip = tr.querySelector('.chip.pausa');
             const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
             return {
               id: a.textContent.trim(),
               href: a.getAttribute('href'),
               paused: !!chip,
               pending: chip ? chip.innerText.replace(/^en pausa ·\s*/, '').trim() : '',
               cells,
             };
           }).filter(Boolean)"""
    )


async def discover_session(page, wanted_client: str) -> str:
    """Pick the run acts 2-3 should film: newest paused run for the demo client."""
    rows = await scrape_panel(page)
    if not rows:
        return ""
    paused = [r for r in rows if r["paused"]]
    for pool in (paused, rows):
        for r in pool:
            if any(wanted_client in c for c in r["cells"]):
                return r["id"]
    return paused[0]["id"] if paused else ""


async def cmd_probe(opts) -> None:
    from playwright.async_api import async_playwright

    if not PROFILE.exists():
        sys.exit("no browser profile — run `record_demo.py login` first")
    async with async_playwright() as pw:
        ctx = await launch(pw, None, headless=not opts.headed)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        rows = await scrape_panel(page)
        if not rows:
            print("\n  ✗ console not reachable — the IAP session has expired.")
            print("    Re-run `record_demo.py login` (sign in as js@qhhe.net).\n")
            await ctx.close()
            return
        print(f"\n  {len(rows)} run(s) on {BASE}\n")
        for r in rows:
            flag = "PAUSED" if r["paused"] else "      "
            print(f"    {flag}  {r['id']:<28} {' · '.join(r['cells'][1:4])}")
            if r["pending"]:
                print(f"            pending: {r['pending']}")
        sid = await discover_session(page, CLIENT_ID)
        print(f"\n  acts 2-3 would film: {sid or '(none found)'}")

        # does the deliverable card acts 3 needs actually exist?
        await goto(page, f"{BASE}/clientes/{CLIENT_ID}/bloques/{BLOCK}/")
        ok = await first_visible(page, [".card-box", ".context-banner"], timeout=6000)
        print(f"  {CLIENT_ID}/{BLOCK} deliverable card: "
              f"{'present' if ok else 'MISSING — re-seed with prepare_demo_data.py'}")

        # and the compiled deck act 4 needs?
        await goto(page, f"{BASE}/propuestas/{CLIENT_ID}/deck/")
        acts = await page.locator("section.act").count()
        print(f"  {CLIENT_ID} presentation deck: {acts} acts"
              f"{'' if acts else '  — MISSING'}\n")
        await ctx.close()


async def launch(pw, record_dir: Path | None, headless: bool):
    """Persistent context on real Chrome where available.

    Google's sign-in refuses OAuth from browsers it fingerprints as automated
    ("this browser or app may not be secure"), which bundled Chromium plus the
    default --enable-automation switch reliably trips. Using the installed Chrome
    channel and dropping the automation flags gets the one interactive login
    through; recording afterwards is unaffected either way.
    """
    args = [
        f"--window-size={VIEWPORT['width']},{VIEWPORT['height']}",
        "--force-device-scale-factor=1",
        "--disable-blink-features=AutomationControlled",
        "--hide-crash-restore-bubble",
        "--disable-features=Translate,MediaRouter",
        "--no-default-browser-check",
        "--no-first-run",
    ]
    kw = {
        "user_data_dir": str(PROFILE),
        "headless": headless,
        "viewport": VIEWPORT,
        "screen": VIEWPORT,
        "device_scale_factor": 1,
        "record_video_dir": str(record_dir) if record_dir else None,
        "record_video_size": VIEWPORT if record_dir else None,
        "args": args,
        "ignore_default_args": ["--enable-automation"],
    }
    if CHROME_APP.exists():
        kw["channel"] = "chrome"
    try:
        ctx = await pw.chromium.launch_persistent_context(**kw)
    except Exception as e:  # noqa: BLE001 - fall back to bundled Chromium
        print(f"    ! Chrome channel unavailable ({type(e).__name__}); using Chromium")
        kw.pop("channel", None)
        ctx = await pw.chromium.launch_persistent_context(**kw)
    await ctx.add_init_script(CURSOR_JS)
    return ctx


async def cmd_login(opts) -> None:
    from playwright.async_api import async_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    print("\n  Opening a browser on the persistent profile.")
    print("  Sign in as js@qhhe.net — it is the ONLY account with both IAP access")
    print("  and prod project access; jaimevelarca@gmail.com has no role on prod,")
    print("  so act 5's Cloud Console tabs would render permission-denied.")
    print("\n    1) the console at the IAP prompt")
    print("    2) console.cloud.google.com (same window, new tab)")
    print("\n  Then come back here and press Enter.\n")
    async with async_playwright() as pw:
        ctx = await launch(pw, None, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await goto(page, BASE, wait="domcontentloaded")
        await asyncio.to_thread(input, "  [Enter] when signed in \u25b8 ")
        await ctx.close()
    print(f"  Profile saved to {PROFILE}\n")


async def cmd_record(opts) -> None:
    from playwright.async_api import async_playwright

    acts = plan()
    print_plan(acts)
    if not PROFILE.exists():
        sys.exit("no browser profile — run `record_demo.py login` first")

    selected = opts.acts or [a.n for a in acts]
    CLIPS.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)

    mode = "COMMIT (clicks will mutate prod state)" if opts.commit else "dry (no state mutated)"
    print(f"  mode: {mode}\n")

    if not opts.session_id and any(n in selected for n in (2, 3)):
        async with async_playwright() as pw:
            ctx = await launch(pw, None, headless=not opts.headed)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            opts.session_id = await discover_session(page, CLIENT_ID)
            await ctx.close()
        print(f"  session for acts 2-3: {opts.session_id or 'NONE FOUND — pass --session-id'}\n")

    async with async_playwright() as pw:
        for a in acts:
            if a.n not in selected:
                continue
            stage = CLIPS / f"_raw_act{a.n}"
            if stage.exists():
                shutil.rmtree(stage)
            stage.mkdir(parents=True)

            print(f"  ▸ act {a.n} — {a.label}  (target {a.target:.1f}s)")
            ctx = await launch(pw, stage, headless=not opts.headed)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            t0 = time.monotonic()
            try:
                await ACT_FNS[a.n](page, a, opts)
            except Exception as e:  # noqa: BLE001 - keep whatever footage the act produced
                print(f"    ! act {a.n} raised {type(e).__name__}: {e}")
            finally:
                await ctx.close()   # video is flushed on context close

            produced = sorted(stage.glob("*.webm"))
            if not produced:
                print(f"    ! no video written for act {a.n}")
                continue
            if a.clip.exists():
                a.clip.unlink()
            produced[0].rename(a.clip)
            shutil.rmtree(stage, ignore_errors=True)
            print(f"    ✓ {a.clip.name}  ({time.monotonic() - t0:.1f}s wall)\n")

    print("  Next:  record_demo.py assemble\n")


def cmd_assemble(opts) -> None:
    acts = plan()
    print_plan(acts)
    missing = [a.n for a in acts if not a.clip.exists()]
    if missing:
        sys.exit(f"missing clips for act(s) {missing} — record them first")

    parts = []
    for a in acts:
        have = probe_duration(a.clip)
        pad = max(0.0, a.target - have) + 0.5
        print(f"  ▸ act {a.n}: clip {have:.1f}s → target {a.target:.1f}s "
              f"({'holding last frame' if have < a.target else 'trimming'})")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(a.clip),
            "-i", str(AUDIO_DIR / a.audio),
            "-filter_complex",
            (
                f"[0:v]fps={FPS},scale={VIEWPORT['width']}:{VIEWPORT['height']}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={VIEWPORT['width']}:{VIEWPORT['height']}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,tpad=stop_mode=clone:stop_duration={pad:.2f}[v]"
            ),
            "-map", "[v]", "-map", "1:a",
            "-t", f"{a.target:.3f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(a.muxed),
        ], check=True)
        parts.append(a.muxed)

    manifest = BUILD / "concat.txt"
    manifest.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    srt_file = VIDEO_DIR / "subtitles_en.srt"
    
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(manifest),
    ]
    if srt_file.exists():
        cmd.extend([
            "-i", str(srt_file),
            "-c:v", "copy", "-c:a", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-metadata:s:s:0", "title=English (CC)",
            "-disposition:s:0", "default",
        ])
    else:
        cmd.extend(["-c", "copy"])
    cmd.extend(["-movflags", "+faststart", str(MASTER)])
    subprocess.run(cmd, check=True)

    final = probe_duration(MASTER)
    print(f"\n  master: {MASTER}")
    print(f"  length: {final:.2f}s ({mmss(final)})   cap {MAX_TOTAL_SECONDS:.0f}s "
          f"({mmss(MAX_TOTAL_SECONDS)})")
    if final > MAX_TOTAL_SECONDS:
        sys.exit(f"  ✗ OVER CAP by {final - MAX_TOTAL_SECONDS:.2f}s")
    print(f"  ✓ under cap by {MAX_TOTAL_SECONDS - final:.2f}s\n")

    t = 0.0
    print("  YouTube timestamps:")
    for a, name in zip(acts, [
        "Introduction & 19-Agent Architecture",
        "Google Cloud Run Console & Asynchronous Execution",
        "The Sacred #1ebe82 Human Gate & In-Place Editing",
        "Multimodal Creative, 9-Act Decks & FastMCP",
        "Google Cloud Backend Proof & Serverless Economics",
    ]):
        print(f"    {mmss(t)} - {name}")
        t += a.target
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="print the timeline derived from the voiceover tracks")
    sub.add_parser("login", help="sign in once; persists the Chrome profile")

    r = sub.add_parser("record", help="record one clip per act")
    r.add_argument("--acts", type=lambda s: [int(x) for x in s.split(",")],
                   help="subset, e.g. --acts 2,3")
    r.add_argument("--commit", action="store_true",
                   help="actually click start / save / approve (mutates prod state)")
    r.add_argument("--headed", action="store_true", help="show the browser window")
    r.add_argument("--session-id", default="", help="pre-seeded session id for acts 2-3")
    r.add_argument("--act1-source", choices=["hybrid", "github", "local"], default="hybrid")

    pr = sub.add_parser("probe", help="report what demo data the live console holds")
    pr.add_argument("--headed", action="store_true")

    sub.add_parser("assemble", help="mux clips against voiceover and concatenate")

    opts = ap.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)

    if opts.cmd == "plan":
        print_plan(plan())
    elif opts.cmd == "login":
        asyncio.run(cmd_login(opts))
    elif opts.cmd == "record":
        asyncio.run(cmd_record(opts))
    elif opts.cmd == "probe":
        asyncio.run(cmd_probe(opts))
    elif opts.cmd == "assemble":
        cmd_assemble(opts)


if __name__ == "__main__":
    main()
