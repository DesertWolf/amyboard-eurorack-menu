import time
import os

try:
    import ujson as json
except Exception:
    import json

import amyboard


# -----------------------------
# Configuration
# -----------------------------
DISPLAY_ROTATE = 90  # 0, 90, 180, 270 (used when sh1107 module is available)
INPUT_MODE = "auto"  # "demo", "adafruit", "twist", "auto", "computer", "midi", "hybrid"
CONTROL_SOURCE_OPTIONS = ("hybrid", "computer", "midi", "auto", "adafruit", "twist", "demo")
MIDI_UART_ID = 1
MIDI_BAUD = 31250
MIDI_RX_PIN = None
MIDI_TX_PIN = None
MIDI_NAV_CC = 20
MIDI_SELECT_CC = 21
MIDI_BACK_CC = 22
MIDI_NOTE_SELECT = 60
MIDI_NOTE_BACK = 61
MIDI_NOTE_UP = 62
MIDI_NOTE_DOWN = 63
CONFIG_PATH = "/user/current/perf_config.json"
STATE_PATH = "/user/current/menu_state.json"
PATCH_PROFILE_DIR = "/user/patches"
PATCH_PROFILE_FORMAT = "amyboard-menu-profile"
PATCH_PROFILE_VERSION = 1
DEFAULT_PRESET_SYNTH = 1
BUILTIN_PATCH_MIN = 0
BUILTIN_PATCH_MAX = 257
DEFAULT_CV_PITCH_INPUT = 0  # CV1 in
DEFAULT_CV_GATE_INPUT = 1  # CV2 in
DEFAULT_CV_GATE_ON = 1.2
DEFAULT_CV_GATE_OFF = 0.6
DEFAULT_CV_PITCH_SCALE = 12.0  # 1V/oct -> 12 semitones per volt
DEFAULT_CV_PITCH_OFFSET = 60.0  # 0V = MIDI note 60
DEFAULT_FILTER_TYPE = "LPF"
DEFAULT_FILTER_CUTOFF = 4000  # Hz, audible default


def get_filter_type_options():
    try:
        import amy
    except Exception:
        return ("LPF",)

    options = []
    if hasattr(amy, "FILTER_LPF"):
        options.append("LPF")
    if hasattr(amy, "FILTER_HPF"):
        options.append("HPF")
    if hasattr(amy, "FILTER_BPF"):
        options.append("BPF")
    if hasattr(amy, "FILTER_LPF24"):
        options.append("LPF24")

    if not options:
        return ("LPF",)
    return tuple(options)


FILTER_TYPE_OPTIONS = get_filter_type_options()


# -----------------------------
# Helpers
# -----------------------------
def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def is_dir(path):
    try:
        mode = os.stat(path)[0]
        return (mode & 0x4000) != 0
    except Exception:
        return False


def safe_read_json(path, default):
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception:
        return default


def safe_write_json(path, obj):
    try:
        with open(path, "w") as f:
            f.write(json.dumps(obj))
        return True
    except Exception:
        return False


def scan_patch_files(paths):
    out = []
    for p in paths:
        try:
            for ent in os.ilistdir(p):
                name = ent[0]
                full = p + "/" + name
                if name.endswith(".patch"):
                    out.append(full)
                elif is_dir(full):
                    # One level deep is enough for v1
                    try:
                        for sub in os.ilistdir(full):
                            subname = sub[0]
                            if subname.endswith(".patch"):
                                out.append(full + "/" + subname)
                    except Exception:
                        pass
        except Exception:
            pass
    out.sort()
    return out


def short_name(path):
    i = path.rfind("/")
    if i >= 0:
        return path[i + 1 :]
    return path


def deep_copy(value):
    if isinstance(value, dict):
        return {k: deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deep_copy(v) for v in value]
    return value


def merge_missing(dst, defaults):
    if not isinstance(dst, dict):
        dst = {}
    for k, v in defaults.items():
        if k not in dst:
            dst[k] = deep_copy(v)
        elif isinstance(v, dict):
            dst[k] = merge_missing(dst.get(k), v)
    return dst


def normalize_filter_type(value):
    if not isinstance(value, str):
        value = str(value)
    kind = value.upper().strip()
    if kind in ("LPF", "LOWPASS", "LOW-PASS"):
        return "LPF"
    if kind in ("HPF", "HIGHPASS", "HIGH-PASS"):
        return "HPF"
    if kind in ("BPF", "BANDPASS", "BAND-PASS"):
        return "BPF"
    if kind in ("LPF24", "LOWPASS24", "LOW-PASS24"):
        return "LPF24"
    return DEFAULT_FILTER_TYPE


def filter_type_to_amy_value(value):
    kind = normalize_filter_type(value)
    try:
        import amy
    except Exception:
        return None
    if kind == "HPF":
        return amy.FILTER_HPF
    if kind == "BPF":
        return amy.FILTER_BPF
    if kind == "LPF24":
        if hasattr(amy, "FILTER_LPF24"):
            return amy.FILTER_LPF24
        return amy.FILTER_LPF
    return amy.FILTER_LPF


# -----------------------------
# Display
# -----------------------------
class Display:
    def __init__(self, rotate=90):
        self.kind = "none"
        self.width = 128
        self.height = 128
        self._d = None

        # Try SH1107 direct driver first (rotation support)
        try:
            import sh1107

            i2c = amyboard.get_i2c()
            self._d = sh1107.SH1107_I2C(
                128, 128, i2c, address=0x3C, rotate=rotate
            )
            self.kind = "sh1107"
            return
        except Exception:
            pass

        # Fallback to amyboard display
        try:
            amyboard.init_display()
            self._d = amyboard.display
            self.kind = "amyboard"
            return
        except Exception:
            self.kind = "none"

    def clear(self):
        if self.kind == "none":
            return
        self._d.fill(0)

    def text(self, msg, x, y, color=255):
        if self.kind == "none":
            return
        s = str(msg)
        if self.kind == "sh1107":
            self._d.text(s, x, y, 1 if color else 0)
        else:
            self._d.text(s, x, y, color)

    def fill_rect(self, x, y, w, h, color):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.fill_rect(x, y, w, h, 1 if color else 0)
        else:
            self._d.fill_rect(x, y, w, h, color)

    def rect(self, x, y, w, h, color):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.rect(x, y, w, h, 1 if color else 0)
        else:
            self._d.rect(x, y, w, h, color)

    def refresh(self):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.show()
        else:
            amyboard.display_refresh()

    def bar(self, x, y, w, h, value, max_value=127):
        self.rect(x, y, w, h, 255)
        fill_w = int((clamp(value, 0, max_value) / float(max_value)) * (w - 2))
        if fill_w > 0:
            self.fill_rect(x + 1, y + 1, fill_w, h - 2, 255)


# -----------------------------
# Input events + drivers
# -----------------------------
class InputEvent:
    def __init__(self, delta=0, click=False, long_press=False, pressed=False):
        self.delta = delta
        self.click = click
        self.long_press = long_press
        self.pressed = pressed


class BaseInputDriver:
    name = "base"

    def poll(self, now_ms):
        return InputEvent()


class DemoInputDriver(BaseInputDriver):
    name = "demo"

    def __init__(self, step_ms=900):
        self.step_ms = step_ms
        self.last_ms = 0
        # Small repeating script to prove menu flow
        self.script = [
            ("delta", 1),
            ("delta", 1),
            ("click", True),
            ("delta", 1),
            ("delta", 1),
            ("click", True),
            ("delta", -1),
            ("long", True),
        ]
        self.idx = 0

    def poll(self, now_ms):
        if now_ms - self.last_ms < self.step_ms:
            return InputEvent()
        self.last_ms = now_ms
        kind, val = self.script[self.idx]
        self.idx = (self.idx + 1) % len(self.script)
        if kind == "delta":
            return InputEvent(delta=val)
        if kind == "click":
            return InputEvent(click=val)
        if kind == "long":
            return InputEvent(long_press=val)
        return InputEvent()

class ComputerInputDriver(BaseInputDriver):
    name = "computer"

    def __init__(self):
        self.queue = []
        self.enabled = False
        self.stdin = None
        self.poller = None

        try:
            import sys
            try:
                import uselect as select
            except Exception:
                import select
            self.stdin = sys.stdin
            self.poller = select.poll()
            self.poller.register(self.stdin, getattr(select, "POLLIN", 1))
            self.enabled = True
        except Exception:
            self.enabled = False

    def _parse_steps(self, parts, default=1):
        if len(parts) < 2:
            return default
        try:
            n = int(parts[1])
            if n < 1:
                return 1
            return n
        except Exception:
            return default

    def _parse_line(self, line):
        s = str(line).strip().lower()
        if not s:
            return []

        parts = s.split()
        cmd = parts[0]

        if cmd in ("up", "u", "k", "prev", "left"):
            return [InputEvent(delta=-self._parse_steps(parts, 1))]
        if cmd in ("down", "d", "j", "next", "right"):
            return [InputEvent(delta=self._parse_steps(parts, 1))]
        if cmd == "delta":
            if len(parts) < 2:
                return []
            try:
                n = int(parts[1])
            except Exception:
                return []
            if n == 0:
                return []
            return [InputEvent(delta=n)]
        if cmd in ("click", "select", "enter", "ok"):
            return [InputEvent(click=True)]
        if cmd in ("back", "long", "hold", "panic", "esc"):
            return [InputEvent(long_press=True)]
        return []

    def poll(self, now_ms):
        if self.queue:
            return self.queue.pop(0)
        if not self.enabled:
            return InputEvent()

        try:
            ready = self.poller.poll(0)
        except Exception:
            ready = []
        if not ready:
            return InputEvent()

        try:
            line = self.stdin.readline()
        except Exception:
            return InputEvent()
        if not line:
            return InputEvent()

        self.queue.extend(self._parse_line(line))
        if self.queue:
            return self.queue.pop(0)
        return InputEvent()


class MIDIInputDriver(BaseInputDriver):
    name = "midi"
    MAX_QUEUE = 48

    def __init__(self, channel_getter=None):
        self.channel_getter = channel_getter or (lambda: 1)
        self.queue = []
        self.running_status = None
        self.data = bytearray()
        self.enabled = False
        self.uart = None
        self.backend = "none"
        self._init_uart()

    def _init_uart(self):
        try:
            import machine

            kwargs = {"baudrate": MIDI_BAUD}
            if MIDI_RX_PIN is not None:
                kwargs["rx"] = machine.Pin(MIDI_RX_PIN)
            if MIDI_TX_PIN is not None:
                kwargs["tx"] = machine.Pin(MIDI_TX_PIN)
            self.uart = machine.UART(MIDI_UART_ID, **kwargs)
            self.enabled = True
            self.backend = "uart%d" % MIDI_UART_ID
            self.name = "midi:" + self.backend
        except Exception:
            self.enabled = False
            self.uart = None

    def _msg_len(self, status):
        hi = status & 0xF0
        if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            return 2
        if hi in (0xC0, 0xD0):
            return 1
        return 0

    def _target_channel(self):
        try:
            return clamp(int(self.channel_getter()), 1, 16)
        except Exception:
            return 1

    def _channel_match(self, status):
        return ((status & 0x0F) + 1) == self._target_channel()

    def _cc_to_delta(self, value):
        if value == 0 or value == 64:
            return 0
        if value == 1:
            return 1
        if value == 127:
            return -1
        if value < 64:
            return 1
        return -1

    def _emit_for_message(self, status, d1, d2):
        if not self._channel_match(status):
            return
        def push(ev):
            if len(self.queue) < self.MAX_QUEUE:
                self.queue.append(ev)

        typ = status & 0xF0
        if typ == 0x90 and d2 > 0:
            if d1 == MIDI_NOTE_UP:
                push(InputEvent(delta=-1))
            elif d1 == MIDI_NOTE_DOWN:
                push(InputEvent(delta=1))
            elif d1 == MIDI_NOTE_SELECT:
                push(InputEvent(click=True))
            elif d1 == MIDI_NOTE_BACK:
                push(InputEvent(long_press=True))
        elif typ == 0xB0:
            if d1 == MIDI_NAV_CC:
                delta = self._cc_to_delta(d2)
                if delta:
                    push(InputEvent(delta=delta))
            elif d1 == MIDI_SELECT_CC and d2 > 0:
                push(InputEvent(click=True))
            elif d1 == MIDI_BACK_CC and d2 > 0:
                push(InputEvent(long_press=True))

    def _feed_byte(self, b):
        if b & 0x80:
            if b >= 0xF8:  # real-time messages
                return
            if b >= 0xF0:
                self.running_status = None
                self.data = bytearray()
                return
            self.running_status = b
            self.data = bytearray()
            return

        if self.running_status is None:
            return

        need = self._msg_len(self.running_status)
        if need <= 0:
            self.data = bytearray()
            return

        self.data.append(b)
        while len(self.data) >= need:
            if need == 1:
                d1 = self.data[0]
                d2 = 0
                self.data = self.data[1:]
            else:
                d1 = self.data[0]
                d2 = self.data[1]
                self.data = self.data[2:]
            self._emit_for_message(self.running_status, d1, d2)

    def poll(self, now_ms):
        if self.queue:
            return self.queue.pop(0)
        if not self.enabled or self.uart is None:
            return InputEvent()

        try:
            raw = self.uart.read()
        except Exception:
            raw = None
        if raw:
            if isinstance(raw, int):
                raw = bytes([raw])
            for b in raw:
                self._feed_byte(b)

        if self.queue:
            return self.queue.pop(0)
        return InputEvent()


class CombinedInputDriver(BaseInputDriver):
    name = "combined"

    def __init__(self, drivers, name="combined"):
        self.drivers = [d for d in drivers if d is not None]
        self.name = name

    def poll(self, now_ms):
        out = InputEvent()
        active = False
        for d in self.drivers:
            ev = d.poll(now_ms)
            if ev.delta or ev.click or ev.long_press or ev.pressed:
                active = True
                out.delta += ev.delta
                out.click = out.click or ev.click
                out.long_press = out.long_press or ev.long_press
                out.pressed = out.pressed or ev.pressed
        if active:
            return out
        return InputEvent()


class AdafruitEncoderInputDriver(BaseInputDriver):
    name = "adafruit"
    SEESAW_ADDR_CANDIDATES = (0x36, 0x37, 0x49)
    SS_GPIO_BASE = 0x01
    SS_GPIO_DIRCLR_BULK = 0x03
    SS_GPIO_BULK_SET = 0x05
    SS_GPIO_PULLENSET = 0x0B
    SS_GPIO_BULK = 0x04
    SS_ENCODER_BASE = 0x11
    SS_ENCODER_POSITION = 0x30
    SS_BUTTON_PIN = 24

    def __init__(self, encoder_index=0, long_press_ms=650):
        self.encoder_index = encoder_index
        self.long_press_ms = long_press_ms

        self.last_pos = 0
        self.prev_pressed = False
        self.press_start = 0
        self.i2c = amyboard.get_i2c()
        self.seesaw_addr = None
        self.button_mask = 1 << self.SS_BUTTON_PIN

        try:
            devs = self.i2c.scan()
        except Exception:
            devs = []
        for addr in self.SEESAW_ADDR_CANDIDATES:
            if addr in devs:
                self.seesaw_addr = addr
                break

        if self.seesaw_addr is not None:
            try:
                # Configure seesaw button GPIO as input pull-up.
                self._ss_write_u32(self.SS_GPIO_DIRCLR_BULK, self.button_mask)
                self._ss_write_u32(self.SS_GPIO_PULLENSET, self.button_mask)
                self._ss_write_u32(self.SS_GPIO_BULK_SET, self.button_mask)
            except Exception:
                pass
            try:
                self.last_pos = self._ss_read_pos()
            except Exception:
                self.last_pos = 0
            return

        try:
            self.last_pos = amyboard.read_encoder(encoder=self.encoder_index)
        except Exception:
            self.last_pos = 0
        try:
            amyboard.init_buttons()
        except Exception:
            pass

    def _ss_write_u32(self, reg, value):
        self.i2c.writeto(
            self.seesaw_addr,
            bytes([self.SS_GPIO_BASE, reg]) + int(value).to_bytes(4, "big"),
        )

    def _ss_read(self, base, reg, n):
        self.i2c.writeto(self.seesaw_addr, bytes([base, reg]))
        time.sleep_ms(2)
        return self.i2c.readfrom(self.seesaw_addr, n)

    def _ss_read_pos(self):
        raw = self._ss_read(self.SS_ENCODER_BASE, self.SS_ENCODER_POSITION, 4)
        return int.from_bytes(raw, "big", True)

    def _get_pressed(self):
        if self.seesaw_addr is not None:
            try:
                bulk = int.from_bytes(self._ss_read(self.SS_GPIO_BASE, self.SS_GPIO_BULK, 4), "big")
                # Input pull-up: LOW means pressed.
                return (bulk & self.button_mask) == 0
            except Exception:
                return False
        try:
            b = amyboard.read_buttons()
            if isinstance(b, (tuple, list)) and len(b) > self.encoder_index:
                return bool(b[self.encoder_index])
        except Exception:
            pass
        return False

    def poll(self, now_ms):
        delta = 0
        click = False
        long_press = False

        try:
            if self.seesaw_addr is not None:
                p = self._ss_read_pos()
            else:
                p = amyboard.read_encoder(encoder=self.encoder_index)
            delta = p - self.last_pos
            self.last_pos = p
        except Exception:
            pass

        pressed = self._get_pressed()
        if pressed and not self.prev_pressed:
            self.press_start = now_ms
        elif (not pressed) and self.prev_pressed:
            dur = now_ms - self.press_start
            if dur >= self.long_press_ms:
                long_press = True
            else:
                click = True

        self.prev_pressed = pressed
        return InputEvent(delta=delta, click=click, long_press=long_press, pressed=pressed)


class TwistInputDriver(BaseInputDriver):
    name = "twist"

    REG_STATUS = 0x01
    REG_COUNT = 0x05

    def __init__(self, long_press_ms=650):
        self.long_press_ms = long_press_ms
        self.i2c = amyboard.get_i2c()
        self.addr = None
        self.prev_pressed = False
        self.press_start = 0
        self.last_count = 0

        devs = self.i2c.scan()
        if 0x3F in devs:
            self.addr = 0x3F
        elif 0x3E in devs:
            self.addr = 0x3E

        if self.addr is not None:
            self.last_count = self._read_i16(self.REG_COUNT)

    def _read_u8(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 1)
        return b[0]

    def _read_i16(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 2)  # little-endian
        v = b[0] | (b[1] << 8)
        if v & 0x8000:
            v -= 65536
        return v

    def poll(self, now_ms):
        if self.addr is None:
            return InputEvent()

        delta = 0
        click = False
        long_press = False
        pressed = False

        try:
            c = self._read_i16(self.REG_COUNT)
            delta = c - self.last_count
            self.last_count = c

            status = self._read_u8(self.REG_STATUS)
            pressed = (status & 0x02) != 0
            click = (status & 0x04) != 0
            self.i2c.writeto_mem(self.addr, self.REG_STATUS, b"\x00")
        except Exception:
            return InputEvent()

        if pressed and not self.prev_pressed:
            self.press_start = now_ms
        elif (not pressed) and self.prev_pressed:
            dur = now_ms - self.press_start
            if dur >= self.long_press_ms:
                long_press = True

        self.prev_pressed = pressed
        return InputEvent(delta=delta, click=click, long_press=long_press, pressed=pressed)


def make_input_driver(mode, midi_channel_getter=None):
    mode = (mode or "").lower()
    if mode == "demo":
        return DemoInputDriver()
    if mode == "computer":
        return ComputerInputDriver()
    if mode == "midi":
        return MIDIInputDriver(channel_getter=midi_channel_getter)
    if mode == "hybrid":
        return CombinedInputDriver(
            [
                ComputerInputDriver(),
                MIDIInputDriver(channel_getter=midi_channel_getter),
            ],
            name="hybrid",
        )
    if mode == "adafruit":
        return AdafruitEncoderInputDriver()
    if mode == "twist":
        return TwistInputDriver()
    # auto
    t = TwistInputDriver()
    if t.addr is not None:
        return t
    return AdafruitEncoderInputDriver()


# -----------------------------
# Pages
# -----------------------------
class PageBase:
    title = "Page"

    def __init__(self, app):
        self.app = app
        self.sel = 0
        self.editing = False

    def on_enter(self):
        pass

    def on_event(self, ev):
        pass

    def render(self, d):
        d.text(self.title, 0, 0, 255)


class PatchesPage(PageBase):
    title = "Patches"
    save_label = "[Save current]"

    def __init__(self, app):
        super().__init__(app)
        self.files = []
        self.offset = 0
    def _item_count(self):
        return 1 + len(self.files)

    def _item_label(self, idx):
        if idx == 0:
            return self.save_label
        return short_name(self.files[idx - 1])

    def refresh(self):
        try:
            amyboard.mount_sd()
        except Exception:
            pass
        self.files = scan_patch_files(["/user", "/sd"])
        max_idx = max(0, self._item_count() - 1)
        self.sel = clamp(self.sel, 0, max_idx)
        self.offset = clamp(self.offset, 0, max_idx)

    def on_enter(self):
        self.refresh()

    def on_event(self, ev):
        count = self._item_count()
        if ev.delta != 0:
            self.sel = clamp(self.sel + ev.delta, 0, max(0, count - 1))
            if self.sel < self.offset:
                self.offset = self.sel
            if self.sel >= self.offset + 6:
                self.offset = self.sel - 5
        if ev.click:
            if self.sel == 0:
                saved = self.app.save_patch_profile()
                if saved is None:
                    self.app.notice("Save failed")
                else:
                    self.refresh()
                    try:
                        self.sel = self.files.index(saved) + 1
                    except Exception:
                        self.sel = 0
                    if self.sel < self.offset:
                        self.offset = self.sel
                    if self.sel >= self.offset + 6:
                        self.offset = self.sel - 5
                    self.app.notice("Saved " + short_name(saved))
            elif len(self.files) > 0:
                p = self.files[self.sel - 1]
                status = self.app.load_patch_profile(p)
                if status == "loaded":
                    self.app.notice("Loaded " + short_name(p))
                elif status == "loaded_cfg_only":
                    self.app.notice("Loaded cfg;apply err")
                else:
                    self.app.notice("Load failed")
        if ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        d.text("Patches", 0, 0, 255)

        y = 16
        start = self.offset
        end = min(self._item_count(), start + 6)
        current = str(self.app.cfg.get("patches", {}).get("current", ""))
        for i in range(start, end):
            prefix = ">" if i == self.sel else " "
            name = self._item_label(i)
            if i > 0 and self.files[i - 1] == current:
                name = "*" + name
            d.text(prefix + name[:18], 0, y, 255)
            y += 16
        d.text("click:load/save", 0, 112, 160)

class PresetVoicePage(PageBase):
    title = "Preset Voice"
    fields = ["patch", "voices"]

    def _values(self):
        return self.app.cfg["preset_voice"]

    def on_event(self, ev):
        v = self._values()
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "patch":
                v[f] = clamp(int(v.get(f, BUILTIN_PATCH_MIN)) + ev.delta, BUILTIN_PATCH_MIN, BUILTIN_PATCH_MAX)
            elif f == "voices":
                v["num_voices"] = clamp(int(v.get("num_voices", 1)) + ev.delta, 1, 16)

        if ev.click:
            self.editing = False
            self.app.apply_preset_voice(save=True, show_notice=True)
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        v = self._values()
        patch = int(v.get("patch", BUILTIN_PATCH_MIN))
        voices = int(v.get("num_voices", 1))
        d.text("Preset Voice", 0, 0, 255)
        rows = [
            "patch:%d" % patch,
            "bank:%s" % self.app.patch_label(patch),
            "voices:%d" % voices,
            "CV1:pitch 1V/oct",
            "CV2:gate trig",
            "click:save",
        ]
        y = 16
        for i, row in enumerate(rows):
            marker = ">"
            star = " "
            if i < len(self.fields):
                marker = ">" if i == self.sel else " "
                star = "*" if self.editing and i == self.sel else " "
            d.text("%s%s %s" % (marker, star, row[:16]), 0, y, 255)
            y += 16


class FilterTypePage(PageBase):
    title = "Filt Type"

    def _values(self):
        return self.app._preset_values()

    def _selected_index(self):
        cur = normalize_filter_type(self._values().get("filter_type", DEFAULT_FILTER_TYPE))
        try:
            return FILTER_TYPE_OPTIONS.index(cur)
        except Exception:
            return 0

    def on_event(self, ev):
        if ev.delta != 0:
            idx = self._selected_index()
            idx = (idx + ev.delta) % len(FILTER_TYPE_OPTIONS)
            self._values()["filter_type"] = FILTER_TYPE_OPTIONS[idx]
            self.app.apply_filter_type(save=True, show_notice=True)
        if ev.click or ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        cur = normalize_filter_type(self._values().get("filter_type", DEFAULT_FILTER_TYPE))
        d.text("Filt Type", 0, 0, 255)
        d.text("Mode:%s" % cur, 0, 24, 255)
        y = 40
        for opt in FILTER_TYPE_OPTIONS:
            marker = ">" if opt == cur else " "
            d.text("%s %s" % (marker, opt), 0, y, 255)
            y += 16
        d.text("delta:change", 0, 112, 160)

class FilterCutoffPage(PageBase):
    title = "Filt Cut"

    def _values(self):
        return self.app._preset_values()

    def on_event(self, ev):
        if ev.delta != 0:
            p = self._values()
            step = 200 if p["filter_cutoff"] >= 2000 else 50
            p["filter_cutoff"] = clamp(p["filter_cutoff"] + ev.delta * step, 100, 12000)
            self.app.apply_filter_type(save=True, show_notice=True)
        if ev.click or ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        p = self._values()
        cutoff = p["filter_cutoff"]
        d.text("Filt Cutoff", 0, 0, 255)
        d.text("Freq:%dHz" % cutoff, 0, 24, 255)
        d.bar(0, 48, 128, 12, cutoff, 12000)
        d.text("delta:change", 0, 112, 160)

class VoiceModePage(PageBase):
    title = "Voice Mode"

    fields = ["polyphony", "unison", "detune", "spread"]

    def _values(self):
        return self.app.cfg["voice_mode"]

    def on_event(self, ev):
        v = self._values()
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        # editing
        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "polyphony":
                v[f] = clamp(v[f] + ev.delta, 1, 16)
            elif f == "unison":
                if ev.delta != 0:
                    v[f] = not v[f]
            elif f == "detune":
                v[f] = clamp(v[f] + ev.delta, 0, 100)
            elif f == "spread":
                v[f] = clamp(v[f] + ev.delta, 0, 100)
        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        d.text("Voice Mode", 0, 0, 255)
        v = self._values()
        y = 16
        for i, f in enumerate(self.fields):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            val = v[f]
            if isinstance(val, bool):
                val = "on" if val else "off"
            d.text("%s%s %s:%s" % (marker, star, f[:7], str(val)), 0, y, 255)
            y += 16


class CVRoutingPage(PageBase):
    title = "CV Routing"

    targets = [
        "none",
        "pitch",
        "filter",
        "amp",
        "macro1",
        "macro2",
        "macro3",
        "macro4",
    ]
    fields = ["input", "target", "amount", "polarity", "smooth"]

    def __init__(self, app):
        super().__init__(app)
        self.cv_idx = 0

    def _route(self):
        return self.app.cfg["cv_routing"]["routes"][self.cv_idx]

    def on_event(self, ev):
        r = self._route()

        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "input":
                self.cv_idx = (self.cv_idx + ev.delta) % 2
            elif f == "target":
                idx = self.targets.index(r["target"]) if r["target"] in self.targets else 0
                idx = (idx + ev.delta) % len(self.targets)
                r["target"] = self.targets[idx]
            elif f == "amount":
                r["amount"] = clamp(r["amount"] + ev.delta, -100, 100)
            elif f == "polarity":
                r["polarity"] = -1 if r["polarity"] > 0 else 1
            elif f == "smooth":
                r["smooth"] = clamp(r["smooth"] + ev.delta, 0, 100)

        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        r = self._route()
        d.text("CV Routing", 0, 0, 255)
        rows = [
            "input:CV%d" % (self.cv_idx + 1),
            "target:%s" % r["target"],
            "amount:%d" % r["amount"],
            "polarity:%s" % ("+" if r["polarity"] > 0 else "-"),
            "smooth:%d" % r["smooth"],
        ]
        y = 16
        for i, row in enumerate(rows):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            d.text("%s%s %s" % (marker, star, row[:18]), 0, y, 255)
            y += 16


class MacrosPage(PageBase):
    title = "Macros"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def on_event(self, ev):
        vals = self.app.cfg["macros"]["values"]
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % 4
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        if ev.delta != 0:
            vals[self.sel] = clamp(vals[self.sel] + ev.delta, 0, 127)
        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        vals = self.app.cfg["macros"]["values"]
        d.text("Macros", 0, 0, 255)
        y = 16
        for i in range(4):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            d.text("%s%s M%d %03d" % (marker, star, i + 1, vals[i]), 0, y, 255)
            d.bar(70, y, 56, 12, vals[i], 127)
            y += 16


class SystemPage(PageBase):
    title = "System"
    items = ["I2C Scan", "Control", "MIDI Ch", "Input", "Save", "Reload", "Panic"]

    def __init__(self, app):
        super().__init__(app)
        self.scan_cache = []
        self._control_before_edit = None

    def on_event(self, ev):
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.items)
            if ev.click:
                item = self.items[self.sel]
                if item == "I2C Scan":
                    try:
                        self.scan_cache = amyboard.get_i2c().scan()
                        self.app.notice("I2C: " + ",".join([hex(x) for x in self.scan_cache]))
                    except Exception:
                        self.app.notice("I2C scan error")
                elif item == "Control":
                    self._control_before_edit = self.app.cfg["system"]["control_source"]
                    self.editing = True
                elif item == "MIDI Ch":
                    self.editing = True
                elif item == "Input":
                    self.app.notice("Input: " + self.app.input_driver.name)
                elif item == "Save":
                    ok = self.app.save_cfg() and self.app.save_state()
                    self.app.notice("Saved" if ok else "Save failed")
                elif item == "Reload":
                    self.app.pages["patches"].refresh()
                    self.app.notice("Patches reloaded")
                elif item == "Panic":
                    self.app.panic()
            if ev.long_press:
                self.app.back_to_menu()
            return

        # editing control source
        if self.items[self.sel] == "Control":
            if ev.delta != 0:
                modes = self.app.control_sources
                cur = self.app.cfg["system"]["control_source"]
                idx = modes.index(cur) if cur in modes else 0
                idx = (idx + ev.delta) % len(modes)
                self.app.cfg["system"]["control_source"] = modes[idx]
            if ev.click:
                self.editing = False
                self.app.apply_control_source(
                    self.app.cfg["system"]["control_source"], save=True, show_notice=True
                )
            if ev.long_press:
                if self._control_before_edit is not None:
                    self.app.cfg["system"]["control_source"] = self._control_before_edit
                self.editing = False
                self.app.back_to_menu()
            return

        # editing MIDI channel
        if self.items[self.sel] == "MIDI Ch":
            if ev.delta != 0:
                ch = self.app.cfg["system"]["midi_channel"]
                self.app.cfg["system"]["midi_channel"] = clamp(ch + ev.delta, 1, 16)
            if ev.click:
                self.editing = False
                self.app.save_cfg()
            if ev.long_press:
                self.editing = False
                self.app.back_to_menu()

    def render(self, d):
        d.text("System", 0, 0, 255)
        y = 16
        for i, it in enumerate(self.items):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            line = it
            if it == "Control":
                line = "Control:%s" % self.app.cfg["system"]["control_source"]
            elif it == "MIDI Ch":
                line = "MIDI Ch:%d" % self.app.cfg["system"]["midi_channel"]
            elif it == "Input":
                line = "Input:%s" % self.app.input_driver.name
            d.text("%s%s %s" % (marker, star, line[:18]), 0, y, 255)
            y += 16


# -----------------------------
# App
# -----------------------------
DEFAULT_CFG = {
    "patches": {"current": ""},
    "preset_voice": {
        "synth": DEFAULT_PRESET_SYNTH,
        "patch": 0,
        "num_voices": 1,
        "filter_type": DEFAULT_FILTER_TYPE,
        "filter_cutoff": DEFAULT_FILTER_CUTOFF,
        "cv_pitch_input": DEFAULT_CV_PITCH_INPUT,
        "cv_gate_input": DEFAULT_CV_GATE_INPUT,
        "cv_gate_on": DEFAULT_CV_GATE_ON,
        "cv_gate_off": DEFAULT_CV_GATE_OFF,
        "cv_pitch_scale": DEFAULT_CV_PITCH_SCALE,
        "cv_pitch_offset": DEFAULT_CV_PITCH_OFFSET,
    },
    "voice_mode": {"polyphony": 6, "unison": False, "detune": 12, "spread": 18},
    "cv_routing": {
        "routes": [
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
        ]
    },
    "macros": {"values": [64, 64, 64, 64]},
    "system": {"midi_channel": 1, "control_source": INPUT_MODE},
}

DEFAULT_STATE = {"menu_index": 0, "current_page": "menu"}


class MenuApp:
    menu_items = ["Preset Voice", "Filt Type", "Filt Cut", "Patches", "Macros", "CV Routing", "Voice Mode", "System"]

    control_sources = list(CONTROL_SOURCE_OPTIONS)

    def __init__(self):
        self.cfg = merge_missing(deep_copy(safe_read_json(CONFIG_PATH, DEFAULT_CFG)), DEFAULT_CFG)
        self.state = merge_missing(deep_copy(safe_read_json(STATE_PATH, DEFAULT_STATE)), DEFAULT_STATE)
        self._normalize_cfg()

        self.display = Display(rotate=DISPLAY_ROTATE)
        self.input_driver = make_input_driver(
            self.cfg["system"]["control_source"], midi_channel_getter=self.get_midi_channel
        )

        self.pages = {
            "preset voice": PresetVoicePage(self),
            "filt type": FilterTypePage(self),
            "filt cut": FilterCutoffPage(self),
            "patches": PatchesPage(self),
            "macros": MacrosPage(self),
            "cv routing": CVRoutingPage(self),
            "voice mode": VoiceModePage(self),
            "system": SystemPage(self),
        }

        self.in_page = False
        self._gate_prev = False
        self._last_note = -1
        self.menu_index = clamp(self.state.get("menu_index", 0), 0, len(self.menu_items) - 1)
        self.notice_msg = ""
        self.notice_until = 0
        self.apply_preset_voice(save=False, show_notice=False)
    def _normalize_cfg(self):
        self.cfg = merge_missing(deep_copy(self.cfg), DEFAULT_CFG)
        try:
            midi_ch = int(self.cfg["system"].get("midi_channel", 1))
        except Exception:
            midi_ch = 1
        self.cfg["system"]["midi_channel"] = clamp(midi_ch, 1, 16)
        mode = str(self.cfg["system"].get("control_source", INPUT_MODE)).lower()
        if mode not in self.control_sources:
            mode = INPUT_MODE if INPUT_MODE in self.control_sources else "hybrid"
        self.cfg["system"]["control_source"] = mode
        cur = self.cfg.get("patches", {}).get("current", "")
        self.cfg["patches"]["current"] = str(cur) if cur is not None else ""
        return self.cfg

    def _ensure_dir(self, path):
        if is_dir(path):
            return True
        try:
            os.mkdir(path)
            return True
        except Exception:
            return False

    def _next_profile_path(self):
        i = 1
        while i < 1000:
            path = PATCH_PROFILE_DIR + "/profile%03d.patch" % i
            try:
                os.stat(path)
                i += 1
            except Exception:
                return path
        return PATCH_PROFILE_DIR + "/profile999.patch"

    def save_patch_profile(self):
        if not self._ensure_dir(PATCH_PROFILE_DIR):
            return None
        path = self._next_profile_path()
        payload = {
            "format": PATCH_PROFILE_FORMAT,
            "version": PATCH_PROFILE_VERSION,
            "cfg": deep_copy(self.cfg),
        }
        if not safe_write_json(path, payload):
            return None
        self.cfg["patches"]["current"] = path
        self.save_cfg()
        return path

    def load_patch_profile(self, path):
        raw = safe_read_json(path, None)
        if not isinstance(raw, dict):
            return "error"
        cfg = raw.get("cfg")
        if not isinstance(cfg, dict):
            cfg = raw
        if not isinstance(cfg, dict):
            return "error"

        self.cfg = merge_missing(deep_copy(cfg), DEFAULT_CFG)
        self._normalize_cfg()
        self.cfg["patches"]["current"] = path
        self.apply_control_source(
            self.cfg["system"]["control_source"], save=False, show_notice=False
        )
        applied = self.apply_preset_voice(save=False, show_notice=False)
        self.save_cfg()
        if applied:
            return "loaded"
        return "loaded_cfg_only"

    def _preset_values(self):
        p = self.cfg.get("preset_voice", {})
        if not isinstance(p, dict):
            p = {}
        try:
            synth = int(p.get("synth", DEFAULT_PRESET_SYNTH))
        except Exception:
            synth = DEFAULT_PRESET_SYNTH
        try:
            patch = int(p.get("patch", BUILTIN_PATCH_MIN))
        except Exception:
            patch = BUILTIN_PATCH_MIN
        try:
            num_voices = int(p.get("num_voices", 1))
        except Exception:
            num_voices = 1
        try:
            cv_pitch_input = int(p.get("cv_pitch_input", DEFAULT_CV_PITCH_INPUT))
        except Exception:
            cv_pitch_input = DEFAULT_CV_PITCH_INPUT
        try:
            cv_gate_input = int(p.get("cv_gate_input", DEFAULT_CV_GATE_INPUT))
        except Exception:
            cv_gate_input = DEFAULT_CV_GATE_INPUT
        p["synth"] = clamp(synth, 0, 31)
        p["patch"] = clamp(patch, BUILTIN_PATCH_MIN, BUILTIN_PATCH_MAX)
        p["num_voices"] = clamp(num_voices, 1, 16)
        p["cv_pitch_input"] = clamp(cv_pitch_input, 0, 1)
        p["cv_gate_input"] = clamp(cv_gate_input, 0, 1)
        try:
            gate_on = float(p.get("cv_gate_on", DEFAULT_CV_GATE_ON))
        except Exception:
            gate_on = DEFAULT_CV_GATE_ON
        try:
            gate_off = float(p.get("cv_gate_off", DEFAULT_CV_GATE_OFF))
        except Exception:
            gate_off = DEFAULT_CV_GATE_OFF
        if gate_on <= gate_off:
            gate_on = DEFAULT_CV_GATE_ON
            gate_off = DEFAULT_CV_GATE_OFF
        p["cv_gate_on"] = gate_on
        p["cv_gate_off"] = gate_off
        try:
            p["cv_pitch_scale"] = float(p.get("cv_pitch_scale", DEFAULT_CV_PITCH_SCALE))
        except Exception:
            p["cv_pitch_scale"] = DEFAULT_CV_PITCH_SCALE
        try:
            p["cv_pitch_offset"] = float(p.get("cv_pitch_offset", DEFAULT_CV_PITCH_OFFSET))
        except Exception:
            p["cv_pitch_offset"] = DEFAULT_CV_PITCH_OFFSET
        p["filter_type"] = normalize_filter_type(p.get("filter_type", DEFAULT_FILTER_TYPE))
        try:
            filter_cutoff = int(p.get("filter_cutoff", DEFAULT_FILTER_CUTOFF))
        except Exception:
            filter_cutoff = DEFAULT_FILTER_CUTOFF
        p["filter_cutoff"] = clamp(filter_cutoff, 100, 12000)
        self.cfg["preset_voice"] = p
        return p

    def patch_label(self, patch):
        p = int(patch)
        if p < 128:
            return "Juno-%03d" % p
        if p < 256:
            return "DX7-%03d" % (p - 128)
        if p == 256:
            return "Piano"
        if p == 257:
            return "WebBase"
        return "Patch-%d" % p

    def apply_cv_play_mapping(self):
       # CV is handled live in the run loop via cv_in()
       # No static routing API available on this firmware
        return True

    def apply_filter_type(self, save=False, show_notice=False):
        p = self._preset_values()
        kind = normalize_filter_type(p.get("filter_type", DEFAULT_FILTER_TYPE))
        p["filter_type"] = kind
        cutoff = int(p.get("filter_cutoff", DEFAULT_FILTER_CUTOFF))
        try:
            import amy

            amy.send(
                synth=p["synth"],
                osc=0,
                filter_type=filter_type_to_amy_value(kind),
                filter_freq=cutoff,
            )
            ok = True
        except Exception:
            print("Filter error:", e)
            ok = False

        if show_notice:
            if ok:
                self.notice("Filt:%s %dHz" % (kind, cutoff))
            else:
                self.notice("Filter err")
        if save:
            self.save_cfg()
        return ok

    def apply_preset_voice(self, save=False, show_notice=False):
        p = self._preset_values()
        ok = False
        try:
            import amy

            amy.send(
                synth=p["synth"],
                patch=p["patch"],
                num_voices=p["num_voices"],
            )
            ok = True
        except Exception:
            ok = False

        filter_ok = self.apply_filter_type(save=False, show_notice=False)
        cv_ok = self.apply_cv_play_mapping()
        if show_notice:
            if ok and filter_ok and cv_ok:
                self.notice("Preset %s ready" % self.patch_label(p["patch"]))
            elif ok and filter_ok:
                self.notice("Preset set; CV map err")
            elif ok:
                self.notice("Preset apply failed")
            else:
                self.notice("Preset apply failed")
        if save:
            self.save_cfg()
        return ok and filter_ok and cv_ok

    def get_midi_channel(self):
        try:
            return clamp(int(self.cfg["system"].get("midi_channel", 1)), 1, 16)
        except Exception:
            return 1

    def apply_control_source(self, mode, save=False, show_notice=False):
        m = str(mode).lower()
        if m not in self.control_sources:
            m = "hybrid"
        self.cfg["system"]["control_source"] = m
        self.input_driver = make_input_driver(m, midi_channel_getter=self.get_midi_channel)
        if show_notice:
            self.notice("Input: " + self.input_driver.name, 1200)
        if save:
            self.save_cfg()

    def save_cfg(self):
        return safe_write_json(CONFIG_PATH, self.cfg)

    def save_state(self):
        self.state["menu_index"] = self.menu_index
        self.state["current_page"] = "menu" if not self.in_page else self.menu_items[self.menu_index]
        return safe_write_json(STATE_PATH, self.state)

    def panic(self):
        try:
            import amy

            synth = int(self.cfg.get("preset_voice", {}).get("synth", DEFAULT_PRESET_SYNTH))
            amy.send(synth=synth, vel=0)
        except Exception:
            pass
        self.notice("PANIC")

    def notice(self, msg, ms=1500):
        self.notice_msg = msg
        self.notice_until = time.ticks_add(time.ticks_ms(), ms)

    def current_page(self):
        key = self.menu_items[self.menu_index].lower()
        return self.pages.get(key, None)

    def back_to_menu(self):
        self.in_page = False
        self.save_state()

    def handle_event(self, ev):
        # global long-press at top level = panic
        if (not self.in_page) and ev.long_press:
            self.panic()
            return

        if not self.in_page:
            if ev.delta != 0:
                self.menu_index = (self.menu_index + ev.delta) % len(self.menu_items)
            if ev.click:
                self.in_page = True
                p = self.current_page()
                if p:
                    p.on_enter()
            return

        p = self.current_page()
        if p:
            p.on_event(ev)

    def render_menu(self):
        d = self.display
        d.text("AMYboard Menu", 0, 0, 255)
        y = 16
        for i, item in enumerate(self.menu_items):
            marker = ">" if i == self.menu_index else " "
            d.text(marker + item[:18], 0, y, 255)
            y += 16
        d.text("click:enter long:panic", 0, 112, 160)

    def render(self):
        d = self.display
        d.clear()
        if not self.in_page:
            self.render_menu()
        else:
            p = self.current_page()
            if p:
                p.render(d)

        now = time.ticks_ms()
        if self.notice_msg and time.ticks_diff(self.notice_until, now) > 0:
            d.fill_rect(0, 96, 128, 16, 0)
            d.text(self.notice_msg[:21], 0, 112, 255)

        d.refresh()

    def run(self):
        last_save = time.ticks_ms()
        
        while True:
            now = time.ticks_ms()

            ev = self.input_driver.poll(now)
            if ev.delta or ev.click or ev.long_press:
                self.handle_event(ev)

            try:
                p = self._preset_values()
                pitch_v = amyboard.cv_in(p["cv_pitch_input"])
                gate_v = amyboard.cv_in(p["cv_gate_input"])
                note = int(pitch_v * p["cv_pitch_scale"] + p["cv_pitch_offset"])
                note = max(0, min(127, note))
                gate = gate_v > p["cv_gate_on"]
                import amy
                if gate and (not self._gate_prev or note != self._last_note):
                    amy.send(synth=p["synth"], note=note, vel=1)
                    self._last_note = note
                elif (not gate) and self._gate_prev:
                    amy.send(synth=p["synth"], vel=0)
                    self._last_note = -1
                self._gate_prev = gate
            except Exception:
                pass

            self.render()

            if time.ticks_diff(now, last_save) > 10000:
                self.save_state()
                last_save = now

            time.sleep_ms(35)


def main():
    amyboard.init_display()
    app = MenuApp()
    app.run()
