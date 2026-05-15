#!/usr/bin/env python
"""
Build script for creating CodeSensei distributions (wheel and source).

Usage:
    python scripts/build_distribution.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

def main() -> int:
    """Build wheel and source distributions."""
    root = Path(__file__).parent.parent
    dist_dir = root / "dist"
    build_dir = root / "build"
    
    print("🔨 CodeSensei Distribution Builder")
    print("=" * 50)
    
    # Clean old artifacts
    print("\n📦 Cleaning old build artifacts...")
    for directory in [dist_dir, build_dir]:
        if directory.exists():
            shutil.rmtree(directory)
            print(f"  ✓ Removed {directory.name}/")
    
    # Install build tools
    print("\n📚 Installing build tools...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "build", "wheel"],
        cwd=root,
        check=True
    )
    print("  ✓ Build tools ready")
    
    # Build distributions
    print("\n🏗️  Building distributions...")
    subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=root,
        check=True
    )
    
    # Show results
    print("\n✅ Build Complete!")
    print("=" * 50)
    print(f"\n📁 Distributions created in: {dist_dir}/")
    print("\n Files:")
    for file in sorted(dist_dir.glob("*")):
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  • {file.name:40} ({size_mb:6.2f} MB)")
    
    print("\n📖 Distribution instructions: See DISTRIBUTION.md")
    print("\n🚀 To upload to PyPI:")
    print(f"   pip install twine")
    print(f"   twine upload dist/*")
    print("\n💾 To share wheel offline:")
    print(f"   Copy dist/code_sensei-*.whl to users")
    print(f"   Users run: pip install code_sensei-*.whl")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
