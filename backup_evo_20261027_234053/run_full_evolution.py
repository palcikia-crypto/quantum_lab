#!/usr/bin/env python3
"""run_full_evolution.py — полный цикл: feedback → auto_add → feedback."""
import sys; sys.path.insert(0, 'core')
from live_feedback import run_feedback
from auto_add import run_auto_add

def main():
    print('=== FULL EVOLUTION CYCLE ===')
    print('\n--- 1. FEEDBACK ---'); run_feedback()
    print('\n--- 2. AUTO-ADD ---'); run_auto_add()
    print('\n--- 3. FEEDBACK ---'); run_feedback()
    print('\n✅ FULL CYCLE DONE')

if __name__ == '__main__': main()
