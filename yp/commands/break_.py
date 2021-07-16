import logging
log = logging.getLogger(__name__)

import gdb
from yp.gdb.breakpoints import INIT_FRAME_LINE
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


@gdb_command("py-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_LOCATION)
def invoke(cmd, args, from_tty):
    try:
        filename, location = args.rstrip().rsplit(':')
    except ValueError:
        gdb.write('Expected py-break <script_file:lineno/function>\n')
        return

    where = f'$_streq({gdb_escape(filename)}, {py_string("co.co_filename")})'

    try:
        lineno = int(location)
    except ValueError:
        func = location
        where += f' && $_streq({gdb_escape(func)}, {py_string("co.co_name")})'
        brk = InitStackFrameBreakpoint(where)
    else:
        gdb.write('py-break only accepts function names (and no line numbers) right now.\n')
        return
