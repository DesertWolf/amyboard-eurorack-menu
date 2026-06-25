# Amyboard Project Guide

## Project Overview

Amyboard is a MicroPython-based menu system and UI framework for the AMY synthesizer. It runs on embedded hardware and provides:
- A navigable menu interface for configuring synthesizer parameters
- Multiple input driver backends (MIDI, computer keyboard, physical encoders, etc.)
- Patch profile management (save/load configurations)
- CV input handling for real-time pitch and gate control
- Display support for OLED screens (sh1107, amyboard native)

## Architecture & Components

### Core Files
- **menu.py** - Main application; contains all UI logic, input drivers, and configuration management
- **sketch.py** - Top-level entry point (calls `main()` from menu.py)
- **basesketch.py** - Base hardware initialization
- **perf_config.json** - Runtime configuration state (auto-generated)

### Key Classes & Modules

#### Display System (`Display` class)
- Abstracts display hardware (sh1107 vs amyboard)
- Methods: `clear()`, `text()`, `fill_rect()`, `rect()`, `bar()`, `refresh()`
- Handles rotation for sh1107 displays

#### Input Drivers (all extend `BaseInputDriver`)
- **DemoInputDriver** - Hardcoded automation script for testing
- **ComputerInputDriver** - Reads from stdin; supports commands like "up", "down", "click", "back"
- **MIDIInputDriver** - UART-based MIDI; customizable CC/note mappings
- **CombinedInputDriver** - Merges multiple drivers (e.g., computer + MIDI = "hybrid")
- **AdafruitEncoderInputDriver** - I2C seesaw-based encoder with button
- **TwistInputDriver** - I2C Adafruit Twist controller
- Auto-detection via `make_input_driver(mode, midi_channel_getter)`

#### Page System (all extend `PageBase`)
- **PresetVoicePage** - Load/edit synth patch, voices, CV mappings
- **PatchesPage** - Browse and load `.patch` files from `/user` or `/sd`
- **MacrosPage** - Edit 4 assignable macro values (0-127)
- **VoiceModePage** - Configure polyphony, unison, detune, spread
- **CVRoutingPage** - Map CV inputs to synth parameters (pitch, filter, macros, etc.)
- **SystemPage** - Control source selection, MIDI channel, I2C scanning, save/reload

#### Main App (`MenuApp` class)
- Initializes all pages, display, and input driver
- Manages state: current menu, current page, notice messages
- Main loop: `run()` → polls input → handles events → renders → CV processing
- Saves/loads config from `/user/current/perf_config.json` and menu state from `/user/current/menu_state.json`

## File Structure & Key Sections

### Configuration Constants (lines 11-36)
- Display rotation, input mode, MIDI settings
- Default file paths (config, patches, profiles)
- CV input defaults (pitch scale 1V/oct = 12 semitones/volt, offset 60 = MIDI C4)

### Helper Functions (lines 52-169)
- `clamp(v, lo, hi)` - Constrain value
- `is_dir(path)` - Check if path is directory (using os.stat mode bits)
- `safe_read_json()`, `safe_write_json()` - Graceful JSON I/O
- `scan_patch_files(paths)` - Recursively scan for `.patch` files (1 level deep)
- `short_name(path)` - Extract filename from path
- `deep_copy()` - Recursive dict/list copying
- `merge_missing()` - Merge config with defaults (non-destructive)

### Page Rendering & Navigation (lines 925-1092)
- Pages are navigated via encoder delta/clicks
- Click to enter edit mode (marked with `*`), click again to confirm
- Long press to exit back to menu
- Menu level: long press = PANIC (all notes off)

### Main Loop (lines 1090-1120)
```
while True:
  1. Poll input driver
  2. Handle events (navigate menu, edit values)
  3. Read CV inputs → convert to MIDI note → send to amy.send()
  4. Render display
  5. Periodic state save (every 10 seconds)
```

## Key Concepts

### Patch Profiles
- Stored as JSON files with metadata: `format`, `version`, `cfg`
- Auto-saved to `/user/patches/profileXXX.patch`
- Can load from `/user` or `/sd` (SD card)
- Current patch path tracked in `cfg["patches"]["current"]`

### CV Play
- CV1 input → pitch (0V = MIDI note 60, default 1V/octave)
- CV2 input → gate (threshold: on > 1.2V, off < 0.6V)
- Triggers `amy.send(synth=X, note=N, vel=1)` when gate rises
- Stops note on gate fall via `amy.send(synth=X, vel=0)`

### Control Sources
Valid modes: `"hybrid"`, `"computer"`, `"midi"`, `"auto"`, `"adafruit"`, `"twist"`, `"demo"`
- `"auto"` - Try Twist first, fallback to Adafruit encoder
- `"hybrid"` - Combine Computer + MIDI input

### Configuration Merging
- Defaults are applied non-destructively
- Missing keys are filled in; existing values preserved
- Happens on load and periodically during operation

## Common Tasks

### Add a New Menu Page
1. Create a class extending `PageBase`:
   ```python
   class MyPage(PageBase):
       title = "My Page"
       
       def on_enter(self): pass
       def on_event(self, ev): pass
       def render(self, d): pass
   ```
2. Add to `MenuApp.menu_items` list
3. Add instance to `MenuApp.pages` dict (use lowercase key)

### Modify Input Driver Behavior
- Edit `_parse_line()` for ComputerInputDriver (add commands)
- Edit MIDI constant assignments (e.g., `MIDI_NOTE_UP`, `MIDI_NAV_CC`)
- Adjust long-press thresholds: `long_press_ms` parameter (default 650ms)

### Change CV Mapping
- Edit `DEFAULT_CV_PITCH_SCALE` (semitones per volt, typically 12)
- Edit `DEFAULT_CV_PITCH_OFFSET` (MIDI note at 0V, typically 60 = C4)
- These are editable per-patch in PresetVoicePage

### Debug/Test with Computer Input
- Set `INPUT_MODE = "computer"` in config
- Run script and stdin reads commands: `up`, `down`, `delta N`, `click`, `back`, etc.
- Example: `echo "delta 2" | python sketch.py`

## Code Conventions

- **Exception handling**: Broad `except Exception` blocks; silent failures preferred for robustness
- **State management**: All app state lives in `cfg` dict + `state` dict; saved to JSON
- **UI feedback**: `notice(msg, ms)` displays overlay message for duration
- **Naming**: Methods starting with `_` are private/internal

## Important File Paths

| Path | Purpose |
|------|---------|
| `/user/current/perf_config.json` | Main config (patches, voice, macros, CV routing, system) |
| `/user/current/menu_state.json` | UI state (current menu index, page) |
| `/user/patches/profileXXX.patch` | Saved patch profiles |
| `/sd/` | SD card mount point (for patch scanning) |

## Testing & Debugging

- **Demo mode**: Set `INPUT_MODE = "demo"` for automated menu navigation
- **I2C Scan**: Use System page → "I2C Scan" to list connected devices
- **Panic**: Long-press at menu level sends `amy.send(vel=0)` to stop all notes
- **Log via notice()**: Use `self.app.notice(msg)` to debug in UI

---

**Last Updated**: 2026-06-23
