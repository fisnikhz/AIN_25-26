#!/usr/bin/env python3
"""
Test i shpejtë për crash fix.
"""

import subprocess
import sys
import time

def test_australia():
    """Test me Australia instance."""
    print("=== Test Hill Climbing me Australia ===")
    
    start_time = time.time()
    result = subprocess.run([
        sys.executable, 
        "run_hill_climbing_restarts.py", 
        "data/input/australia_iptv.json"
    ], capture_output=True, text=True, timeout=120)  # 2 minuta timeout
    
    elapsed = time.time() - start_time
    
    if result.returncode == 0:
        print(f"✅ SUCCESS! Completed në {elapsed:.1f}s")
        # Extract score nga output
        for line in result.stdout.split('\n'):
            if 'Fitness finale:' in line:
                print(f"Final Score: {line}")
                break
        return True
    else:
        print(f"❌ CRASH! Return code: {result.returncode}")
        print("STDERR:", result.stderr[-500:] if result.stderr else "No stderr")
        return False

if __name__ == "__main__":
    test_australia()