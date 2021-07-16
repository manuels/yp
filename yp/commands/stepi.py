import gdb
import logging
log = logging.getLogger(__name__)

from yp.gdb.utils import gdb_command
from yp.gdb.breakpoints import CASE_TARGET_LIST


class NextInstrBreakpoint(gdb.Breakpoint):
    def __init__(self, location, next_instr_brk_list):
        gdb.Breakpoint.__init__(self,
                                location,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.next_instr_brk_list = next_instr_brk_list
        self.silent = True
        self.enabled = False

    def stop(self):
        # TODO print disassembler
        for brk in self.next_instr_brk_list:
            brk.enabled = False
        gdb.execute('py-bt')
        return True


@gdb_command("py-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    next_instr_brk_list = []
    lst = [NextInstrBreakpoint(location, next_instr_brk_list) for location in CASE_TARGET_LIST]
    next_instr_brk_list[:] = lst

    for brk in next_instr_brk_list:
        brk.enabled = True
    gdb.execute('continue')


@gdb_command("py-reverse-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    next_instr_brk_list = []
    lst = [NextInstrBreakpoint(location, next_instr_brk_list) for location in CASE_TARGET_LIST]
    next_instr_brk_list[:] = lst

    for brk in next_instr_brk_list:
        brk.enabled = True
    gdb.execute('reverse-continue')
