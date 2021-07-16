import sys
import gdb

import yp
from yp.gdb.utils import gdb_command, malloc, ExecDirection
from yp.gdb.breakpoints import INIT_FRAME_LINE, END_FRAME_LINE, CASE_TARGET_LIST, BreakpointGroup

gdbenv = yp.gdbenv

global instr_ub, instr_lb, instr_prev, f_lineno
instr_ub = -1
instr_lb = 0
instr_prev = -1
f_lineno = 0


def update_instruction_bounds(code, lasti):
    with malloc('sizeof(PyAddrPair)') as bounds:
        int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_lower) = 0'))
        int(gdb.parse_and_eval(f'(((PyAddrPair *) {bounds}).ap_upper) = 0'))

        lineno = int(gdb.parse_and_eval(f'_PyCode_CheckLineNumber({code}, {lasti}, {bounds})'))

        instr_lb = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_lower'))
        instr_ub = int(gdb.parse_and_eval(f'((PyAddrPair *) {bounds}).ap_upper'))

    return instr_lb, instr_ub, lineno


def is_at_new_line():
    global instr_ub, instr_lb, instr_prev, f_lineno

    frame: gdbenv.PyFrameObjectPtr = gdbenv.Frame.get_selected_python_frame().get_pyop()

    code = frame.co
    lasti = frame.f_lasti

    direction = ExecDirection.get_exec_direction()

    # If the last instruction executed isn't in the current
    # instruction window, reset the window.
    if lasti < instr_lb or lasti >= instr_ub:
        instr_lb, instr_ub, f_lineno = update_instruction_bounds(code.as_address(), lasti)

    # If the last instruction falls at the start of a line or if
    # it represents a jump backwards, update the frame's line
    # number and call the trace function.
    if    (direction.is_forward() and (lasti == instr_lb or lasti < instr_prev)) \
       or (direction.is_reverse() and (lasti == instr_lb or lasti > instr_prev)):
        filename = code.pyop_field('co_filename') or '?'
        func = code.pyop_field('co_name') or '?'
        location = (filename, func, f_lineno)
    else:
        location = None

    instr_prev = lasti
    return location


class NextInstrBreakpoint(gdb.Breakpoint):
    def __init__(self, location, brk_group):
        gdb.Breakpoint.__init__(self,
                                location,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.brk_group = brk_group
        self.silent = True
        self.enabled = False

    def stop(self):
        if not is_at_new_line():
            return False

        if self.enabled:
            # we might hit two breakpoints in a row because of NOP
            # just print the backtrace once here
            #print(f'py-bt {self.location}')
            gdb.execute('py-bt')

        self.brk_group.disable()

        return True


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self):
        gdb.Breakpoint.__init__(self,
                                INIT_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)

    def stop(self):
        global instr_ub, instr_lb, instr_prev, f_lineno
        instr_ub = -1
        instr_lb = 0
        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            instr_prev = -1
            f_lineno = 0
        else:
            instr_prev = sys.maxsize
            f_lineno = sys.maxsize
        return False


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self):
        gdb.Breakpoint.__init__(self,
                                END_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)

    def stop(self):
        global instr_ub, instr_lb, instr_prev, f_lineno
        instr_ub = -1
        instr_lb = 0
        if ExecDirection.get_exec_direction() == ExecDirection.REVERSE:
            instr_prev = -1
            f_lineno = 0
        else:
            instr_prev = sys.maxsize
            f_lineno = sys.maxsize
        return False


@gdb_command("py-step", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]
    brk_group += [InitStackFrameBreakpoint(), EndStackFrameBreakpoint()]
    brk_group.enable()

    gdb.execute('continue')


@gdb_command("py-reverse-step", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]
    brk_group += [InitStackFrameBreakpoint(), EndStackFrameBreakpoint()]
    brk_group.enable()

    gdb.execute('reverse-continue')
