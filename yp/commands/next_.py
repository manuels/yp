import dataclasses
import sys
import gdb

import yp
from yp.commands.step import is_at_new_line, InstrState
from yp.gdb.utils import gdb_command, malloc, ExecDirection
from yp.gdb.breakpoints import INIT_FRAME_LINE, END_FRAME_LINE, CASE_TARGET_LIST, BreakpointGroup

gdbenv = yp.gdbenv


class NextInstrBreakpoint(gdb.Breakpoint):
    def __init__(self, location, brk_group, state, counter):
        gdb.Breakpoint.__init__(self,
                                location,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.brk_group = brk_group
        self.state = state
        self.silent = True
        self.enabled = False
        self.counter = counter

    def stop(self):
        if self.counter['stack_counter'] > 0 or not is_at_new_line(self.state):
            return False

        if self.enabled:
            # we might hit two breakpoints in a row because of NOP
            # just print the backtrace once here
            #print(f'py-bt {self.location}')
            gdb.execute('py-bt')

        self.brk_group.disable()

        return True


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, state: InstrState, counter):
        gdb.Breakpoint.__init__(self,
                                INIT_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.state = state
        self.counter = counter

    def stop(self):
        self.state.instr_ub = -1
        self.state.instr_lb = 0
        if ExecDirection.get_exec_direction() == ExecDirection.FORWARD:
            self.state.instr_prev = -1
            self.state.f_lineno = 0
            self.counter['stack_counter'] += 1
        else:
            self.state.instr_prev = sys.maxsize
            self.state.f_lineno = sys.maxsize
        self.counter['stack_counter'] -= 1
        return False


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, state, counter):
        gdb.Breakpoint.__init__(self,
                                END_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.state = state
        self.counter = counter

    def stop(self):
        self.state.instr_ub = -1
        self.state.instr_lb = 0
        if ExecDirection.get_exec_direction() == ExecDirection.REVERSE:
            self.state.instr_prev = -1
            self.state.f_lineno = 0
            self.counter['stack_counter'] -= 1
        else:
            self.state.instr_prev = sys.maxsize
            self.state.f_lineno = sys.maxsize
            self.counter['stack_counter'] += 1
        return False


@gdb_command("py-next", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    counter = dict(stack_counter=0)
    state = InstrState()
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group, state, counter) for location in CASE_TARGET_LIST]
    brk_group += [InitStackFrameBreakpoint(state, counter), EndStackFrameBreakpoint(state, counter)]
    brk_group.enable()  # ATTENTION: is this correct?

    gdb.execute('continue')


@gdb_command("py-reverse-next", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    counter = dict(stack_counter=0)
    state = InstrState()
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group, state, counter) for location in CASE_TARGET_LIST]
    brk_group += [InitStackFrameBreakpoint(state, counter), EndStackFrameBreakpoint(state, counter)]
    brk_group.enable()  # ATTENTION: is this correct?

    gdb.execute('reverse-continue')
