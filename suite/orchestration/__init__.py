"""Orchestration for the Digital Marketing AI Suite.

`pipeline.py` defines the 6-layer / 19-agent DAG and runs it (offline or on
Vertex). `demo.py` is the offline end-to-end runner. `job_entrypoint.py` is the
Cloud Run Job entry that runs one agent (or the whole pipeline) in production.
"""
