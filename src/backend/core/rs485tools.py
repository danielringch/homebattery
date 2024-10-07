from machine import Pin, UART
from rp2 import PIO, StateMachine, asm_pio

@asm_pio(autopull=True, pull_thresh=8, set_init=(PIO.OUT_LOW, PIO.OUT_LOW), sideset_init=PIO.OUT_HIGH, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT)
def uart_tx_18n1():
    pull()
    set(pins, 0b11).delay(7) # driver enable
    nop().delay(7)
    nop().delay(7)
    nop().delay(7)
    label("byteloop")
    set(y, 7).side(0).delay(7) # start bit
    label("bitloop")
    out(pins, 1).delay(6) # payload
    jmp(y_dec, "bitloop")
    nop().side(1).delay(6) # stop bit
    jmp(not_osre, "byteloop")
    nop().delay(7)
    set(pins, 0b00).delay(7) # driver disable
    label("end")
    jmp("end")


@asm_pio(autopull=True, pull_thresh=8, set_init=(PIO.OUT_LOW, PIO.OUT_LOW), sideset_init=PIO.OUT_HIGH, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT)
def uart_tx_18n2():
    pull()
    set(pins, 0b11).delay(7) # driver enable
    nop().delay(7)
    nop().delay(7)
    nop().delay(7)
    label("byteloop")
    set(y, 7).side(0).delay(7) # start bit
    label("bitloop")
    out(pins, 1).delay(6) # payload
    jmp(y_dec, "bitloop")
    nop().side(1).delay(6) # stop bit
    nop().delay(7)
    jmp(not_osre, "byteloop")
    nop().delay(7)
    set(pins, 0b00).delay(7) # driver disable
    label("end")
    jmp("end")


@asm_pio(autopull=True, pull_thresh=8, set_init=(PIO.OUT_LOW, PIO.OUT_LOW), sideset_init=PIO.OUT_HIGH, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT)
def uart_tx_18e1():
    pull()
    set(pins, 0b11).delay(7) # driver enable
    nop().delay(7)
    nop().delay(7)
    nop().delay(7)
    label("byteloop")
    set(y, 7).side(0).delay(4) # start bit
    mov(isr, null)
    mov(isr, isr)
    label("bitloop")
    out(x, 1)
    mov(pins, x).delay(3) # payload
    jmp(not_x, "jmpnop")
    mov(isr, invert(isr))
    label("cont")
    jmp(y_dec, "bitloop")
    nop()
    mov(pins, isr).delay(7) # parity
    nop().side(1).delay(6) # stop bit
    jmp(not_osre, "byteloop")
    nop().delay(7)
    set(pins, 0b00) # driver disable
    label("end")
    jmp("end")
    label("jmpnop")
    jmp("cont")


@asm_pio(autopull=True, pull_thresh=8, set_init=(PIO.OUT_LOW, PIO.OUT_LOW), sideset_init=PIO.OUT_HIGH, out_init=PIO.OUT_HIGH, out_shiftdir=PIO.SHIFT_RIGHT)
def uart_tx_18o1():
    pull()
    set(pins, 0b11).delay(7) # driver enable
    nop().delay(7)
    nop().delay(7)
    nop().delay(7)
    label("byteloop")
    set(y, 7).side(0).delay(4) # start bit
    mov(isr, null)
    mov(isr, invert(isr))
    label("bitloop")
    out(x, 1)
    mov(pins, x).delay(3) # payload
    jmp(not_x, "jmpnop")
    mov(isr, invert(isr))
    label("cont")
    jmp(y_dec, "bitloop")
    nop()
    mov(pins, isr).delay(7) # parity
    nop().side(1).delay(6) # stop bit
    jmp(not_osre, "byteloop")
    nop().delay(7)
    set(pins, 0b00) # driver disable
    label("end")
    jmp("end")
    label("jmpnop")
    jmp("cont")


def init_rs485(port_id: int, baud: int, bits: int, parity: int, stop: int, timeout: int, timeout_char: int):
    if port_id == 0:
        uart = UART(1, tx=None, rx=Pin(5), timeout=timeout, timeout_char=timeout_char)
    elif port_id == 1:
        uart = UART(0, tx=None, rx=Pin(13), timeout=timeout, timeout_char=timeout_char)
    else:
        raise Exception('Unknow port id: ', port_id)
    uart.init(baudrate=baud, bits=bits, parity=parity, stop=stop)

    if parity == 0:
        tx_func = uart_tx_18e1
    elif parity == 1:
        tx_func = uart_tx_18o1
    elif stop == 1:
        tx_func = uart_tx_18n1
    elif stop == 2:
        tx_func = uart_tx_18n2
    else:
        assert False

    if port_id == 0:
        sm = StateMachine(0, tx_func, freq=8 * baud, set_base=Pin(6), sideset_base=Pin(4), out_base=Pin(4))
    else:
        sm = StateMachine(5, tx_func, freq=8 * baud, set_base=Pin(14), sideset_base=Pin(12), out_base=Pin(12))

    return (uart, sm)