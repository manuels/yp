import logging

import yp.commands.step
from yp.commands.step import InstrState, is_at_new_line

log = logging.getLogger(__name__)

import gdb
from yp.gdb.breakpoints import INIT_FRAME_LINE, BreakpointGroup, CASE_TARGET_LIST
from yp.gdb.stack_frame import get_current_pyframe
from yp.gdb.utils import gdb_command, gdb_escape, py_string


class InitStackFrameBreakpoint(gdb.Breakpoint):
    def __init__(self, condition):
        gdb.Breakpoint.__init__(self,
                                INIT_FRAME_LINE,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=False)
        self.condition = condition

    def stop(self):
        v = gdb.parse_and_eval(self.condition)
        if v == 0:
            return False

        log.debug(f'stop InitStackFrameBreakpoint {get_current_pyframe()}')
        gdb.execute('py-bt')

        return True


class NextInstrBreakpoint(gdb.Breakpoint):
    def __init__(self, location, brk_group, state: InstrState, filename, lineno):
        gdb.Breakpoint.__init__(self,
                                location,
                                type=gdb.BP_BREAKPOINT,
                                wp_class=gdb.WP_WRITE,
                                internal=True)
        self.filename = filename
        self.lineno = lineno
        self.brk_group = brk_group
        self.state = state
        self.enabled = False

    def stop(self):
        location = not is_at_new_line(self.state)
        if not location:
            return False  # not at new line

        filename, func, lineno = location
        if filename != self.filename or lineno != self.lineno:
            return False

        if self.enabled:
            # we might hit two breakpoints in a row because of NOP
            # just print the backtrace once here
            #print(f'py-bt {self.location}')
            gdb.execute('py-bt')

        self.brk_group.disable()

        return True


@gdb_command("py-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_LOCATION)
def invoke(cmd, args, from_tty):
    try:
        filename, location = args.rstrip().rsplit(':')
    except ValueError:
        gdb.write('Expected py-break <script_file:lineno/function>\n')
        return

    try:
        lineno = int(location)
    except ValueError:
        func = location
        where = f'$_streq({gdb_escape(filename)}, {py_string("co.co_filename")})'
        where += f' && $_streq({gdb_escape(func)}, {py_string("co.co_name")})'
        brk = InitStackFrameBreakpoint(where)
    else:
        gdb.write('py-break only accepts function names (and no line numbers) right now.\n')

        state = InstrState()
        brk_group = BreakpointGroup()
        brk_group += [NextInstrBreakpoint(location, brk_group, state, filename, lineno) for location in CASE_TARGET_LIST]
        brk_group += [yp.commands.step.InitStackFrameBreakpoint(state),
                      yp.commands.step.EndStackFrameBreakpoint(state)]
        brk_group.enable()  # ATTENTION: is this correct?

        return
