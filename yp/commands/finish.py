import gdb

from yp.commands.step import NextInstrBreakpoint
from yp.gdb.breakpoints import END_FRAME_LINE, CASE_TARGET_LIST, INIT_FRAME_LINE, BreakpointGroup
from yp.gdb.utils import gdb_command, ExecDirection


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, next_instr_brk_group, counter):
        gdb.Breakpoint.__init__(self,
                                INIT_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.counter = counter
        self.next_instr_brk_group = next_instr_brk_group
        self.exec_direction = ExecDirection()

    def stop(self):
        if self.exec_direction.is_forward():
            start_frame(self.counter)
        else:
            end_frame(self, self.counter, self.next_instr_brk_group)
        return False


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, next_instr_brk_group, counter):
        gdb.Breakpoint.__init__(self,
                                END_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.counter = counter
        self.next_instr_brk_group = next_instr_brk_group
        self.exec_direction = ExecDirection()

    def stop(self):
        if self.exec_direction.is_forward():
            end_frame(self, self.counter, self.next_instr_brk_group)
        else:
            start_frame(self.counter)
        return False


def start_frame(counter):
    counter['stack_counter'] += 1


def end_frame(brk, counter, next_instr_brk_group):
    if counter['stack_counter'] == 0:
        brk.enabled = False
        next_instr_brk_group.enable()
    counter['stack_counter'] -= 1


class NextInstrBreakpoint(NextInstrBreakpoint):
    def __init__(self, location, brk_group):
        super(NextInstrBreakpoint, self).__init__(location)
        self.brk_group = brk_group

    def stop(self):
        res = super(NextInstrBreakpoint, self).stop()
        if res:
            self.brk_group.disable()
        return res


@gdb_command("py-finish", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]

    counter = dict(stack_counter=0)
    InitStackFrameBreakpoint(brk_group, counter)
    EndStackFrameBreakpoint(brk_group, counter)

    brk_group.disable()

    gdb.execute('continue')


@gdb_command("py-reverse-finish", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]

    counter = dict(stack_counter=0)
    InitStackFrameBreakpoint(brk_group, counter)
    EndStackFrameBreakpoint(brk_group, counter)

    brk_group.disable()

    gdb.execute('reverse-continue')
