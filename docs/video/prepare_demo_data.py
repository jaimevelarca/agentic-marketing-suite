#!/usr/bin/env python3
"""
Pre-populate full 19-agent demo data for Acme Global Technologies Inc.
and compile the interactive 9-act presentation deck and detail report.
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "suite"))

from orchestration.pipeline import run_pipeline
from infra import clients
from rendering import compile_proposal

def main():
    print("🚀 Pre-populating demo data for Acme Global Technologies Inc. ...")
    input_path = REPO_ROOT / "suite" / "inputs" / "acme_global.json"
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    
    client_id = "acme-global"
    
    # 1. Execute 19-agent pipeline hermetically
    res = run_pipeline(client_id=client_id, inputs=payload, auto_approve=True)
    print(f"  ✅ Executed 19 agents: {len(res['transcript'])} steps produced {len(res['memory'])} memory blocks.")
    
    # 2. Persist blocks into storage
    for block_name, block_data in res["memory"].items():
        clients.write_memory_block(client_id, block_name, block_data, gate_status="approved")
        
    print("  ✅ Persisted 20 memory blocks into storage.")
    
    # 3. Compile interactive 9-Act HTML presentation deck & detail report
    exports_dir = REPO_ROOT / "exports" / "proposals" / client_id
    exports_dir.mkdir(parents=True, exist_ok=True)
    
    prop = compile_proposal(client_id=client_id, out_dir=exports_dir)
    print("\n🎉 Proposal Assets Compiled:")
    print(f"  📊 Presentation Deck: file://{prop['presentation_path']}")
    print(f"  📑 Detail Dossier:    file://{prop['detail_path']}")
    print("\nReady for video recording!")

if __name__ == "__main__":
    main()
