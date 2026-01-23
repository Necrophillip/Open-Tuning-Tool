# 🚀 Release Management Guide

## Creating a Release with GitHub Actions

This project uses GitHub Actions to automatically compile and distribute binaries for all platforms.

### Step 1: Create a Release Tag

```bash
# Create and push a version tag
git tag -a v1.0.0-rc1 -m "Release Candidate 1 - Step Response Analysis Improvements"
git push origin v1.0.0-rc1
```

### Step 2: Create Release on GitHub

1. Go to: https://github.com/Necrophillip/Open-Tuning-Tool/releases
2. Click "Draft a new release"
3. Select the tag you just created
4. Add release title: `Open-Tuning-Tool 1.0.0-rc1`
5. Add release description (copy from CHANGELOG.md)
6. Mark as **Pre-release** if RC or beta
7. Click "Publish release"

### Step 3: Automatic Build Process

GitHub Actions will automatically:

1. ✅ Clone the repository
2. ✅ Build Windows executable (.exe)
3. ✅ Build macOS app bundle and DMG
4. ✅ Build Linux executable
5. ✅ Upload all binaries to the release
6. ✅ Create checksums
7. ✅ Notify on completion

**Total time**: 15-25 minutes

### Step 4: Download and Test

Once the build completes:

1. Visit the release page: https://github.com/Necrophillip/Open-Tuning-Tool/releases/tag/v1.0.0-rc1
2. Download the appropriate binary:
   - Windows: `Open-Tuning-Tool-windows-x64.zip`
   - macOS: `Open-Tuning-Tool-macos.dmg`
   - Linux: `Open-Tuning-Tool-linux-x64.tar.gz`

3. Test the binary on each platform

### Step 5: Publish Announcement

After successful testing:

1. Update project website/landing page
2. Post to FPV communities
3. Create announcement on GitHub Discussions
4. Share with team

---

## Manual Build (Optional)

If you need to build locally without GitHub Actions:

### Windows

```bash
cd Open-Tuning-Tool
pip install pyinstaller

pyinstaller --onefile ^
    --windowed ^
    --name "Open-Tuning-Tool" ^
    --add-data "fpv_tuner:fpv_tuner" ^
    fpv_tuner/main.py

# Output: dist/Open-Tuning-Tool.exe
```

### macOS

```bash
cd Open-Tuning-Tool
pip install pyinstaller

pyinstaller --onefile \
    --windowed \
    --name "Open-Tuning-Tool" \
    --osx-bundle-identifier com.opentuningtool.fpv \
    --add-data "fpv_tuner:fpv_tuner" \
    fpv_tuner/main.py

# Create DMG
hdiutil create -volname "Open-Tuning-Tool" \
    -srcfolder dist/Open-Tuning-Tool.app \
    -ov -format UDZO \
    dist/Open-Tuning-Tool-macos.dmg

# Output: dist/Open-Tuning-Tool-macos.dmg
```

### Linux

```bash
cd Open-Tuning-Tool
pip install pyinstaller

pyinstaller --onefile \
    --name "Open-Tuning-Tool" \
    --add-data "fpv_tuner:fpv_tuner" \
    fpv_tuner/main.py

# Create tarball
tar czf Open-Tuning-Tool-linux-x64.tar.gz -C dist Open-Tuning-Tool

# Output: Open-Tuning-Tool-linux-x64.tar.gz
```

---

## Release Checklist

Before releasing:

- [ ] Update `fpv_tuner/__version__.py` with new version
- [ ] Update `CHANGELOG.md` with all changes
- [ ] Update `README.md` if needed
- [ ] Run all tests locally
- [ ] Verify on all platforms (or wait for CI)
- [ ] Update installation docs
- [ ] Create GitHub release
- [ ] Wait for GitHub Actions to complete
- [ ] Test all downloaded binaries
- [ ] Announce release

---

## Version Numbering

We use Semantic Versioning: `MAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:
- `1.0.0` - First stable release
- `1.0.0-rc1` - Release Candidate 1
- `1.0.0-beta1` - Beta release
- `1.1.0` - Minor feature release
- `1.1.1` - Patch/bug fix release
- `2.0.0` - Major breaking release

---

## CI/CD Pipeline

### Trigger Events

The build workflow is triggered by:

1. **Release creation** - When you create a GitHub release
2. **Manual trigger** - Using `workflow_dispatch` from GitHub Actions tab

### Build Matrix

| Platform | OS | Python | Output |
|----------|-----|--------|--------|
| Windows | Windows Latest | 3.11 | `.exe` |
| macOS | macOS Latest | 3.11 | `.dmg` + `.app` |
| Linux | Ubuntu Latest | 3.11 | `.tar.gz` |

### Artifacts

All artifacts are:
- ✅ Automatically signed (where applicable)
- ✅ Stored in release assets
- ✅ Available for 30 days
- ✅ Downloadable by all users

---

## Troubleshooting

### Build fails on Windows

**Solution**: Make sure PyQt6 is installed:
```bash
pip install PyQt6
```

### DMG creation fails on macOS

**Solution**: Ensure `hdiutil` is available (should be on all macOS):
```bash
which hdiutil
```

### Linux executable won't run

**Solution**: Make executable and check dependencies:
```bash
chmod +x Open-Tuning-Tool
ldd Open-Tuning-Tool  # Check dependencies
```

### GitHub Actions fails

Check the logs:
1. Go to Actions tab in GitHub
2. Click the failed workflow
3. See detailed error messages
4. Fix issue and retry

---

## Distribution

### Distribution Channels

After release:

1. **GitHub Releases** - Primary distribution
2. **PyPI** - Python package (optional future)
3. **App Stores** - Windows Store, Mac App Store (future)
4. **Website** - Direct downloads
5. **Package Managers** - Homebrew, Chocolatey (future)

### File Distribution

Share release links:

```markdown
**Download Open-Tuning-Tool 1.0.0-rc1:**

- [Windows x64](https://github.com/Necrophillip/Open-Tuning-Tool/releases/download/v1.0.0-rc1/Open-Tuning-Tool-windows-x64.zip)
- [macOS DMG](https://github.com/Necrophillip/Open-Tuning-Tool/releases/download/v1.0.0-rc1/Open-Tuning-Tool-macos.dmg)
- [Linux x64](https://github.com/Necrophillip/Open-Tuning-Tool/releases/download/v1.0.0-rc1/Open-Tuning-Tool-linux-x64.tar.gz)
```

---

## Post-Release

After successful release:

1. ✅ Mark issues as resolved
2. ✅ Close related pull requests
3. ✅ Create branch for next version
4. ✅ Update development roadmap
5. ✅ Plan next release features

---

**Happy releasing!** 🚀
