# Distribution Guide for CodeSensei

This guide explains how to distribute CodeSensei without exposing your personal file structure.

## Distribution Methods

### Method 1: PyPI Package (Recommended for Open Source)

Distribute through Python Package Index so users install with `pip`.

**Advantages:**
- ✅ No personal file paths exposed
- ✅ One-line installation: `pip install code-sensei[gui]`
- ✅ Automatic updates
- ✅ Professional distribution

**Steps:**
1. Create account on [PyPI.org](https://pypi.org)
2. Run from project root:
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```
3. Users install with: `pip install code-sensei[gui]`
4. Users run with: `code-sensei-gui`

---

### Method 2: Wheel Distribution (Binary Package)

Pre-built package that doesn't expose source paths.

**Advantages:**
- ✅ No paths exposed
- ✅ Faster installation (no compilation)
- ✅ Can be shared as single .whl file
- ✅ Works across Python versions

**Steps:**
1. Build wheel from project root:
   ```bash
   pip install build
   python -m build
   ```
2. Share the `.whl` file from `dist/` folder
3. Users install with: `pip install code_sensei-0.1.0-py3-none-any.whl`
4. Users run with: `code-sensei-gui`

---

### Method 3: Source Distribution with Setup Instructions

Share the source code but with a proper installer.

**Advantages:**
- ✅ Clean installation instructions
- ✅ Users install in their own environment
- ✅ No paths exposed in runtime

**Steps:**
1. Create `INSTALL.md` (see template below)
2. Share only these files:
   - `src/` - Source code
   - `tests/` - Tests
   - `pyproject.toml` - Package config
   - `README.md` - Documentation
   - `LICENSE` - License file
   - `INSTALL.md` - Installation guide

3. Users follow INSTALL.md to set up

---

### Method 4: Windows Installer (MSI)

For non-technical Windows users.

**Advantages:**
- ✅ Single .exe installer
- ✅ No command line needed
- ✅ Professional appearance

**Note:** Requires WiX or similar tool. More advanced setup.

---

## What NOT to Share

⚠️ **Remove these before distribution:**
- `.venv/` - Virtual environment (always regenerate)
- `dist/` - Old builds  
- `build/` - Build artifacts
- `*.egg-info/` - Installation metadata
- `.env` - Environment variables with personal settings
- `.git/` - Git history (create fresh repo for distribution)
- `__pycache__/` - Python cache

---

## Recommended Installation Instructions for Users

### For PyPI Distribution

```markdown
# Installation

### Requirements
- Python 3.10 or higher
- Ollama running locally (for LLM features)

### Quick Start

1. Install CodeSensei:
   ```bash
   pip install code-sensei[gui]
   ```

2. Start Ollama (in another terminal):
   ```bash
   ollama serve
   ```

3. Launch the GUI:
   ```bash
   code-sensei-gui
   ```

4. Click "Select Project..." and choose a folder to analyze

### Environment Variables (Optional)

Create `.env` in your home directory:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
EMBEDDING_MODEL=nomic-embed-text
HYBRID_LLM_MODE=true
```
```

### For Wheel Distribution

```markdown
# Installation

1. Download `code_sensei-0.1.0-py3-none-any.whl`

2. Install:
   ```bash
   pip install code_sensei-0.1.0-py3-none-any.whl
   ```

3. Run:
   ```bash
   code-sensei-gui
   ```
```

---

## Building Distributions

### Build Both Wheel and Source

```bash
pip install build
python -m build
```

Output files in `dist/`:
- `code_sensei-0.1.0-py3-none-any.whl` - Binary wheel
- `code-sensei-0.1.0.tar.gz` - Source distribution

---

## Testing Distribution

Before sharing, test the installation in a clean environment:

```bash
# Create temp venv
python -m venv test_env
test_env\Scripts\activate

# Install from wheel
pip install dist/code_sensei-0.1.0-py3-none-any.whl

# Test GUI
code-sensei-gui
```

---

## Privacy Checklist

Before distribution, verify:

- [ ] No `.venv` or `venv` folder included
- [ ] No absolute paths in code (use relative paths only)
- [ ] No personal file paths in documentation
- [ ] No `.env` file with secrets/paths
- [ ] No `dist/` or `build/` artifacts
- [ ] No local Ollama setup scripts exposing paths
- [ ] README.md doesn't reference personal paths
- [ ] All configuration uses environment variables

---

## Recommended: Method 1 + 2

**Best approach for most cases:**

1. Publish to PyPI for public distribution
2. Also build and share `.whl` for offline installation
3. Include clear installation instructions
4. Users have options: online (`pip install`) or offline (`.whl`)

No personal file structure is exposed in either case!
