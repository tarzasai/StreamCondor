# Architecture Overview

This document provides an in-depth look at StreamCondor's architecture, component interactions, and design decisions.

## Table of Contents

- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [UI Components](#ui-components)
- [Data Flow](#data-flow)
- [Thread Model](#thread-model)
- [Resource Management](#resource-management)
- [Design Decisions](#design-decisions)

## System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        Tray[System Tray Icon]
        Settings[Settings Window]
        StreamDlg[Stream Dialog]
        URLDlg[URL Dialog]
    end

    subgraph "Business Logic Layer"
        Monitor[Stream Monitor<br/>QThread]
        Launcher[Stream Launcher]
        Config[Configuration Manager]
        Favicons[Favicon Manager]
    end

    subgraph "External Services"
        SL[Streamlink CLI]
        Player[Media Player]
        Web[Web Services]
    end

    subgraph "Storage Layer"
        ConfigFile[Config JSON<br/>~/.config]
        Cache[Favicon Cache<br/>~/.cache]
        Assets[Application Assets]
    end

    Tray --> Monitor
    Tray --> Launcher
    Tray --> Config
    Settings --> Config
    StreamDlg --> Config

    Monitor --> SL
    Launcher --> SL
    Launcher --> Player
    Favicons --> Web

    Config --> ConfigFile
    Favicons --> Cache
    Tray -.-> Assets

    style Tray fill:#28a745,color:#fff
    style Monitor fill:#ffc107,color:#000
    style Config fill:#17a2b8,color:#fff
    style ConfigFile fill:#e1f5e1,color:#000
    style Cache fill:#e1f5e1,color:#000
```

### Component Layers

1. **UI Layer** - PyQt6 widgets for user interaction
2. **Business Logic** - Core functionality and state management
3. **External Services** - Integration with streamlink and media players
4. **Storage** - Persistent configuration and cached data

## Core Components

### 1. Configuration Manager (`configuration.py`)

Manages application configuration with automatic persistence.

```mermaid
classDiagram
    class Configuration {
        -QSettings settings
        -dict _config
        +get(key, default)
        +set(key, value)
        +get_streams() list
        +add_stream(stream)
        +remove_stream(index)
        +save()
    }

    class ConfigProperty {
        <<descriptor>>
        +__get__(instance, owner)
        +__set__(instance, value)
    }

    Configuration --> ConfigProperty : uses

    note for Configuration "Auto-saves on property changes\nUses XDG paths on Linux\nJSON serialization"
```

**Key Features**:
- Property-based access with auto-save
- XDG base directory compliance
- Stream list management
- Window geometry persistence
- Type validation

**Usage Example**:
```python
config = Configuration()
config.check_interval = 60  # Auto-saves
streams = config.get_streams()
```

### 2. Stream Monitor (`monitor.py`)

Background thread that periodically checks stream status.

```mermaid
sequenceDiagram
    participant Main
    participant Monitor
    participant Streamlink
    participant TrayIcon

    Main->>Monitor: start()
    activate Monitor

    loop Every check_interval seconds
        Monitor->>Streamlink: Check each stream
        Streamlink-->>Monitor: Status (online/offline)

        alt Stream status changed
            Monitor->>TrayIcon: emit stream_online(stream)
            TrayIcon-->>User: Show notification
        end
    end

    Main->>Monitor: stop()
    deactivate Monitor
```

**Key Features**:
- QThread-based for non-blocking operation
- Configurable check interval
- Per-stream enable/disable
- Efficient status change detection
- Error handling and retry logic

**Signals**:
- `stream_online(stream)` - Stream went online
- `stream_offline(stream)` - Stream went offline
- `check_complete()` - Check cycle finished

### 3. Stream Launcher (`launcher.py`)

Builds and executes streamlink commands with custom arguments.

```mermaid
flowchart TD
    Start[Launch Stream] --> LoadConfig[Load Stream Config]
    LoadConfig --> MergeArgs[Merge Arguments]

    MergeArgs --> GlobalArgs[Global streamlink_args]
    MergeArgs --> StreamArgs[Stream-specific sl_args]
    MergeArgs --> PlayerArgs[Player arguments]

    GlobalArgs --> VarSub[Variable Substitution]
    StreamArgs --> VarSub
    PlayerArgs --> VarSub

    VarSub --> BuildCmd[Build Command Line]
    BuildCmd --> ShellParse[shlex.split]
    ShellParse --> Popen[subprocess.Popen]

    Popen --> DEVNULL[stdout/stderr → DEVNULL]
    DEVNULL --> Detach[start_new_session=True]
    Detach --> Return[Return Success]

    style Popen fill:#ffc107,color:#000
    style DEVNULL fill:#dc3545,color:#fff
    style Detach fill:#28a745,color:#fff
```

**Command Structure**:
```bash
streamlink [global_args] [stream_args] <url> <quality> --player <player> --player-args "<player_args>"
```

**Argument Merging Logic**:
1. Start with global defaults
2. Overlay stream-specific overrides
3. Apply variable substitution (`$SC.name`, `$SC.type`)
4. Remove duplicates (last wins)
5. Build final command line

**Design Decision: DEVNULL for stdout/stderr**
```python
subprocess.Popen(
  shlex.split(command_line),
  stdout=subprocess.DEVNULL,  # Must be DEVNULL
  stderr=subprocess.DEVNULL,  # PIPE causes launch failure
  start_new_session=True
)
```

**Why DEVNULL?** Using `PIPE` for output capture prevents streamlink from launching properly in detached mode. DEVNULL is required for fire-and-forget process execution.

### 4. Favicon Manager (`favicons.py`)

Fetches, caches, and manages platform icons.

```mermaid
sequenceDiagram
    participant UI
    participant Favicons
    participant Cache
    participant Web

    UI->>Favicons: get_favicon(url, size)

    Favicons->>Cache: Check disk cache
    alt Cache hit
        Cache-->>Favicons: QPixmap
        Favicons-->>UI: Cached icon
    else Cache miss
        Favicons->>Web: Fetch HTML
        Web-->>Favicons: HTML content
        Favicons->>Favicons: Extract favicon URL
        Favicons->>Web: Download image
        Web-->>Favicons: Image bytes
        Favicons->>Favicons: Resize with PIL
        Favicons->>Cache: Save to disk
        Favicons-->>UI: New icon
    end
```

**Features**:
- BeautifulSoup4 HTML parsing
- Multiple size support (16, 32, 64)
- PIL-based resizing with antialiasing
- XDG cache directory storage
- URL normalization and domain extraction

**Cache Structure**:
```
~/.cache/StreamCondor/favicons/
├── twitch.tv_16.png
├── twitch.tv_32.png
├── youtube.com_16.png
└── ...
```

### 5. Streamlink User (`sluser.py`)

Wrapper for streamlink with user config and plugin support.

```python
class StreamlinkSession:
  def __init__(self):
    self.session = streamlink.Streamlink()
    self._load_user_config()
    self._load_plugins()

  def streams(self, url: str) -> dict:
    """Get available streams for URL."""
    return self.session.streams(url)
```

**Features**:
- Loads user streamlink config
- Custom plugin directory support
- Shared session instance

### 6. Resource Manager (`resources.py`)

Cross-platform asset path resolution.

```mermaid
flowchart TD
    Request[Get Asset Path] --> CheckPyInstaller{PyInstaller?}

    CheckPyInstaller -->|Yes| UseSys[Use sys._MEIPASS]
    CheckPyInstaller -->|No| CheckInstalled{Installed?}

    CheckInstalled -->|Yes| UsePkg[Use package_data]
    CheckInstalled -->|No| UseDev[Use src/assets/]

    UseSys --> Return[Return Path]
    UsePkg --> Return
    UseDev --> Return

    style CheckPyInstaller fill:#ffc107,color:#000
    style CheckInstalled fill:#ffc107,color:#000
    style Return fill:#28a745,color:#fff
```

**Usage**:
```python
from resources import resource_path

icon_path = resource_path('assets/icon_monitoring_idle.png')
```

## UI Components

### System Tray Icon (`trayicon.py`)

Main user interface element.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Menu_Open: Right Click
    Idle --> Action: Left Click
    Idle --> Online: Stream Detected

    Menu_Open --> Idle: Select Item
    Menu_Open --> Settings: Open Settings
    Menu_Open --> URLDialog: Open URL

    Online --> Idle: Stream Offline
    Online --> Menu_Open: Right Click

    Action --> Idle: Action Complete

    Settings --> Idle: Close
    URLDialog --> Idle: Close

    style Idle fill:#28a745,color:#fff
    style Online fill:#dc3545,color:#fff
    style Settings fill:#17a2b8,color:#fff
```

**Features**:
- Context menu with dynamic online streams
- Visual state indicators (5 icon states)
- Desktop notifications (per-stream override)
- Configurable left-click action
- Tooltip with stream counts

**Icon States**:
1. `icon_monitoring_off.png` - Monitoring disabled
2. `icon_monitoring_idle.png` - Monitoring, no streams online
3. `icon_monitoring_live.png` - One or more streams online
4. `icon_monitoring_idle_muted.png` - Monitoring, notifications off
5. `icon_monitoring_live_muted.png` - Streams online, notifications off

### Settings Window (`settings.py`)

Tabbed configuration interface.

```mermaid
graph TB
    Settings[Settings Window]

    subgraph "Streams Tab"
        Tree[Stream Tree<br/>QTreeWidget]
        Buttons[Add/Edit/Delete/Clone]
        Tree --> StreamDialog
        Buttons --> StreamDialog
    end

    subgraph "General Tab"
        Monitoring[Monitoring Settings]
        Player[Player Settings]
        Behavior[Behavior Settings]
    end

    Settings --> StreamsTab
    Settings --> GeneralTab

    StreamsTab --> Tree
    GeneralTab --> Monitoring
    GeneralTab --> Player
    GeneralTab --> Behavior

    style Settings fill:#17a2b8,color:#fff
    style Tree fill:#e1f5e1,color:#000
```

**Stream Tree Structure**:
```
Root
├── twitch
│   ├── streamer1 [●] [🔔]
│   └── streamer2 [○]
├── youtube
│   └── channel1 [●] [🔔]
└── other
    └── custom_stream [●]
```

**Features**:
- Grouped by stream type
- Visual indicators (online status, notifications)
- Drag-and-drop reordering
- Favicon integration
- Keyboard shortcuts

### Stream Dialog (`stream.py`)

Multi-tab editor for stream configuration.

```mermaid
graph TB
    StreamDialog[Stream Dialog]

    subgraph "Basic Tab"
        URL[URL Input]
        Name[Name Input]
        Type[Type Selection]
    end

    subgraph "Options Tab"
        Quality[Quality Selection]
        Check[Enable Checking]
        Notify[Enable Notifications]
    end

    subgraph "Advanced Tab"
        SLArgs[Streamlink Args]
        Player[Player Selection]
        PlayerArgs[Player Args]
    end

    subgraph "Preview Tab"
        Command[Command Preview]
    end

    StreamDialog --> BasicTab
    StreamDialog --> OptionsTab
    StreamDialog --> AdvancedTab
    StreamDialog --> PreviewTab

    URL --> AutoDetect[Auto-detect Type]
    AutoDetect --> Type

    SLArgs --> Command
    PlayerArgs --> Command

    style StreamDialog fill:#17a2b8,color:#fff
    style Command fill:#e1f5e1,color:#000
```

**Features**:
- Auto-detection of stream type from URL
- Live command preview with syntax highlighting
- Variable substitution preview
- Validation and error messages
- Clone mode for quick stream duplication

## Data Flow

### Stream Status Check Flow

```mermaid
sequenceDiagram
    participant Timer as QTimer
    participant Monitor as StreamMonitor
    participant SLS as Streamlink
    participant Config as Configuration
    participant Tray as TrayIcon
    participant User

    Timer->>Monitor: timeout()
    activate Monitor

    Monitor->>Config: get_streams()
    Config-->>Monitor: streams[]

    loop For each enabled stream
        Monitor->>SLS: streams(url)

        alt Stream available
            SLS-->>Monitor: {quality: Stream}
            Monitor->>Monitor: Mark as online
        else Stream unavailable
            SLS-->>Monitor: {}
            Monitor->>Monitor: Mark as offline
        end

        alt Status changed
            Monitor->>Tray: emit stream_online/offline(stream)

            alt Notifications enabled
                Tray->>User: Show notification
            end

            Tray->>Tray: Update icon
            Tray->>Tray: Update menu
        end
    end

    Monitor->>Tray: emit check_complete()
    deactivate Monitor
```

### Stream Launch Flow

```mermaid
sequenceDiagram
    participant User
    participant Menu as Context Menu
    participant Tray as TrayIcon
    participant Launcher as StreamLauncher
    participant Config as Configuration
    participant SL as Streamlink Process
    participant Player as Media Player

    User->>Menu: Click stream
    Menu->>Tray: launch_stream(stream)
    Tray->>Launcher: launch(stream)
    activate Launcher

    Launcher->>Config: Get global settings
    Config-->>Launcher: defaults

    Launcher->>Launcher: Merge arguments
    Launcher->>Launcher: Variable substitution
    Launcher->>Launcher: Build command line

    Launcher->>SL: Popen(streamlink ...)
    activate SL
    SL->>Player: Launch player
    activate Player

    Launcher-->>Tray: Success
    deactivate Launcher

    Note over SL,Player: Detached processes

    deactivate SL
    deactivate Player
```

### Configuration Save Flow

```mermaid
flowchart LR
    UserEdit[User Edits Setting] --> Property[ConfigProperty.__set__]
    Property --> Validate[Type Validation]
    Validate --> Update[Update _config dict]
    Update --> Save[config.save]
    Save --> JSON[Write JSON file]
    JSON --> Signal[Emit changed signal]

    style UserEdit fill:#17a2b8,color:#fff
    style Save fill:#ffc107,color:#000
    style JSON fill:#28a745,color:#fff
```

## Thread Model

### Main Thread vs Background Thread

```mermaid
graph TB
    subgraph "Main Thread (GUI)"
        Main[QApplication]
        Tray[TrayIcon]
        Settings[Settings Window]
        Dialogs[Dialogs]

        Main --> Tray
        Main --> Settings
        Main --> Dialogs
    end

    subgraph "Background Thread"
        Monitor[StreamMonitor<br/>QThread]
        Timer[QTimer]

        Timer -.-> Monitor
    end

    Monitor -.signal.-> Tray
    Monitor -.signal.-> Settings

    Tray --start/stop--> Monitor

    style Main fill:#007bff,color:#fff
    style Monitor fill:#ffc107,color:#000
```

**Thread Safety**:
- GUI operations only in main thread
- Monitor runs in separate QThread
- Signal/slot mechanism for cross-thread communication
- No shared mutable state

**Why QThread?**
- Non-blocking UI during stream checks
- Clean signal-based state updates
- Qt event loop integration
- Proper cleanup on application exit

## Resource Management

### Asset Loading Strategy

```mermaid
flowchart TD
    Request[Load Asset] --> DevCheck{Development?}

    DevCheck -->|Yes| SrcAssets[src/assets/]
    DevCheck -->|No| InstallCheck{Installed?}

    InstallCheck -->|PyInstaller| MEIPASS[sys._MEIPASS]
    InstallCheck -->|pip| SitePackages[site-packages/]

    SrcAssets --> Load[Load File]
    MEIPASS --> Load
    SitePackages --> Load

    Load --> Cache[Cache in Memory]
    Cache --> Return[Return Resource]

    style DevCheck fill:#ffc107,color:#000
    style InstallCheck fill:#ffc107,color:#000
    style Cache fill:#28a745,color:#fff
```

### Cache Management

**Favicon Cache**:
- Location: `~/.cache/StreamCondor/favicons/`
- Format: `{domain}_{size}.png`
- Expiration: Manual cleanup (no auto-expiry)
- Size limit: None (typically < 10 MB)

**Config File**:
- Location: `~/.config/StreamCondor.json`
- Format: Pretty-printed JSON (2-space indent)
- Backup: None (manual backup recommended)
- Size: Proportional to stream count

## Design Decisions

### Why PyQt6 Instead of Tkinter?

- **System tray support** - Native QSystemTrayIcon
- **Rich widgets** - QTreeWidget, QTabWidget with styling
- **Thread integration** - QThread with signal/slot
- **Modern look** - Better cross-platform appearance

### Why JSON for Configuration?

- Human-readable and editable
- Native Python support
- Easy backup and version control
- Simple schema validation

### Why Detached Processes?

- User may close StreamCondor while watching
- Media player process must outlive parent
- No need for process management
- Clean separation of concerns

### Why Not Built-in Streamlink Library?

- CLI provides better stability
- User's streamlink config respected
- Custom plugins work automatically
- Easier debugging (can test commands directly)

### Why Three-State Notifications?

```python
notify: bool | None
```

- `True` - Always notify (override default)
- `False` - Never notify (override default)
- `None` - Use global default (flexible)

Benefits:
- Per-stream customization
- Global default changes apply automatically
- Explicit overrides preserved

## Performance Considerations

### Stream Checking Optimization

- **Parallel checks** - Future enhancement (currently sequential)
- **Check interval** - User-configurable (default 60s)
- **Status caching** - Only signal changes, not every check
- **Error handling** - Failed checks don't block others

### Memory Usage

- **Config** - Single in-memory dict (~1 KB per stream)
- **Favicon cache** - Lazy-loaded QPixmaps (released when not displayed)
- **Monitor state** - Minimal per-stream booleans
- **Total** - Typically < 50 MB resident set size

### Startup Time

```
0-100ms   Import modules
100-200ms Load configuration
200-300ms Initialize streamlink
300-400ms Create UI
400-500ms Show tray icon
```

**Total**: ~500ms typical startup time

## Security Considerations

### Command Injection Prevention

```python
# Safe: shlex.split properly escapes arguments
command_line = f"streamlink {url} {quality}"
subprocess.Popen(shlex.split(command_line))
```

### URL Validation

- No automatic URL opening (user confirmation required)
- Streamlink handles URL parsing and validation
- No direct shell command execution

### Configuration File

- Local file system only (no remote configs)
- Standard permissions (user read/write)
- No sensitive data stored (no passwords/tokens)

## Future Enhancements

### Planned Features

1. **Parallel stream checking** - Use asyncio or ThreadPoolExecutor
2. **Stream recording** - Integration with streamlink --record
3. **Notification templates** - Custom notification messages
4. **Plugin system** - User-defined stream handlers
5. **Multi-profile support** - Switch between config profiles
6. **Statistics** - Track uptime, view count, etc.

### Architecture Changes

- **Database option** - SQLite for large stream lists
- **Event sourcing** - Append-only event log for state changes
- **gRPC API** - Remote control and monitoring
- **Web UI** - Browser-based configuration

---

For implementation details, see source code comments and docstrings.
