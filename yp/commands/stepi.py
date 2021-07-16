import gdb
import logging
log = logging.getLogger(__name__)

from yp.gdb.utils import gdb_command
from yp.gdb.breakpoints import CASE_TARGET_LIST, BreakpointGroup


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
        if self.enabled:
            # TODO print bytecode
            gdb.execute('py-bt')
        self.brk_group.disable()
        return True


@gdb_command("py-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]
    brk_group.enable()

    gdb.execute('continue')


@gdb_command("py-reverse-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    brk_group = BreakpointGroup()
    brk_group += [NextInstrBreakpoint(location, brk_group) for location in CASE_TARGET_LIST]
    brk_group.enable()

    gdb.execute('reverse-continue')
