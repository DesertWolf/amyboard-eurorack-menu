# Development Guide

This document provides guidance for contributing to the AMYboard project and understanding the codebase.

## Project Structure

### Main Files
- **sketch.py** (5 lines): Entry point/bootloader for Tulip firmware
- **menu.py** (1200+ lines): Core application with all UI, input drivers, and logic
- **perf_config.json**: Hardware calibration and runtime configuration (auto-generated)
- **basesketch.py**: Hardware initialization (included in Tulip, not shown here)

### Documentation
- **README.md**: User-facing documentation, hardware requirements, usage guide
- **DEVELOPMENT.md**: This file - contributor and developer guide
- **CLAUDE.md**: Historical design notes and architecture overview

## Code Organization

### menu.py Sections

| Lines | Section | Purpose |
|-------|---------|---------|
| 1-50 | Imports & Constants | Configuration, display settings, MIDI mappings, file paths |
| 52-169 | Helper Functions | Utility functions (clamp, JSON I/O, file scanning, dict merging) |
| 171-265 | Display System | Display abstraction (SH1107 vs amyboard) |
| 267-350 | Input Events & BaseDriver | Event class and driver interface |
| 352-450 | DemoInputDriver | Hardcoded automation for testing |
| 452-550 | ComputerInputDriver | stdin-based input parsing |
| 552-750 | MIDIInputDriver | UART MIDI protocol implementation |
| 752-850 | CombinedInputDriver | Multi-driver merging |
| 852-1000 | AdafruitEncoderInputDriver | Seesaw I2C encoder driver |
| 1000-1100 | TwistInputDriver | Adafruit Twist I2C controller driver |
| 1100-1150 | make_input_driver() | Factory function with auto-detection |
| 1152-1500 | Page System | PageBase and all page classes (Patches, Preset, Voice, CV, Macros, System) |
| 1500-1700 | MenuApp Class | Main application, state management, event handling |
| 1700-1750 | Main Loop | run() method and main() entry point |

## Key Design Patterns

### Exception Handling
The codebase uses broad exception handling (`except Exception:`) throughout for robustness:
```python
try:
    # Hardware operation that may fail
    value = amyboard.cv_in(0)
except Exception:
    # Silent failure - continue gracefully
    pass
```
This is intentional for embedded systems where certain hardware may not be available.

### Configuration Management
- **Defaults**: Defined in `DEFAULT_CFG` dictionary
- **Merging**: `merge_missing()` recursively fills in missing keys without overwriting existing values
- **Persistence**: Config auto-saves every 10 seconds, explicitly via `save_cfg()`
- **State**: Menu position and current page saved to separate `menu_state.json`

### Page Lifecycle
```
User clicks on menu item
  ↓
Page.on_enter() called (initialize, refresh data)
  ↓
Main loop calls Page.on_event(ev) for each input event
  ↓
Main loop calls Page.render(display) to draw
  ↓
Long-press triggers Page exit back to menu
```

### Input Event Flow
```
InputDriver.poll() returns InputEvent
  ↓
MenuApp.handle_event() processes it
  ↓
Routes to current Page.on_event() if in page, or menu navigation
  ↓
State updated, render() called next frame
```

## MicroPython Compatibility

### Critical Limitations
1. **No f-strings**: Use `"value: %d" % value` instead of `f"value: {value}"`
2. **Limited JSON**: Must use `ujson` on MicroPython, fallback to `json` on full Python
3. **Limited Modules**: No `pathlib`, limited `os` support
4. **Memory**: Embedded devices have limited RAM; avoid large data structures
5. **No threads**: All code runs single-threaded in main loop

### Compatibility Checks
- Test with both standard Python and MicroPython when possible
- Use `try/except` for optional imports
- Avoid module features not available in MicroPython

## Hardware Integration

### I2C Device Detection
Devices are auto-discovered during initialization:
```python
i2c = amyboard.get_i2c()
devices = i2c.scan()  # Returns list of addresses
```

Available device libraries:
- `sh1107`: Display driver
- `machine.UART`: MIDI communication
- `amyboard`: Hardware abstraction (encoder, buttons, CV inputs, display)

### AMY Synthesizer Communication
```python
import amy

# Send note
amy.send(synth=1, note=60, vel=100)

# Stop note
amy.send(synth=1, vel=0)

# Important: Always include 'synth' parameter for reliable note-offs
```

## Testing Strategies

### Unit Testing Approach
Since this runs on embedded hardware, testing is primarily integration-based:

1. **Demo Mode**: Use `INPUT_MODE = "demo"` for automated menu navigation testing
2. **Computer Input**: Set `INPUT_MODE = "computer"` and pipe commands via stdin
3. **I2C Simulation**: Mock I2C responses for testing without hardware
4. **Log via notice()**: Use `self.app.notice(msg)` to display debug info on screen

### Computer Input Commands
```bash
# Navigation
echo "up\ndown\nclick\nback" | python sketch.py

# Delta operations
echo "delta 3" | python sketch.py
echo "delta -1" | python sketch.py

# Chaining
echo -e "up\nup\nclick\ndown\nclick" | python sketch.py
```

## Adding Features

### Adding a New Menu Page

1. **Create Page Class** (in menu.py, after existing pages):
```python
class MyNewPage(PageBase):
    title = "My Feature"
    fields = ["field1", "field2"]  # For editable fields
    
    def __init__(self, app):
        super().__init__(app)
        self.custom_state = None
    
    def on_enter(self):
        # Initialize page, load data, refresh UI state
        self.custom_state = self.app.cfg.get("my_feature", {})
    
    def on_event(self, ev):
        if not self.editing:
            # Navigation mode
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
        else:
            # Editing mode
            f = self.fields[self.sel]
            if ev.delta != 0:
                # Update value
                self.custom_state[f] = clamp(
                    self.custom_state[f] + ev.delta, 0, 127
                )
            if ev.click:
                self.editing = False
                self.app.save_cfg()
            if ev.long_press:
                self.editing = False
                self.app.back_to_menu()
    
    def render(self, d):
        d.text("My Feature", 0, 0, 255)
        y = 16
        for i, f in enumerate(self.fields):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            val = self.custom_state[f]
            d.text("%s%s %s:%d" % (marker, star, f, val), 0, y, 255)
            y += 16
```

2. **Add to MenuApp** (in menu.py, around line 1500):
```python
class MenuApp:
    menu_items = [
        "Preset Voice", "Patches", "Macros", "CV Routing", 
        "Voice Mode", "System", "My Feature"  # Add here
    ]
    
    def __init__(self):
        # ... existing code ...
        self.pages = {
            # ... existing pages ...
            "my feature": MyNewPage(self),  # Add here
        }
```

3. **Add to Config** (in `DEFAULT_CFG`):
```python
DEFAULT_CFG = {
    # ... existing config ...
    "my_feature": {
        "field1": 50,
        "field2": 25,
    }
}
```

### Adding a New Input Driver

1. **Create Driver Class**:
```python
class MyInputDriver(BaseInputDriver):
    name = "my_driver"
    
    def __init__(self):
        self.device = None
        try:
            # Initialize hardware
            self.device = initialize_my_hardware()
        except Exception:
            pass
    
    def poll(self, now_ms):
        if self.device is None:
            return InputEvent()
        
        try:
            delta = self.device.read_encoder()
            pressed = self.device.read_button()
            # Return appropriate InputEvent
            return InputEvent(delta=delta, click=pressed)
        except Exception:
            return InputEvent()
```

2. **Register in make_input_driver()**:
```python
def make_input_driver(mode, midi_channel_getter=None):
    # ... existing cases ...
    if mode == "my_driver":
        return MyInputDriver()
    # ...
```

3. **Add to CONTROL_SOURCE_OPTIONS**:
```python
CONTROL_SOURCE_OPTIONS = (
    "hybrid", "computer", "midi", "auto", "adafruit", "twist", "demo", "my_driver"
)
```

## Common Patterns

### Safe JSON I/O
```python
# Reading
config = safe_read_json(path, default_value)

# Writing
success = safe_write_json(path, data_dict)
```

### Value Clamping
```python
value = clamp(new_value, min_val, max_val)
```

### Deep Copying Config
```python
cfg_copy = deep_copy(self.cfg)  # Recursive copy of dicts/lists
```

### User Feedback
```python
# Display notice on screen for duration
self.app.notice("Operation complete", ms=1500)
```

## Performance Considerations

### Main Loop Timing
- Default sleep: 35ms (≈28 FPS for display)
- Input poll: Called every frame
- Config save: Every 10 seconds
- CV processing: Every frame

### Optimization Tips
1. Minimize JSON reads/writes (only when necessary)
2. Cache device handles (don't re-init every frame)
3. Use `clamp()` instead of min/max chaining
4. Avoid creating objects in main loop
5. Keep page render() methods simple

## Debugging

### Enable Notice Messages
```python
self.app.notice("Debug: value=%d" % value, ms=2000)
```

### Use Demo Mode for Testing
```python
INPUT_MODE = "demo"  # Automated menu navigation
```

### I2C Diagnostics
Use System → I2C Scan menu to identify connected devices and addresses.

### Serial Output
For Tulip firmware, serial output goes to the device console. Access via:
- Serial monitor (e.g., `screen /dev/ttyUSB0`)
- Tulip's web console
- Device logs

## Code Style

### Formatting
- Indentation: 4 spaces (not tabs)
- Line length: Keep under 100 characters when practical
- Comments: Explain *why*, not *what* (code shows what)

### Naming
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_CASE`
- Private members: `_prefix`

### Exception Handling
```python
# Preferred: Broad catch for robustness
try:
    result = operation()
except Exception:
    result = None

# Avoid: Bare except
try:
    result = operation()
except:
    pass
```

## Deployment Checklist

Before pushing to GitHub:
- [ ] Code runs without errors on target hardware
- [ ] No f-strings present
- [ ] All imports have fallbacks/try-except
- [ ] Configuration loads correctly
- [ ] State persists across power cycles
- [ ] All pages render without errors
- [ ] Input drivers function correctly
- [ ] CV inputs (if applicable) calibrated
- [ ] README updated with new features
- [ ] CHANGELOG entry added
- [ ] No debug/temporary code left in

## Resources

- **MicroPython Docs**: https://docs.micropython.org/
- **Tulip Firmware**: https://github.com/bzm3r/tulip
- **AMY Synthesizer**: https://github.com/shorepine/amy
- **Adafruit Libraries**: https://github.com/adafruit
- **I2C Debugging**: Use I2C scan feature in System menu

## Version Control

### Branch Strategy
- `main`: Stable, tested code
- `develop`: Active development
- Feature branches: `feature/description` for new features
- Bug fixes: `bugfix/description` for fixes

### Commit Messages
- Clear, descriptive messages
- Reference issues: "Fixes #123"
- Explain *why* in the body for complex changes
- Example: `Add CV routing: allows mapping analog inputs to synth params`

---

**Last Updated**: 2026-06-24  
**Maintained By**: AMYboard Contributors
