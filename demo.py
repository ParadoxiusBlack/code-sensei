#!/usr/bin/env python3
"""
CodeSensei Demo Runner

Executes real CodeSensei CLI commands against demo_project without mocks.
Captures complete output including real Ollama LLM responses.

Usage:
    python demo.py

Output:
    - Complete demo run saved to docs/demo_run_latest.txt
    - All 6 demo steps executed with real LLM responses
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _run_cli(args, label):
    """
    Execute a code-sensei CLI command and capture output.
    
    Args:
        args: List of command arguments (code-sensei + subcommand)
        label: Human-readable label for this step
        
    Returns:
        Tuple of (success: bool, output: str, error: str, exit_code: int)
    """
    print(f"\n{'='*70}")
    print(f"DEMO STEP: {label}")
    print(f"{'='*70}")
    print(f"Command: code-sensei {' '.join(args)}")
    print()
    
    try:
        result = subprocess.run(
            ["code-sensei"] + args,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).parent
        )
        
        output = result.stdout
        error = result.stderr
        exit_code = result.returncode
        
        if output:
            print(output)
        if error and exit_code != 0:
            print(f"STDERR:\n{error}", file=sys.stderr)
        
        success = exit_code == 0
        
        return success, output, error, exit_code
        
    except subprocess.TimeoutExpired:
        msg = f"TIMEOUT: Command exceeded 120 seconds"
        print(msg, file=sys.stderr)
        return False, "", msg, -1
    except FileNotFoundError:
        msg = "ERROR: 'code-sensei' command not found. Install with: pip install -e ."
        print(msg, file=sys.stderr)
        return False, "", msg, -1
    except Exception as e:
        msg = f"ERROR: {str(e)}"
        print(msg, file=sys.stderr)
        return False, "", msg, -1


def _strip_ansi(text):
    """Remove ANSI terminal control sequences for clean output."""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def main():
    """Run all 6 demo steps and capture output."""
    
    print("\n" + "="*70)
    print("CodeSensei Demo Runner")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Project: demo_project")
    print()
    
    # Collect all output
    demo_sections = []
    
    # =========================================================================
    # STEP 1: Index
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["index", "./demo_project"],
        "Index demo_project"
    )
    demo_sections.append({
        "step": 1,
        "title": "Indexing",
        "command": "code-sensei index ./demo_project",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # STEP 2: Q&A
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["ask", "What does TokenManager do?", "-p", "./demo_project"],
        "Q&A: What does TokenManager do?"
    )
    demo_sections.append({
        "step": 2,
        "title": "Code Q&A",
        "command": "code-sensei ask 'What does TokenManager do?' -p ./demo_project",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # STEP 3: Test Generation
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["tests", "TokenManager", "-p", "./demo_project", "-f", "pytest"],
        "Generate tests for TokenManager"
    )
    demo_sections.append({
        "step": 3,
        "title": "Test Generation",
        "command": "code-sensei tests TokenManager -p ./demo_project -f pytest",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # STEP 4: Refactoring Analysis
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["refactor", "authentication and token handling", "-p", "./demo_project"],
        "Refactor analysis: authentication and token handling"
    )
    demo_sections.append({
        "step": 4,
        "title": "Refactoring Analysis",
        "command": "code-sensei refactor 'authentication and token handling' -p ./demo_project",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # STEP 5: Documentation Generation
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["docs", "TokenManager", "-p", "./demo_project", "--type", "docstrings", "--style", "google"],
        "Generate Google-style docstrings"
    )
    demo_sections.append({
        "step": 5,
        "title": "Documentation Generation",
        "command": "code-sensei docs TokenManager -p ./demo_project --type docstrings --style google",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # STEP 6: Index Status
    # =========================================================================
    success, stdout, stderr, exit_code = _run_cli(
        ["status", "-p", "./demo_project"],
        "Show index status"
    )
    demo_sections.append({
        "step": 6,
        "title": "Index Status",
        "command": "code-sensei status -p ./demo_project",
        "success": success,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr
    })
    
    # =========================================================================
    # Write Summary
    # =========================================================================
    print("\n" + "="*70)
    print("DEMO SUMMARY")
    print("="*70)
    
    success_count = sum(1 for s in demo_sections if s["success"])
    total_count = len(demo_sections)
    
    print(f"✓ Completed: {success_count}/{total_count} steps")
    print()
    
    for section in demo_sections:
        status = "✓" if section["success"] else "✗"
        print(f"{status} Step {section['step']}: {section['title']} (exit code: {section['exit_code']})")
    
    # =========================================================================
    # Write to File
    # =========================================================================
    docs_dir = Path(__file__).parent / "docs"
    output_file = docs_dir / "demo_run_latest.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("CodeSensei Demo Run Output\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"Project: demo_project\n")
        f.write("\n")
        
        for section in demo_sections:
            f.write("\n" + "="*70 + "\n")
            f.write(f"STEP {section['step']}: {section['title']}\n")
            f.write("="*70 + "\n")
            f.write(f"Command: {section['command']}\n")
            f.write(f"Exit code: {section['exit_code']}\n")
            f.write("\n")
            
            # Clean up ANSI codes for file output
            clean_stdout = _strip_ansi(section["stdout"])
            if clean_stdout:
                f.write("Output:\n")
                f.write(clean_stdout)
                if not clean_stdout.endswith("\n"):
                    f.write("\n")
            
            if section["stderr"]:
                clean_stderr = _strip_ansi(section["stderr"])
                f.write("\nErrors:\n")
                f.write(clean_stderr)
                if not clean_stderr.endswith("\n"):
                    f.write("\n")
    
    print(f"\n✓ Complete output saved to: {output_file}")
    print()
    
    # Return exit code based on all steps succeeding
    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
