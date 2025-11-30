# StreamCondor

StreamCondor is a lightweight system-tray utility that monitors livestreams and opens them with [Streamlink](https://streamlink.github.io/).

## Features

- 🔔 **Real-time Stream Monitoring** - Automatically detect when your favorite streamers go live
- 🎯 **Multi-platform Support** - Works with Twitch, YouTube and any Streamlink-supported platform
- 🖥️ **System Tray Integration** - Unobtrusive monitoring with visual status indicators
- 🎨 **Custom Player Support** - Launch streams with mpv, VLC, or your preferred media player
- ⚙️ **Flexible Configuration** - Per-stream settings for quality, notifications, and streamlink arguments
- 🌐 **Favicon Support** - Automatic platform icon fetching and caching
- 📋 **Clipboard Integration** - Quick stream launching from copied URLs

Supported platforms: Linux, Windows, macOS (desktop with a system tray)

Minimum requirement: Python 3.12

## Run from source (no install)

To run a local copy without installing the package:

```bash
git clone https://github.com/tarzasai/StreamCondor.git
cd StreamCondor
PYTHONPATH="$PWD/src" python -m streamcondor.main
```

This runs the application using the sources in `src/streamcondor`.

## Configuration file locations

StreamCondor stores a single JSON configuration file per user:

- Linux: `~/.config/StreamCondor.json`
- Windows: `%APPDATA%\StreamCondor.json`
- macOS: `~/Library/Application Support/StreamCondor.json`

If the file is missing the app starts with reasonable defaults; open the Settings UI to manage streams.

## Troubleshooting

- No tray icon: ensure your desktop environment provides a system tray (some Wayland setups may need extra support).
- Icons missing: install from PyPI (the packaged wheel includes assets) or ensure `src/streamcondor/assets` exists when running from source.
- If the app exits or shows errors, run in a terminal to see logs:

```bash
streamcondor --help
# or when running from source
PYTHONPATH="$PWD/src" python -m streamcondor.main --log-level DEBUG
```

## Reporting issues

Open issues at: https://github.com/tarzasai/StreamCondor/issues

When reporting, include platform, steps to reproduce, and any terminal logs.

## License

StreamCondor is licensed under the MIT License. See `LICENSE` for details.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Streamlink](https://streamlink.github.io/) - Stream extraction library
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- Contributors and testers

---

**Note**: This is a third-party tool not affiliated with any streaming platform.
