# Data Flow Documentation

This document details how data moves through StreamCondor, including configuration management, stream monitoring, and user interactions.

## Table of Contents

- [Configuration Flow](#configuration-flow)
- [Stream Monitoring Flow](#stream-monitoring-flow)
- [Stream Launch Flow](#stream-launch-flow)
- [Notification Flow](#notification-flow)
- [Favicon Loading Flow](#favicon-loading-flow)
- [Settings Update Flow](#settings-update-flow)

## Configuration Flow

### Initial Load on Startup

```mermaid
sequenceDiagram
    participant Main
    participant Config
    participant File as Config File
    participant Tray
    participant Monitor

    Main->>Config: Configuration()
    activate Config

    Config->>File: Check ~/.config/StreamCondor.json

    alt File exists
        File-->>Config: JSON content
        Config->>Config: Parse and validate
    else File missing
        Config->>Config: Create defaults
        Config->>File: Write default config
    end

    Config-->>Main: config instance
    deactivate Config

    Main->>Tray: TrayIcon(config)
    Main->>Monitor: StreamMonitor(config)

    Tray->>Config: get_streams()
    Config-->>Tray: streams[]

    Monitor->>Config: check_interval
    Config-->>Monitor: 60 (seconds)
```

### Configuration Save Flow

```mermaid
flowchart TD
    Start[User Changes Setting] --> UI{UI Component}

    UI -->|Property| ConfigProp[ConfigProperty.__set__]
    UI -->|Direct| ConfigSet[config.set]

    ConfigProp --> Validate[Validate Type]
    ConfigSet --> Validate

    Validate --> UpdateDict[Update _config dict]
    UpdateDict --> Serialize[JSON Serialize]
    Serialize --> Write[Write to File]
    Write --> Emit[Emit config_changed signal]

    Emit --> TrayUpdate[TrayIcon updates]
    Emit --> MonitorUpdate[Monitor restarts]

    style Start fill:#17a2b8,color:#fff
    style Write fill:#28a745,color:#fff
    style Emit fill:#ffc107,color:#000
```

**Auto-Save Example**:
```python
# Property-based auto-save
config.check_interval = 120  # Immediately saved

# Manual save
config.set('custom_key', value)
config.save()
```

### Stream List Modifications

```mermaid
sequenceDiagram
    participant User
    participant Settings as Settings Window
    participant Dialog as Stream Dialog
    participant Config
    participant File as Config File
    participant Monitor

    User->>Settings: Click "Add"
    Settings->>Dialog: StreamDialog(mode='add')
    Dialog->>User: Show form

    User->>Dialog: Fill fields + Save
    Dialog->>Config: add_stream(stream_dict)
    activate Config

    Config->>Config: Append to streams[]
    Config->>File: save()
    File-->>Config: Success

    Config->>Monitor: emit stream_added
    Config-->>Dialog: Success
    deactivate Config

    Dialog->>Settings: close()
    Settings->>Settings: Refresh tree view
    Monitor->>Monitor: Start checking new stream
```

## Stream Monitoring Flow

### Periodic Check Cycle

```mermaid
flowchart TD
    Start[QTimer Timeout] --> GetStreams[Get Enabled Streams]
    GetStreams --> Loop{For Each Stream}

    Loop -->|Next| CheckURL[Check URL with Streamlink]
    CheckURL --> Available{Streams Available?}

    Available -->|Yes| WasOffline{Previously Offline?}
    Available -->|No| WasOnline{Previously Online?}

    WasOffline -->|Yes| EmitOnline[Emit stream_online]
    WasOffline -->|No| Continue1[Continue]

    WasOnline -->|Yes| EmitOffline[Emit stream_offline]
    WasOnline -->|No| Continue2[Continue]

    EmitOnline --> UpdateState[Update Internal State]
    EmitOffline --> UpdateState
    Continue1 --> Loop
    Continue2 --> Loop

    UpdateState --> Loop
    Loop -->|Done| EmitComplete[Emit check_complete]
    EmitComplete --> ScheduleNext[Schedule Next Check]

    style Start fill:#007bff,color:#fff
    style EmitOnline fill:#28a745,color:#fff
    style EmitOffline fill:#dc3545,color:#fff
    style EmitComplete fill:#6c757d,color:#fff
```

### Status Change Detection

```mermaid
sequenceDiagram
    participant Timer
    participant Monitor
    participant SLS as Streamlink
    participant Tray
    participant User

    Timer->>Monitor: check()

    loop Each enabled stream
        Monitor->>SLS: streams(url)

        alt Stream online
            SLS-->>Monitor: {'best': Stream, '720p': Stream}
            Monitor->>Monitor: Compare with previous state

            alt Was offline → now online
                Monitor->>Tray: stream_online(stream)
                Note over Monitor,Tray: First detection

                Tray->>User: Desktop notification
                Tray->>Tray: Update icon (red)
                Tray->>Tray: Add to menu
            else Was online → still online
                Note over Monitor: No signal (no change)
            end

        else Stream offline
            SLS-->>Monitor: {}
            Monitor->>Monitor: Compare with previous state

            alt Was online → now offline
                Monitor->>Tray: stream_offline(stream)
                Note over Monitor,Tray: Went offline

                Tray->>Tray: Update icon (green if none online)
                Tray->>Tray: Remove from menu
            else Was offline → still offline
                Note over Monitor: No signal (no change)
            end
        end
    end
```

### Error Handling Flow

```mermaid
flowchart TD
    CheckStream[Check Stream] --> Try{Try}

    Try -->|Success| GetStreams[streams dict]
    Try -->|Exception| CatchError[Catch Exception]

    CatchError --> LogError[Log Debug Message]
    LogError --> MarkOffline[Mark as Offline]

    GetStreams --> HasStreams{Has Streams?}
    HasStreams -->|Yes| MarkOnline[Mark as Online]
    HasStreams -->|No| MarkOffline

    MarkOnline --> Return[Return Status]
    MarkOffline --> Return

    style Try fill:#ffc107,color:#000
    style CatchError fill:#dc3545,color:#fff
    style LogError fill:#ff6666,color:#fff
```

**Error Examples**:
- Network timeout → Mark offline
- Invalid URL → Mark offline
- Streamlink crash → Mark offline
- Plugin error → Mark offline

## Stream Launch Flow

### Complete Launch Sequence

```mermaid
sequenceDiagram
    participant User
    participant Menu
    participant Launcher
    participant Config
    participant Builder as Command Builder
    participant Process as subprocess.Popen
    participant SL as Streamlink
    participant Player

    User->>Menu: Click online stream
    Menu->>Launcher: launch(stream)
    activate Launcher

    Launcher->>Config: Get stream config
    Config-->>Launcher: stream_dict

    Launcher->>Config: Get global defaults
    Config-->>Launcher: defaults_dict

    Launcher->>Builder: Merge arguments
    activate Builder

    Builder->>Builder: Start with globals
    Builder->>Builder: Overlay stream-specific
    Builder->>Builder: Remove duplicates
    Builder->>Builder: Variable substitution
    Builder-->>Launcher: Merged args
    deactivate Builder

    Launcher->>Builder: Build command line
    Builder-->>Launcher: Full command string

    Launcher->>Process: Popen(shlex.split(cmd))
    activate Process

    Process->>SL: Execute streamlink
    activate SL

    SL->>SL: Parse URL
    SL->>SL: Extract streams
    SL->>SL: Select quality

    SL->>Player: Launch with stream URL
    activate Player

    Process-->>Launcher: Process started
    deactivate Process

    Launcher-->>Menu: Success
    deactivate Launcher

    Note over SL,Player: Detached processes<br/>continue independently

    deactivate SL
    deactivate Player
```

### Argument Merging Logic

```mermaid
flowchart TD
    Start[Start Launch] --> LoadGlobal[Load Global Args]
    LoadGlobal --> GlobalSL[default_streamlink_args]
    LoadGlobal --> GlobalPlayer[default_media_player_args]

    GlobalSL --> MergeSL[Merge with stream.sl_args]
    GlobalPlayer --> MergePlayer[Merge with stream.mp_args]

    MergeSL --> ParseSL[Parse Arguments]
    MergePlayer --> ParsePlayer[Parse Arguments]

    ParseSL --> DedupeSL[Remove Duplicates]
    ParsePlayer --> DedupePlayer[Remove Duplicates]

    DedupeSL --> VarSubSL[Variable Substitution]
    DedupePlayer --> VarSubPlayer[Variable Substitution]

    VarSubSL --> BuildCmd[Build Command]
    VarSubPlayer --> BuildCmd

    BuildCmd --> Final[Final Command Line]

    style Start fill:#007bff,color:#fff
    style BuildCmd fill:#28a745,color:#fff
    style Final fill:#ffc107,color:#000
```

**Example Merging**:
```python
# Global defaults
default_streamlink_args = "--retry-max 5 --retry-streams 3"
default_media_player_args = "--no-border"

# Stream-specific
stream.sl_args = "--retry-max 10 --title \"$SC.name\""
stream.mp_args = "--no-osc"

# Result after merge
streamlink_args = "--retry-streams 3 --retry-max 10 --title \"Streamer Name\""
player_args = "--no-border --no-osc"
```

**Deduplication Rule**: Last occurrence wins (stream overrides global).

### Variable Substitution

```mermaid
flowchart LR
    Input["--title \"$SC.name - $SC.type\""] --> Parse[Parse Variables]
    Parse --> Lookup[Lookup Values]

    Lookup --> Name[stream.name = 'StreamerName']
    Lookup --> Type[stream.type = 'twitch']

    Name --> Replace[Replace in String]
    Type --> Replace

    Replace --> Output["--title \"StreamerName - twitch\""]

    style Input fill:#e1f5e1,color:#000
    style Output fill:#e1f5e1,color:#000
```

**Available Variables**:
- `$SC.name` → Stream display name
- `$SC.type` → Platform type (twitch, youtube, etc.)

## Notification Flow

### Decision Tree for Notifications

```mermaid
flowchart TD
    StreamOnline[Stream Goes Online] --> CheckGlobal{Global Notify?}

    CheckGlobal -->|Disabled| NoNotify1[No Notification]
    CheckGlobal -->|Enabled| CheckStream{Stream Notify?}

    CheckStream -->|false| NoNotify2[No Notification]
    CheckStream -->|true| ShowNotify[Show Notification]
    CheckStream -->|null| ShowNotify

    ShowNotify --> CheckPlatform{Desktop Environment}

    CheckPlatform -->|Linux| LibNotify[libnotify]
    CheckPlatform -->|Windows| WinNotify[Windows Notifications]
    CheckPlatform -->|macOS| MacNotify[macOS Notifications]

    LibNotify --> Display[Display to User]
    WinNotify --> Display
    MacNotify --> Display

    style ShowNotify fill:#28a745,color:#fff
    style NoNotify1 fill:#dc3545,color:#fff
    style NoNotify2 fill:#dc3545,color:#fff
    style Display fill:#ffc107,color:#000
```

### Tristate Notification Logic

```python
def should_notify(global_notify: bool, stream_notify: bool | None) -> bool:
  """Determine if notification should be shown."""
  if stream_notify is not None:
    return stream_notify  # Explicit override
  return global_notify    # Use default
```

**Truth Table**:

| Global | Stream | Result | Reason |
|--------|--------|--------|--------|
| True   | True   | ✅ Notify | Explicit enable |
| True   | False  | ❌ Don't | Explicit disable |
| True   | None   | ✅ Notify | Use default |
| False  | True   | ✅ Notify | Explicit enable |
| False  | False  | ❌ Don't | Explicit disable |
| False  | None   | ❌ Don't | Use default |

## Favicon Loading Flow

### Complete Favicon Retrieval

```mermaid
sequenceDiagram
    participant UI
    participant Favicons
    participant Cache as Disk Cache
    participant Web as Web Server
    participant PIL

    UI->>Favicons: get_favicon(url, size)
    activate Favicons

    Favicons->>Favicons: Extract domain from URL
    Favicons->>Cache: Check ~/.cache/StreamCondor/favicons/{domain}_{size}.png

    alt Cache hit
        Cache-->>Favicons: PNG bytes
        Favicons->>Favicons: Load QPixmap
        Favicons-->>UI: Cached favicon
    else Cache miss
        Favicons->>Web: GET https://{domain}/
        Web-->>Favicons: HTML content

        Favicons->>Favicons: Parse HTML (BeautifulSoup)
        Favicons->>Favicons: Find <link rel="icon">

        alt Favicon found
            Favicons->>Web: GET {favicon_url}
            Web-->>Favicons: Image bytes
        else No favicon
            Favicons->>Favicons: Try /favicon.ico
            Favicons->>Web: GET https://{domain}/favicon.ico
            Web-->>Favicons: Image bytes
        end

        Favicons->>PIL: Open image
        PIL->>PIL: Resize to target size
        PIL->>PIL: Apply antialiasing
        PIL-->>Favicons: Resized image

        Favicons->>Cache: Save as PNG
        Favicons->>Favicons: Convert to QPixmap
        Favicons-->>UI: New favicon
    end

    deactivate Favicons
```

### Favicon URL Resolution

```mermaid
flowchart TD
    Start[Parse HTML] --> FindLink{<link rel="icon">?}

    FindLink -->|Found| CheckHref{Has href?}
    FindLink -->|Not found| Fallback[Try /favicon.ico]

    CheckHref -->|Yes| CheckAbsolute{Absolute URL?}
    CheckHref -->|No| Fallback

    CheckAbsolute -->|Yes| UseURL[Use href as-is]
    CheckAbsolute -->|No| JoinURL[Join with base URL]

    JoinURL --> UseURL
    UseURL --> Download[Download Image]
    Fallback --> Download

    Download --> Success{Downloaded?}
    Success -->|Yes| Resize[Resize Image]
    Success -->|No| UseDefault[Use Default Icon]

    Resize --> Cache[Save to Cache]
    Cache --> Return[Return QPixmap]
    UseDefault --> Return

    style Start fill:#007bff,color:#fff
    style Download fill:#ffc107,color:#000
    style Cache fill:#28a745,color:#fff
```

### Size Variants

```mermaid
flowchart LR
    Original[Original Favicon] --> Size16[Resize to 16x16]
    Original --> Size32[Resize to 32x32]
    Original --> Size64[Resize to 64x64]

    Size16 --> Cache16[Cache: domain_16.png]
    Size32 --> Cache32[Cache: domain_32.png]
    Size64 --> Cache64[Cache: domain_64.png]

    style Original fill:#17a2b8,color:#fff
    style Cache16 fill:#e1f5e1,color:#000
    style Cache32 fill:#e1f5e1,color:#000
    style Cache64 fill:#e1f5e1,color:#000
```

## Settings Update Flow

### Stream Tree Refresh

```mermaid
sequenceDiagram
    participant User
    participant Settings
    participant Config
    participant Tree as QTreeWidget
    participant Favicons

    User->>Settings: Open Settings
    Settings->>Config: get_streams()
    Config-->>Settings: streams[]

    Settings->>Settings: Group by type

    loop For each stream
        Settings->>Tree: Create QTreeWidgetItem
        Settings->>Favicons: get_favicon(stream.url, 16)
        Favicons-->>Settings: QPixmap icon
        Settings->>Tree: Set icon
        Settings->>Tree: Set text (name, url)
        Settings->>Tree: Set checkboxes (check, notify)
    end

    Settings->>Tree: Expand all groups
    Settings-->>User: Show window
```

### Stream Edit Propagation

```mermaid
flowchart TD
    Start[User Edits Stream] --> Dialog[Stream Dialog]
    Dialog --> Validate[Validate Input]

    Validate --> Valid{Valid?}
    Valid -->|No| ShowError[Show Error Message]
    ShowError --> Dialog

    Valid -->|Yes| UpdateConfig[Update Configuration]
    UpdateConfig --> SaveFile[Save to File]
    SaveFile --> EmitSignal[Emit stream_updated]

    EmitSignal --> UpdateTree[Settings: Refresh Tree]
    EmitSignal --> UpdateMenu[TrayIcon: Refresh Menu]
    EmitSignal --> RestartMonitor[Monitor: Restart Checks]

    UpdateTree --> Close[Close Dialog]
    UpdateMenu --> Close
    RestartMonitor --> Close

    style Start fill:#007bff,color:#fff
    style Validate fill:#ffc107,color:#000
    style SaveFile fill:#28a745,color:#fff
    style ShowError fill:#dc3545,color:#fff
```

## Performance Optimization

### Lazy Loading Strategy

```mermaid
flowchart TD
    Start[Component Initialization] --> CheckCache{Cache Valid?}

    CheckCache -->|Yes| UseCache[Use Cached Data]
    CheckCache -->|No| LoadData[Load Fresh Data]

    LoadData --> ProcessData[Process Data]
    ProcessData --> UpdateCache[Update Cache]
    UpdateCache --> UseCache

    UseCache --> Return[Return Data]

    style CheckCache fill:#ffc107,color:#000
    style UseCache fill:#28a745,color:#fff
    style LoadData fill:#17a2b8,color:#fff
```

**Lazy-Loaded Components**:
1. **Favicons** - Only loaded when displayed in UI
2. **Stream status** - Only checked for enabled streams
3. **Settings window** - Created on first open
4. **Dialogs** - Created on demand

### Caching Strategy

```mermaid
graph TB
    subgraph "In-Memory Cache"
        ConfigCache[Configuration Dict]
        FaviconCache[QPixmap Cache]
        StatusCache[Stream Status Dict]
    end

    subgraph "Disk Cache"
        ConfigFile[~/.config/StreamCondor.json]
        FaviconFiles[~/.cache/StreamCondor/favicons/]
    end

    ConfigCache -.write.-> ConfigFile
    ConfigFile -.read.-> ConfigCache

    FaviconCache -.write.-> FaviconFiles
    FaviconFiles -.read.-> FaviconCache

    StatusCache -.ephemeral.-> StatusCache

    style ConfigCache fill:#e1f5e1,color:#000
    style FaviconCache fill:#e1f5e1,color:#000
    style StatusCache fill:#e1f5e1,color:#000
```

**Cache Lifetimes**:
- **Configuration** - In-memory until app exit, auto-saved on change
- **Favicons** - On disk indefinitely, in memory until widget destroyed
- **Stream status** - In memory only, refreshed every check interval

---

For more details on specific components, see [Architecture Overview](architecture.md).
