"""Run-once script to send the guide announcement webhook from within the app."""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from combined import post_guide_webhook

print("Sending guide announcement webhook...")
result = post_guide_webhook()
if result:
    print("[OK] Guide announcement sent successfully!")
else:
    print("[FAIL] Check that CLAIMS_WEBHOOK has a valid token in combined.py (line ~111).")
    sys.exit(1)
