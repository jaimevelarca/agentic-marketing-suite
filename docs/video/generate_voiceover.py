#!/usr/bin/env python3
"""
Generate high-fidelity voiceover tracks for the All Things Agentic video demo
using macOS native speech synthesis ('say') and 'afconvert' to AAC / m4a.
"""
import subprocess
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "Samantha"  # Standard high-quality en_US voice installed on macOS

ACTS = {
    "act1_intro": (
        "Welcome to the Agentic Marketing Suite, an institutional fleet of 19 autonomous AI agents built on Google Cloud "
        "for the All Things Agentic Hackathon, competing in the Fortified Enterprise Fleet category. "
        "Digital marketing today is fragmented across isolated silos: market research, 90-day strategy, 4-week content calendars, "
        "multimodal copy, visual assets, and paid media distribution. Rather than a simple conversational chatbot, "
        "we built an asynchronous enterprise fleet. It is orchestrated via Google ADK 2.x Graph Workflows, powered by Gemini 3.7 Flash "
        "and Vertex AI, persisted in Firestore Native, and strictly governed by sacred emerald Human Financial Gates."
    ),
    "act2_onboarding": (
        "Here is our review console running live on Google Cloud Run behind Direct Identity-Aware Proxy. "
        "An enterprise operator onboards a client through our structured wizard. "
        "Behind the scenes, a Cloud Run Job triggers our ADK 2.x graph workflow. Layer 1 executes Business Diagnostics, "
        "Audience Intelligence, and Competitive Radar, extracting brand unique selling propositions and Ideal Customer Profiles. "
        "Notice that each agent's output is a strictly typed memory block, streamed directly to Firestore Native. "
        "The system runs asynchronously without blocking active user sessions."
    ),
    "act3_human_gate": (
        "Now, witness our sacred emerald Human Gate in action. True enterprise automation requires zero blind spend. "
        "When the Strategy Orchestrator finishes, the ADK 2.x workflow raises a native RequestInput interrupt, "
        "cleanly suspending execution without burning idle compute. In the review console, operators review visual "
        "deliverable cards rather than raw JSON. I can inspect audience segments, edit strategic copy in-place, and click the "
        "emerald approval button. Instantly, the gate updates in Firestore, and our ADK orchestrator automatically resumes "
        "downstream execution, recalculating all subsequent production layers with the human-approved adjustments."
    ),
    "act4_creative_production": (
        "Downstream, Layer 4 Production generates copy assets, visual creative specs via Gemini 3.1 Flash Image, "
        "landing pages, and email nurture flows. With one click, the suite compiles this interactive 9-act HTML presentation deck "
        "and executive report directly from Firestore memory. For external distribution, our FastMCP gateway connects to "
        "Meta Ads and Resend Email. It is guarded by our Human Financial Authorization Gate, which rejects any API call "
        "exceeding confirmed client budget ceilings, and Model Armor powered by Google Gemma, which intercepts prompt "
        "injections and redacts sensitive PII before execution."
    ),
    "act5_cloud_proof": (
        "Everything you see is deployed on Google Cloud via Pulumi Infrastructure as Code. "
        "Here is our Cloud Run service with request-based billing: when idle, it scales to zero for zero dollar compute spend. "
        "Here is our Firestore Native Memory Bank maintaining multi-week state across sessions, and Vertex AI logs running "
        "Gemini 3.7 Flash. Finally, our offline hermetic test suite runs 335 unit tests in under 5 seconds, guaranteeing "
        "100% reliability. Agentic Marketing Suite proves that autonomous, multi-agent enterprise fleets are here today "
        "on Google Cloud. Thank you!"
    ),
}

def main():
    print(f"🎙️ Generating voiceover audio files in: {AUDIO_DIR}")
    for act_id, text in ACTS.items():
        aiff_path = AUDIO_DIR / f"{act_id}.aiff"
        m4a_path = AUDIO_DIR / f"{act_id}.m4a"
        
        print(f"Generating {act_id}...")
        # 1. Generate AIFF using macOS say
        subprocess.run(["say", "-v", VOICE, "-r", "175", text, "-o", str(aiff_path)], check=True)
        
        # 2. Convert to AAC m4a
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff_path), str(m4a_path)], check=True)
        aiff_path.unlink(missing_ok=True)
        print(f"  ✅ Saved: {m4a_path.name} ({m4a_path.stat().st_size // 1024} KB)")

    print("\n🎉 All 5 voiceover tracks generated successfully!")

if __name__ == "__main__":
    main()
