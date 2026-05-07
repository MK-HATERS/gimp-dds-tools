# GIMP DDS Export Plugin - Setup & Usage Guide

## Version 3.0 - Complete Refactor

This guide covers installation, configuration, and troubleshooting of the improved DDS export plugin.

---

## Requirements

- **GIMP 3.0 or newer**
- **Python 3.8+** with GObject Introspection bindings
- **texconv** (Microsoft DirectXTex converter)
- **Windows OS** (currently; Linux/macOS support planned)

---

## Installation

### Step 1: Install texconv

#### Option A: Windows Package Manager (Recommended)

```bash
winget install texconv
```

This installs texconv to `C:\Program Files\texconv\` which is automatically detected.

#### Option B: Manual Installation

1. Download from: https://github.com/microsoft/DirectXTex/releases
2. Extract to a known location (e.g., `C:\tools\texconv.exe`)
3. Set environment variable:
   ```bash
   setx TEXCONV_PATH "C:\tools\texconv.exe"
   ```
   Then restart your terminal/system.

#### Verification

Open Command Prompt and run:
```bash
texconv -?
```

Should show texconv help output.

### Step 2: Install GIMP Plugin

1. Place `dds_tools.py` in your GIMP plug-ins folder:
   - **Windows**: `%LOCALAPPDATA%\Local\Programs\GIMP 3\lib\gimp\3.0\plug-ins\dds_tools\`
   - **Linux**: `~/.config/GIMP/3.0/plug-ins/`
   - **macOS**: `~/Library/Application Support/GIMP/3.0/plug-ins/`

2. Make script executable (Linux/macOS):
   ```bash
   chmod +x dds_tools.py
   ```

3. Restart GIMP or reload plugins via `Filters → Python-Fu → Refresh Scripts`

---

## Usage

### Basic Export

1. Open image in GIMP
2. Go to `File → Export` (or `Image → Export As`)
3. You should see "Export as DDS (texconv)..." option
4. Select your desired options:
   - **Compression format**: BC1-BC7 or uncompressed
   - **Generate mipmaps**: Creates multiple resolution versions
   - **sRGB color space**: For perceptually-accurate textures
   - **Overwrite existing**: Allow replacing existing DDS files

5. Click "Export" and choose save location

### Recommended Settings

| Use Case | Format | Mipmaps | sRGB | Notes |
|----------|--------|---------|------|-------|
| Game Textures | BC3/DXT5 | ✓ | ✓ | Best quality/compression balance |
| Diffuse Maps | BC3/DXT5 | ✓ | ✓ | Color data should be sRGB |
| Normal Maps | BC5/RG | ✓ | ✗ | Linear color space for normals |
| High Quality | BC7 | ✓ | ✓ | Best quality, slower compression |
| Lightweight | BC1/DXT1 | ✓ | ✓ | Fast, smallest size |
| Alpha Textures | BC2/DXT3 | ✓ | ✓ | For 1-bit/binary alpha |
| Uncompressed | R8G8B8A8 | ✓ | ✓ | Debug/reference only |

---

## Logging & Troubleshooting

### View Log File

All operations are logged to: `~/.gimp-3.0/dds_export.log`

On Windows, this is typically:
```
C:\Users\YourUsername\AppData\Roaming\GIMP\3.0\dds_export.log
```

View with any text editor or:
```bash
tail -f ~/.gimp-3.0/dds_export.log  # Unix/Linux
Get-Content $env:APPDATA\GIMP\3.0\dds_export.log -Tail 50  # PowerShell
```

### Common Issues

#### Issue: "texconv.exe not found"

**Solutions:**
1. Reinstall texconv via `winget install texconv`
2. Set `TEXCONV_PATH` environment variable manually
3. Verify texconv is accessible:
   ```bash
   where texconv.exe
   ```

**Log check:**
```
ERROR - texconv.exe not found. Please install it or set TEXCONV_PATH
```

#### Issue: "Output directory is not writable"

**Solutions:**
1. Choose a different save location
2. Check folder permissions
3. Ensure you have write access to the target directory

**Log check:**
```
ERROR - Output directory is not writable: C:/path/to/dir
```

#### Issue: "PNG save error"

**Solutions:**
1. Ensure image can be exported as PNG (no GIMP-specific features)
2. Try `Image → Flatten Image` first
3. Check available disk space

**Log check:**
```
ERROR - PNG export failed: [error details]
```

#### Issue: "Image dimensions must be multiples of 4"

**Solutions:**
1. Resize image to nearest multiple of 4 (512, 1024, 2048, etc.)
2. Use `Image → Scale Image` and enable "Lock aspect ratio"

**Log check:**
```
WARNING - Image dimensions (513x513) are not multiples of 4
```

### Debug Mode

To enable verbose logging, edit line 39 in `dds_tools.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Already set to DEBUG
    ...
)
```

Then restart GIMP and check the log file for detailed information about each step.

---

## Advanced Configuration

### Environment Variables

#### TEXCONV_PATH
Set to override texconv location:

```bash
# Windows Command Prompt
set TEXCONV_PATH=C:\custom\path\texconv.exe

# Windows PowerShell
$env:TEXCONV_PATH = "C:\custom\path\texconv.exe"

# Linux/macOS
export TEXCONV_PATH=/usr/local/bin/texconv
```

### Log File Location

Log file is always saved to: `~/.gimp-3.0/dds_export.log`

To access from GIMP console:
```python
log_path = Path.home() / '.gimp-3.0' / 'dds_export.log'
print(log_path)
```

---

## Running Tests

To verify functionality:

```bash
# Install pytest
pip install pytest

# Run tests
python -m pytest tests/test_dds_export.py -v
```

Expected output:
```
======================== test session starts ========================
...
======================== 30 passed in 0.45s ========================
```

---

## Performance Tips

1. **Batch Processing**: Export multiple images to DDS sequentially
2. **Mipmap Generation**: Takes longer for larger images
3. **Compression Format**: BC1 is fastest, BC7 is slowest
4. **Preview**: Generate mipmaps in development, disable in final builds if memory-constrained

### Typical Export Times

| Image Size | Format | With Mipmaps | Time |
|------------|--------|--------------|------|
| 512x512 | BC3 | Yes | 2-3s |
| 1024x1024 | BC3 | Yes | 5-7s |
| 2048x2048 | BC7 | Yes | 15-20s |
| 4096x4096 | BC3 | Yes | 30-40s |

---

## Known Limitations

- **Windows only**: Currently requires Windows OS and texconv.exe
- **CLI only**: No GUI options for advanced texconv features (may be added)
- **Single image**: Batch processing not yet supported
- **No preview**: Cannot preview DDS before saving

---

## Development

### Code Structure

```
dds_tools/
├── dds_tools.py           # Main plugin
tests/
├── test_dds_export.py     # Unit tests
SETUP.md                   # This file
README.md                  # Quick start
```

### Adding New Features

1. Add function with type hints
2. Add logging statements
3. Add corresponding unit tests
4. Update SETUP.md
5. Test with actual GIMP

### Contributing

Contributions welcome! Please:
1. Follow existing code style (type hints, logging, docstrings)
2. Add tests for new functionality
3. Update documentation
4. Test on Windows

---

## Support

If you encounter issues:

1. **Check the log file**: `~/.gimp-3.0/dds_export.log`
2. **Verify texconv**: Run `texconv -?` in command prompt
3. **Check GIMP console** for Python errors: `Filters → Python-Fu → Console`
4. **Search existing issues** on GitHub
5. **Create a new issue** with:
   - GIMP version
   - Python version
   - texconv version
   - Relevant log file excerpts
   - Steps to reproduce

---

## Version History

### v3.0 (Current)
- Complete refactor with type hints
- Comprehensive logging to file
- Progress feedback with GIMP 3.0+ API
- Improved error handling and validation
- Full unit test suite
- Auto-detection of texconv via PATH or environment variable

---

## License

Same as GIMP plugins (typically GPL v2+)

---

## Credits

- **Original Author**: Tenir
- **Refactor/Improvements**: v3.0 Contributors MkHaters
- **texconv**: Microsoft DirectXTex team
- **GIMP**: GIMP Development Team
