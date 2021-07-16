import gdb

from yp.commands.step import NextInstrBreakpoint
from yp.gdb.breakpoints import END_FRAME_LINE, CASE_TARGET_LIST, INIT_FRAME_LINE
from yp.gdb.utils import gdb_command, ExecDirection


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, next_instr_brk_list, counter):
        gdb.Breakpoint.__init__(self,
                                INIT_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.counter = counter
        self.next_instr_brk_list = next_instr_brk_list
        self.exec_direction = ExecDirection()

    def stop(self):
        if self.exec_direction.is_forward():
            start_frame(self.counter)
        else:
            end_frame(self, self.counter, self.next_instr_brk_list)
        return False


class EndStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, next_instr_brk_list, counter):
        gdb.Breakpoint.__init__(self,
                                END_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.counter = counter
        self.next_instr_brk_list = next_instr_brk_list
        self.exec_direction = ExecDirection()

    def stop(self):
        if self.exec_direction.is_forward():
            end_frame(self, self.counter, self.next_instr_brk_list)
        else:
            start_frame(self.counter)
        return False


def start_frame(counter):
    counter['stack_counter'] += 1


def end_frame(brk, counter, next_instr_brk_list):
    if counter['stack_counter'] == 0:
        for brk in next_instr_brk_list:
            brk.enabled = True
        brk.enabled = False
    counter['stack_counter'] -= 1


class NextInstrBreakpoint(NextInstrBreakpoint):
    def __init__(self, location, next_instr_brk_list):
        super(NextInstrBreakpoint, self).__init__(location)
        self.next_instr_brk_list = next_instr_brk_list

    def stop(self):
        res = super(NextInstrBreakpoint, self).stop()
        if res:
            for brk in self.next_instr_brk_list:
                brk.enabled = False
        return res


@gdb_command("py-finish", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    next_instr_brk_list = []
    lst = [NextInstrBreakpoint(location, next_instr_brk_list) for location in CASE_TARGET_LIST]
    next_instr_brk_list[:] = lst

    counter = dict(stack_counter=0)
    InitStackFrameBreakpoint(next_instr_brk_list, counter)
    EndStackFrameBreakpoint(next_instr_brk_list, counter)

    for brk in next_instr_brk_list:
        brk.enabled = False

    gdb.execute('continue')


@gdb_command("py-reverse-finish", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    next_instr_brk_list = []
    lst = [NextInstrBreakpoint(location, next_instr_brk_list) for location in CASE_TARGET_LIST]
    next_instr_brk_list[:] = lst

    counter = dict(stack_counter=0)
    InitStackFrameBreakpoint(next_instr_brk_list, counter)
    EndStackFrameBreakpoint(next_instr_brk_list, counter)

    for brk in next_instr_brk_list:
        brk.enabled = False

    gdb.execute('reverse-continue')
