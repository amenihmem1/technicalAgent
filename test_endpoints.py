#!/usr/bin/env python
import sys
import traceback

sys.path.insert(0, 'c:\\Users\\ameni\\Desktop\\Stage\\technique-agent\\backend')

try:
    from orchestrator.session_store import JsonSessionStore
    from api_server import _build_candidate_history_groups
    
    print("[1/3] Initializing session store...")
    store = JsonSessionStore()
    
    print("[2/3] Loading payloads...")
    payloads = store.list_payloads(limit=80)
    print(f"  -> Loaded {len(payloads)} payloads")
    
    print("[3/3] Building candidate history groups...")
    result = _build_candidate_history_groups(payloads)
    print(f"  -> Success! Got {len(result.get('sessions', []))} sessions")
    print(f"  -> Got {len(result.get('candidates', []))} candidate groups")
    
    print("\nAll tests passed!")
    
except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
