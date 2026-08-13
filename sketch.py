import sys
sys.path.append("/current")

# --- Safe mode: hold encoder button at boot to skip menu ---
_SAFE_MODE = False
try:
    import time
    import amyboard
    import sh1107

    _i2c = amyboard.get_i2c()
    _d = sh1107.SH1107_I2C(128, 128, _i2c, address=0x3C, rotate=90)
    _d.fill(0)
    _d.text("Hold btn: safe", 0, 0, 1)
    _d.text("mode in 4s...", 0, 16, 1)
    _d.show()

    # Check Adafruit seesaw button
    _SS_ADDR = None
    for _a in (0x36, 0x37, 0x49):
        if _a in _i2c.scan():
            _SS_ADDR = _a
            break

    _PIN = 24
    _MASK = 1 << _PIN
    if _SS_ADDR:
        _i2c.writeto(_SS_ADDR, bytes([0x01, 0x03]) + (int(_MASK)).to_bytes(4, "big"))
        _i2c.writeto(_SS_ADDR, bytes([0x01, 0x0B]) + (int(_MASK)).to_bytes(4, "big"))
        _i2c.writeto(_SS_ADDR, bytes([0x01, 0x05]) + (int(_MASK)).to_bytes(4, "big"))

    _deadline = time.ticks_add(time.ticks_ms(), 4000)
    while time.ticks_diff(_deadline, time.ticks_ms()) > 0:
        _held = False
        if _SS_ADDR:
            try:
                _i2c.writeto(_SS_ADDR, bytes([0x01, 0x04]))
                time.sleep_ms(2)
                _bulk = int.from_bytes(_i2c.readfrom(_SS_ADDR, 4), "big")
                _held = (_bulk & _MASK) == 0  # pull-up: LOW = pressed
            except Exception:
                pass
        if _held:
            _SAFE_MODE = True
            break
        time.sleep_ms(50)

    _d.fill(0)
    if _SAFE_MODE:
        _d.text("SAFE MODE", 0, 0, 1)
        _d.text("Thonny ready", 0, 16, 1)
    else:
        _d.text("Starting...", 0, 0, 1)
    _d.show()
    time.sleep_ms(500)

except Exception:
    pass  # If anything fails, just boot normally

if not _SAFE_MODE:
    import menu
    menu.main()

