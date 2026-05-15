# Quick Distribution Guide

Your CodeSensei project is now set up for professional distribution **without exposing personal file paths**.

## What's New

✅ **New GUI entry point**: `code-sensei-gui` command  
✅ **Distribution packages created** in `dist/` folder  
✅ **No path exposure** - clean installation for end users  

## Your Distribution Files

```
dist/
├── code_sensei-0.1.0-py3-none-any.whl    (Binary package - easiest)
└── code_sensei-0.1.0.tar.gz              (Source package - transparent)
```

Both packages hide your personal file structure from users.

## How to Distribute

### Option A: Share the Wheel (Easiest for Users)

```bash
# Share the .whl file
# Users install with:
pip install code_sensei-0.1.0-py3-none-any.whl
code-sensei-gui
```

**Advantages:**
- No compilation needed
- No paths exposed
- Works offline
- Fastest installation

### Option B: Publish to PyPI (Professional)

```bash
pip install twine
twine upload dist/*
```

**Then users just:**
```bash
pip install code-sensei[gui]
code-sensei-gui
```

### Option C: Share Source Code

Users follow installation:
```bash
git clone [your-repo]
cd code-sensei
pip install -e ".[gui]"
code-sensei-gui
```

---

## Testing Your Distribution

Before sharing, verify installation works clean:

```bash
# Create test environment
python -m venv test_env
test_env\Scripts\activate

# Install from wheel
pip install dist/code_sensei-0.1.0-py3-none-any.whl

# Test GUI launches
code-sensei-gui
```

---

## Files You Created

📄 **DISTRIBUTION.md** - Detailed distribution guide (77 lines)  
🐍 **scripts/build_distribution.py** - Automated build script  
📦 **dist/code_sensei-0.1.0-py3-none-any.whl** - Binary package (31 MB)  
📦 **dist/code_sensei-0.1.0.tar.gz** - Source package (284 KB)  

---

## Key Privacy Safeguards

✅ All relative paths (no absolute paths exposed)  
✅ Entry point is generic (no folder references)  
✅ Configuration via environment variables  
✅ No `.venv` or personal paths in packages  
✅ Users run command from anywhere  

---

## Rebuild Distributions

Whenever you make changes:

```bash
python scripts/build_distribution.py
```

This automatically cleans old builds and creates fresh packages.

---

## Next Steps

1. **Share the wheel**: Send `dist/code_sensei-0.1.0-py3-none-any.whl` to users
2. **Or publish to PyPI**: Follow DISTRIBUTION.md for PyPI instructions  
3. **Update version**: Edit `version = "0.1.0"` in `pyproject.toml` for future releases
4. **Test first**: Always verify in clean environment before sharing

---

## Usage for End Users

After installation, they simply run:

```bash
code-sensei-gui
```

That's it! No file paths, no confusion, no personal data exposed.

---

## FAQ

**Q: Can users modify the code after installing?**  
A: Yes, they can if they install from source. Wheel is read-only (recommended).

**Q: Do users need Ollama installed?**  
A: Yes, they need `ollama serve` running for LLM features.

**Q: Can they use on different machines?**  
A: Yes! No machine-specific paths are stored.

**Q: How do I update the package?**  
A: Update version in `pyproject.toml`, run `build_distribution.py`, share new `.whl`

---

For more details, see **DISTRIBUTION.md** in project root.
