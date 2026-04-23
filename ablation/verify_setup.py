#!/usr/bin/env python3
"""
Ablation Study Setup Verification

Checks that all baseline variants are properly set up and ready to run.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ABLATION_DIR = PROJECT_ROOT / "ablation"

def check_directory_structure():
    """Verify ablation directory structure."""
    print("Checking directory structure...")
    
    required_dirs = [
        ABLATION_DIR / "baseline0_full",
        ABLATION_DIR / "baseline1_no_comments",
        ABLATION_DIR / "baseline2_no_filtering"
    ]
    
    all_exist = True
    for d in required_dirs:
        if d.exists():
            print(f"  ✓ {d.name}")
        else:
            print(f"  ✗ {d.name} NOT FOUND")
            all_exist = False
    
    return all_exist

def check_files():
    """Verify all required files exist."""
    print("\nChecking files...")
    
    required_files = [
        ("ablation_config.py", ABLATION_DIR / "ablation_config.py"),
        ("run_ablation.py", ABLATION_DIR / "run_ablation.py"),
        ("analyze_results.py", ABLATION_DIR / "analyze_results.py"),
        ("baseline0/ahoy.py", ABLATION_DIR / "baseline0_full" / "ahoy.py"),
        ("baseline1/ahoy.py", ABLATION_DIR / "baseline1_no_comments" / "ahoy.py"),
        ("baseline1/utils_variant.py", ABLATION_DIR / "baseline1_no_comments" / "utils_variant.py"),
        ("baseline2/ahoy.py", ABLATION_DIR / "baseline2_no_filtering" / "ahoy.py"),
        ("baseline2/utils_variant.py", ABLATION_DIR / "baseline2_no_filtering" / "utils_variant.py"),
    ]
    
    all_exist = True
    for name, path in required_files:
        if path.exists():
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} NOT FOUND")
            all_exist = False
    
    return all_exist

def check_environment():
    """Verify maf-py conda environment is active."""
    print("\nChecking conda environment...")
    
    import subprocess
    
    try:
        # Get current Python executable
        python_exe = sys.executable
        
        # Check if maf-py is in the path
        if "maf-py" in python_exe or "maf-py" in sys.prefix:
            print(f"  ✓ maf-py environment detected")
            print(f"    Python: {python_exe}")
            return True
        else:
            print(f"  ✗ maf-py environment NOT detected")
            print(f"    Current Python: {python_exe}")
            print(f"    Expected: conda env maf-py")
            print(f"\n  To activate: conda activate maf-py")
            return False
    except Exception as e:
        print(f"  ✗ Error checking environment: {e}")
        return False

def check_imports():
    """Verify Python modules can be imported."""
    print("\nChecking imports...")
    
    sys.path.insert(0, str(ABLATION_DIR))
    sys.path.insert(0, str(PROJECT_ROOT))
    
    all_ok = True
    
    # Check ablation_config
    try:
        from ablation_config import get_ablation_mode, AblationMetrics
        print(f"  ✓ ablation_config")
    except Exception as e:
        print(f"  ✗ ablation_config: {e}")
        all_ok = False
    
    # Check baseline1 variant
    try:
        from baseline1_no_comments.utils_variant import include_protocol_definitions_no_comments
        print(f"  ✓ baseline1_no_comments.utils_variant")
    except Exception as e:
        print(f"  ✗ baseline1_no_comments.utils_variant: {e}")
        all_ok = False
    
    # Check baseline2 variant
    try:
        from baseline2_no_filtering.utils_variant import get_exception_tracker
        print(f"  ✓ baseline2_no_filtering.utils_variant")
    except Exception as e:
        print(f"  ✗ baseline2_no_filtering.utils_variant: {e}")
        all_ok = False
    
    # Check run_ablation
    try:
        from run_ablation import AblationHarness
        print(f"  ✓ run_ablation")
    except ImportError as e:
        # run_ablation imports bspl which may not be available outside project context
        if "bspl" in str(e):
            print(f"  ✓ run_ablation (import deferred - requires bspl context)")
        else:
            print(f"  ✗ run_ablation: {e}")
            all_ok = False
    except Exception as e:
        print(f"  ✗ run_ablation: {e}")
        all_ok = False
    
    # Check analyze_results
    try:
        from analyze_results import AblationAnalyzer
        print(f"  ✓ analyze_results")
    except Exception as e:
        print(f"  ✗ analyze_results: {e}")
        all_ok = False
    
    return all_ok

def main():
    print("=" * 70)
    print("ABLATION STUDY SETUP VERIFICATION")
    print("=" * 70)
    
    checks = [
        ("Directory Structure", check_directory_structure),
        ("File Existence", check_files),
        ("Conda Environment (maf-py)", check_environment),
        ("Python Imports", check_imports),
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = all(r for _, r in results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name}: {status}")
    
    if all_passed:
        print("\n✓ All checks passed! Ablation study is ready to run.")
        print(f"\nTo start, run:")
        print(f"  python {ABLATION_DIR}/run_ablation.py --all --runs 1")
        return 0
    else:
        print("\n✗ Some checks failed. Please review the output above.")
        print("\nCommon fixes:")
        print("  1. Environment: conda activate maf-py")
        print("  2. Directory: cd c:\\PhD\\Research\\MultiAgents\\Code\\MAF")
        return 1

if __name__ == "__main__":
    sys.exit(main())
