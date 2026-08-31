#!/usr/bin/env python3
"""
Generate high-quality English (en_US) voiceover audio tracks for Agentic Marketing Suite demo video.
Uses macOS Samantha voice for clean, professional English narration matching the hackathon script.
"""
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIO_DIR = REPO / "docs" / "video" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS = {
    "act1_intro.m4a": (
        "Welcome to the Agentic Marketing Suite, an institutional fleet of nineteen autonomous AI agents built on Google Cloud "
        "for the All Things Agentic Hackathon. Digital marketing today is fragmented across isolated silos: market research, strategy, "
        "content calendars, and multimodal creative production. Rather than a simple chatbot, we built an asynchronous enterprise fleet "
        "orchestrated via Google ADK 2.x Graph Workflows, powered by Gemini 3.7 Flash and Vertex AI, and strictly governed by sacred "#1ebe82" Human Financial Gates."
    ),
    "act2_onboarding.m4a": (
        "Here is our review console running live on Google Cloud Run behind Direct Identity-Aware Proxy. "
        "An enterprise operator onboards a client through our structured wizard. Behind the scenes, a Cloud Run Job triggers our ADK 2.x graph workflow. "
        "Layer 1 executes Business Diagnostics, Audience Intelligence, and Competitive Radar, extracting brand USPs and Ideal Customer Profiles. "
        "Each agent output is a strictly typed memory block, streamed directly to Firestore Native without blocking active user sessions."
    ),
    "act3_human_gate.m4a": (
        "Now, witness our sacred #1ebe82 Human Gate in action. True enterprise automation requires zero blind spend. "
        "When the Strategy Orchestrator finishes, the ADK 2.x workflow raises a native interrupt, cleanly suspending execution without burning idle compute. "
        "In the review console, operators review visual deliverable cards rather than raw JSON. I can inspect audience segments, edit strategic copy in-place, "
        "and click the emerald "#1ebe82" approval button. Instantly, Firestore updates and downstream execution automatically resumes."
    ),
    "act4_creative_production.m4a": (
        "Downstream, Layer 4 Production generates copy assets, visual creative specs via Gemini Flash Image, landing pages, and email nurture flows. "
        "With one click, the suite compiles this interactive nine-act presentation deck and executive report directly from Firestore memory. "
        "For external distribution, our FastMCP gateway connects to Meta Ads and Resend, guarded by our Human Financial Authorization Gate "
        "and Model Armor powered by Google Gemma, which intercepts prompt injections and redacts sensitive PII."
    ),
    "act5_cloud_proof.m4a": (
        "Everything you see is deployed on Google Cloud via Pulumi IaC. Here is our Cloud Run service with request-based billing: when idle, it scales to zero for zero dollar compute spend. "
        "Here is our Firestore Native Memory Bank maintaining multi-week state across sessions, and Vertex AI logs running Gemini 3.7 Flash. "
        "Finally, our offline hermetic test suite runs three hundred thirty-five unit tests in under five seconds, guaranteeing one hundred percent reliability. "
        "Agentic Marketing Suite proves that autonomous multi-agent enterprise fleets are here today on Google Cloud. Thank you!"
    ),
}

def generate():
    for filename, text in SCRIPTS.items():
        out_path = AUDIO_DIR / filename
        txt_path = AUDIO_DIR / f"{filename}.txt"
        txt_path.write_text(text, encoding="utf-8")
        
        print(f"Generating {filename} (English - Samantha)...")
        subprocess.run(
            ["say", "-v", "Samantha", "-f", str(txt_path), "-o", str(out_path), "--data-format=aac"],
            check=True
        )
        txt_path.unlink()
        
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out_path)],
            capture_output=True, text=True, check=True
        )
        print(f"  -> {filename}: {float(probe.stdout.strip()):.2f}s")

if __name__ == "__main__":
    generate()
