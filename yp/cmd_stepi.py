from yp.gdb_utils import gdb, gdb_command
from yp.yp_gdb import gdb, log, CASE_TARGET_LIST


class NextInstrBreakpoint(gdb.Breakpoint):
    def __init__(self, location):
        gdb.Breakpoint.__init__(self,
                                location,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.silent = True
        self.enabled = False

    def stop(self):
        # TODO print disassembler
        for brk in BREAKPOINTS:
            brk.enabled = False
        gdb.execute('py-bt')
        return True


BREAKPOINTS = [NextInstrBreakpoint(location) for location in CASE_TARGET_LIST]


@gdb_command("py-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    for brk in BREAKPOINTS:
        brk.enabled = True
    gdb.execute('continue')


@gdb_command("py-reverse-stepi", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    for brk in BREAKPOINTS:
        brk.enabled = True
    gdb.execute('reverse-continue')
