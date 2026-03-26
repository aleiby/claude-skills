---
name: godot
description: Communicate with a running Godot editor via the GodotMCP WebSocket plugin. Send commands to inspect scenes, read/write scripts, take screenshots, play/stop the game, and manipulate nodes.
---

# Godot Editor Communication

## Overview

Sends commands to the GodotMCP EditorPlugin's WebSocket server running inside Godot. The plugin must be installed and Godot must be open for this to work.

## Connection

| Detail | Value |
|--------|-------|
| Protocol | WebSocket |
| Host | `host.internal` (OrbStack bridge to macOS) |
| Port | `6550` (default) |
| Auth | None |

## Protocol

**Request:**
```json
{"id": "<unique-string>", "category": "<handler>", "command": "<cmd>", "params": {}}
```

**Response:**
```json
{"id": "<same-id>", "success": true, "data": {...}}
```

## Sending Commands

Use Node.js with the globally-installed `ws` module. Set `NODE_PATH` so the global module is found:

```bash
NODE_PATH=$(npm root -g) node -e "
const WebSocket = require('ws');
const ws = new WebSocket('ws://host.internal:6550');
const req = {id: '1', category: 'scene', command: 'get_current', params: {}};
ws.on('open', () => ws.send(JSON.stringify(req)));
ws.on('message', (d) => { console.log(d.toString()); ws.close(); process.exit(0); });
ws.on('error', (e) => { console.error(e.message); process.exit(1); });
setTimeout(() => { console.error('Timeout'); process.exit(1); }, 10000);
"
```

## Taking Screenshots

Use the helper script instead of raw WebSocket calls:

```bash
NODE_PATH=$(npm root -g) node tools/mcp_screenshot.js /tmp/screenshot.png
```

This tries the game bridge first, falls back to editor screenshot, and saves to the specified path. Then use `Read` tool to view the image.

For raw WebSocket screenshot commands, the `data` field contains a base64-encoded image and a `path` to where Godot saved it on macOS. Use `mac bash -c 'cat <path>'` to retrieve the file if needed.

## Available Commands

### project
| Command | Params | Description |
|---------|--------|-------------|
| `get_settings` | `section?`, `key?` | Read project settings |
| `list_files` | `path?`, `filter?`, `recursive?` | List project files |
| `read_file` | `path` | Read a file's content |
| `write_file` | `path`, `content` | Write a file |
| `get_uid` | `path` | Get UID for a resource path |
| `get_path_from_uid` | `uid` | Resolve UID to path |

### scene
| Command | Params | Description |
|---------|--------|-------------|
| `create` | `path`, `root_type`, `root_name?` | Create a new scene |
| `open` | `path` | Open a scene in the editor |
| `get_current` | | Get the currently open scene |
| `save` | `path?` | Save the current scene |
| `delete` | `path` | Delete a scene file |
| `instance` | `scene_path`, `parent_path`, `name?` | Instance a scene as child |
| `get_tree` | `path?` | Get the scene tree structure |
| `play` | `scene_path?` | Run the game (optionally specific scene) |
| `stop` | | Stop the running game |

### node
| Command | Params | Description |
|---------|--------|-------------|
| `add` | `parent_path`, `type`, `name` | Add a node |
| `delete` | `node_path` | Delete a node |
| `rename` | `node_path`, `new_name` | Rename a node |
| `duplicate` | `node_path`, `new_name?` | Duplicate a node |
| `move` | `node_path`, `new_parent_path` | Reparent a node |
| `get_properties` | `node_path` | Get all properties |
| `set_property` | `node_path`, `property`, `value` | Set a property |
| `get_signals` | `node_path` | List signals |
| `connect_signal` | `node_path`, `signal`, `target_path`, `method` | Connect a signal |
| `disconnect_signal` | `node_path`, `signal`, `target_path`, `method` | Disconnect a signal |
| `get_children` | `node_path` | List child nodes |

### script
| Command | Params | Description |
|---------|--------|-------------|
| `list` | `path?`, `language?` (`cs`/`gd`/`all`) | List scripts |
| `read` | `path` | Read script content |
| `create` | `path`, `content` | Create a script |
| `edit` | `path`, `content` | Edit a script |
| `attach` | `node_path`, `script_path` | Attach script to node |
| `detach` | `node_path` | Detach script from node |

### editor
| Command | Params | Description |
|---------|--------|-------------|
| `screenshot` | `viewport?` (`2d`/`3d`/`full`) | Capture editor viewport |
| `get_errors` | `count?` | Get recent error log |
| `execute_gdscript` | `code` | Execute GDScript in editor |
| `reload_project` | | Reload the project |
| `get_open_files` | | List open files in editor |
| `open_file` | `path`, `line?` | Open a file in editor |

### game (relayed to running game via GameBridge autoload)

These commands are forwarded through the editor to the game process. The game must be running (`scene.play` first) and the GameBridge autoload must be registered.

| Command | Params | Description |
|---------|--------|-------------|
| `screenshot` | | Capture the game viewport (returns base64 PNG in `data.image_base64`) |
| `get_scene_tree` | `depth?` | Get the live game scene tree with node positions |
| `get_node_properties` | `node_path` | Inspect any node's properties in the running game |
| `simulate_input` | `type`, ... | Inject input into the game (see below) |
| `get_performance` | | Get FPS, frame time, object counts, memory usage |

**Input simulation types** (all cross-platform, no OS APIs):

| `type` | Additional Params | Description |
|--------|-------------------|-------------|
| `action` | `action`, `pressed?` | Trigger an InputMap action |
| `key` | `key`, `pressed?` | Simulate a key press (uses Godot keycode names) |
| `mouse_motion` | `x`, `y` | Move the mouse to a position |
| `mouse_button` | `x?`, `y?`, `button?`, `pressed?` | Click at a position |

### runtime (editor-side, limited)
| Command | Params | Description |
|---------|--------|-------------|
| `get_scene_tree` | `depth?` | Editor's view of the scene tree (autoloads only when game is running) |
| `get_node_properties` | `node_path` | Inspect editor-side nodes |
| `capture_frame` | | Editor performance metrics |
| `monitor_property` | `node_path`, `property` | Sample a property over time |

## Building the C# Project

The .NET SDK is only available on macOS. Build with:

```bash
mac bash -lc 'dotnet build 2>&1'
```

## Troubleshooting

- **Connection refused**: Godot isn't running or the plugin isn't enabled. Check Editor > Project Settings > Plugins.
- **Timeout**: The WebSocket connected but Godot didn't respond. The editor may be busy (e.g., importing assets).
- **`MODULE_NOT_FOUND` for ws**: Run `npm install -g ws` and ensure `NODE_PATH=$(npm root -g)` is set.
