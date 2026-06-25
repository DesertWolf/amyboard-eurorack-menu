# amyboard-eurorack-menu

A professional MicroPython menu system and UI framework for the AMY synthesizer running on AMYboard hardware (Tulip firmware). This project provides a navigable interface for configuring synthesizer parameters, managing patch profiles, and handling real-time CV input/MIDI control.

## Features

- **Navigable Menu Interface**: Intuitive hierarchical menu system for synthesizer parameter configuration
- **Multiple Input Drivers**: Support for various input backends including:
  - MIDI (via UART)
  - Adafruit Seesaw encoder (I2C)
  - Adafruit Twist controller (I2C)
  - Computer keyboard/stdin (for testing)
  - Hardware automation (demo mode)
  - Hybrid mode (combine multiple drivers)
  
- **Patch Profile Management**: Save and load complete synthesizer configurations
- **CV Control**: Real-time CV input handling for:
  - Pitch control (1V/octave default, configurable)
  - Gate/trigger input (adjustable threshold)
  - Macro mapping for modulation control
  
- **Display Support**: Compatible with SH1107 128×128 OLED displays (I2C)
- **MIDI Integration**: Full MIDI channel selection and CC/note mappings
- **Voice Mode Control**: Polyphony, unison mode, detune, and spread configuration
- **System Management**: I2C device scanning, panic control, save/reload functionality

## Hardware Requirements

### Minimum Setup
- **AMYboard** with Tulip MicroPython firmware
- **SH1107 OLED Display** (128×128 pixels, I2C address 0x3C)
- **Adafruit Seesaw Encoder** or **Adafruit Twist** controller (I2C)

### Optional Input Devices
- **MIDI USB Interface** or **DIN-5 MIDI** connection
- **CV Input Modules** (for real-time parameter control)
- **Macro Controllers** (any CV-capable hardware)

### I2C Addresses (Auto-Detected)
| Device | Address(es) |
|--------|------------|
| SH1107 Display | 0x3C |
| Adafruit Seesaw Encoder | 0x36, 0x37, 0x49 |
| Adafruit Twist | 0x3E, 0x3F |

### UART Configuration
- **UART ID**: 1 (configurable)
- **Baud Rate**: 31250 (MIDI standard)
- **RX/TX Pins**: Configurable per hardware setup

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/amyboard-eurorack-menu.git
   cd amyboard-eurorack-menu
   ```

2. **Upload to AMYboard**
   - Transfer `sketch.py`, `menu.py`, and `perf_config.json` to your Tulip device
   - Place `sketch.py` as the main bootloader
   - Create `/user/current/` directory on the device if it doesn't exist

3. **Directory Structure on Device**
   ```
   /
   ├── sketch.py              (bootloader)
   ├── menu.py               (main application)
   ├── basesketch.py         (hardware init)
   ├── perf_config.json      (calibration)
   └── /user/
       ├── /current/
       │   ├── perf_config.json (runtime config)
       │   └── menu_state.json  (UI state)
       ├── /patches/
       │   └── profileXXX.patch (saved profiles)
       └── /sd/               (SD card mount, optional)
   ```

## Quick Start

### Basic Operation
1. **Power on** the AMYboard - menu system initializes automatically
2. **Navigate** using encoder: rotate for up/down, click to enter/select
3. **Edit Values**: Click to enter edit mode (marked with `*`), rotate to adjust, click to confirm
4. **Exit/Back**: Long-press to return to previous menu or panic (stop all notes)

### Menu Structure
```
AMYboard Menu
├── Preset Voice    - Select patch, configure voices, set CV parameters
├── Patches         - Browse and load/save patch profiles
├── Macros          - Edit 4 assignable macro control values (0-127)
├── CV Routing      - Map CV inputs to synth parameters
├── Voice Mode      - Configure polyphony, unison, detune, spread
└── System          - I2C scan, control source, MIDI settings, save/reload
```

### Computer Input Mode (Testing)
Set `INPUT_MODE = "computer"` in `menu.py` and send commands via stdin:
```bash
# Navigation
echo "up" | python sketch.py
echo "down" | python sketch.py
echo "delta 5" | python sketch.py  # Delta by N steps

# Selection
echo "click" | python sketch.py
echo "back" | python sketch.py     # Long press (menu back/panic)
```

## Configuration

### Main Config File: `perf_config.json`

The configuration is automatically saved to `/user/current/perf_config.json` and includes:

```json
{
  "system": {
    "control_source": "auto",  // "hybrid", "computer", "midi", "auto", "adafruit", "twist", "demo"
    "midi_channel": 1           // 1-16
  },
  "preset_voice": {
    "patch": 0,                 // 0-257 (builtin patches)
    "num_voices": 1,            // 1-16
    "synth": 1,                 // Synth index
    "cv_pitch_input": 0,        // 0 = CV1
    "cv_gate_input": 1,         // 1 = CV2
    "cv_pitch_scale": 12.0,     // 12.0 = 1V/octave (semitones per volt)
    "cv_pitch_offset": 60.0,    // MIDI note at 0V (60 = C4)
    "cv_gate_on": 1.2,          // Gate high threshold (volts)
    "cv_gate_off": 0.6          // Gate low threshold (volts)
  },
  "voice_mode": {
    "polyphony": 6,
    "unison": false,
    "detune": 12,
    "spread": 18
  },
  "cv_routing": {
    "routes": [
      { "target": "none", "amount": 0, "polarity": 1, "smooth": 20 },
      { "target": "none", "amount": 0, "polarity": 1, "smooth": 20 }
    ]
  },
  "macros": {
    "values": [64, 64, 64, 64]
  },
  "patches": {
    "current": ""
  }
}
```

### Configuration Constants in `menu.py` (Lines 11-36)

```python
DISPLAY_ROTATE = 90           # 0, 90, 180, 270 for SH1107
INPUT_MODE = "auto"           # Default input driver mode
MIDI_UART_ID = 1              # UART port for MIDI
MIDI_BAUD = 31250             # Standard MIDI baud rate
MIDI_NAV_CC = 20              # CC for menu navigation
MIDI_SELECT_CC = 21           # CC for selection
MIDI_BACK_CC = 22             # CC for back/menu exit
DEFAULT_CV_PITCH_SCALE = 12.0 # Semitones per volt
DEFAULT_CV_PITCH_OFFSET = 60.0 # MIDI note at 0V
```

## Architecture

### Core Components

#### Display System (`Display` class)
- Abstracts hardware display backends (SH1107 vs amyboard native)
- Provides rendering interface: `clear()`, `text()`, `fill_rect()`, `bar()`, `refresh()`

#### Input Drivers (extend `BaseInputDriver`)
- **DemoInputDriver**: Hardcoded automation for testing
- **ComputerInputDriver**: stdin-based input for debugging
- **MIDIInputDriver**: UART-based MIDI with configurable mappings
- **AdafruitEncoderInputDriver**: I2C Seesaw-based encoder control
- **TwistInputDriver**: Adafruit Twist I2C controller
- **CombinedInputDriver**: Merges multiple drivers (hybrid mode)
- **Auto-detection**: `make_input_driver()` function automatically detects available hardware

#### Page System (extend `PageBase`)
Each page represents a configuration section:
- **PresetVoicePage**: Patch selection and voice configuration
- **PatchesPage**: Browse/load/save patch profiles
- **MacrosPage**: Edit 4 macro values with visual bars
- **CVRoutingPage**: Map CV inputs to parameters
- **VoiceModePage**: Polyphony and unison configuration
- **SystemPage**: System settings and diagnostics

#### Main Application (`MenuApp` class)
- Initializes display, input driver, and all pages
- Manages application state and configuration
- Runs main loop: poll input → handle events → render → process CV → sleep

### Main Loop Flow
```python
while True:
    1. Poll input driver for events
    2. Handle navigation/editing events
    3. Read CV inputs and convert to MIDI notes
    4. Send note-on/note-off commands to AMY
    5. Render display
    6. Periodic save (every 10 seconds)
    7. Sleep 35ms
```

### CV Play Implementation
- CV1 input → Pitch (0V = MIDI note 60 by default, adjustable)
- CV2 input → Gate (threshold-based triggering)
- Gate rising edge triggers `amy.send(note=N, vel=1)`
- Gate falling edge triggers `amy.send(vel=0)` to stop note

## Development

### Adding a New Page
```python
class MyPage(PageBase):
    title = "My Feature"
    
    def __init__(self, app):
        super().__init__(app)
        # Initialize state
    
    def on_enter(self):
        # Called when page is entered
        pass
    
    def on_event(self, ev):
        # Handle InputEvent (delta, click, long_press)
        pass
    
    def render(self, d):
        # Draw to display object d
        d.text("Title", 0, 0, 255)
```

### Important Code Conventions
- **No f-strings**: Use `%` formatting only (MicroPython compatibility)
- **Exception Handling**: Broad `except Exception` preferred for robustness
- **State Management**: All state lives in `cfg` dict, saved to JSON
- **Silent Failures**: Hardware errors are caught and logged via `notice()`
- **MIDI Note-Off**: Always include `synth` parameter in `amy.send()` calls

### Testing with Demo Mode
```python
INPUT_MODE = "demo"  # Enable automated menu navigation
# Script cycles through: up, up, click, up, up, click, down, long-press
```

## File Structure

| File | Purpose |
|------|---------|
| `sketch.py` | Entry point (bootloader) |
| `menu.py` | Main application (1200+ lines) |
| `perf_config.json` | Hardware calibration and runtime settings |
| `README.md` | This file |
| `LICENSE` | MIT License |

## Quirks & Known Issues

### MicroPython Limitations
- No f-string support: `"note:%d" % note` instead of `f"note:{note}"`
- Broad exception handling required due to firmware variations
- Limited JSON module (`ujson` preferred over standard `json`)

### Hardware Specifics
- **Gate Threshold**: Default ~1.2V on, ~0.6V off (hysteresis to prevent jitter)
- **CV Scale**: Default 1V/octave (12 semitones/volt) - adjustable per patch
- **Display Rotation**: Set to 90° by default; change `DISPLAY_ROTATE` if needed
- **MIDI**: Must include `synth` parameter in `amy.send()` for reliable note-offs

### Input Driver Priority (Auto Mode)
1. Try Adafruit Twist (0x3E/0x3F)
2. Fallback to Adafruit Seesaw (0x36/0x37/0x49)

## Contributing

Contributions are welcome! Please:
1. Follow existing code style and conventions
2. Test on actual hardware when possible
3. Maintain MicroPython compatibility (no f-strings, etc.)
4. Document hardware-specific configurations
5. Update this README for new features

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Support & Resources

- **AMY Synthesizer**: https://github.com/shorepine/amy
- **Tulip Firmware**: https://github.com/bzm3r/tulip
- **Adafruit Hardware**: https://learn.adafruit.com/

## Changelog

### v1.0.0 (2026-06-24)
- Initial release
- Full menu system implementation
- Multi-driver input support
- Patch profile management
- CV play and routing
- MIDI integration
- System diagnostics

---

**Last Updated**: 2026-06-24  
**Status**: Active Development  
**Python Version**: MicroPython 3.x
