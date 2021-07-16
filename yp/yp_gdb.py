from pathlib import Path
import warnings
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
#log.setLevel(logging.DEBUG)
#log.debug = print

STACK = []

import yp
import gdb
gdbenv = yp.gdbenv

from yp.gdb.breakpoints import UserInitStackFrameBreakpoint
from yp.gdb.utils import gdb_command, gdb_escape, py_string

class NextInstrOptimizationWarning(RuntimeWarning):
    pass
    
warnings.simplefilter('once', NextInstrOptimizationWarning)

"""
@gdb_command("py-foo", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
#    print(get_pygdb_selected_frame())
#    print(get_pygdb_selected_frame().get_pyop())
    pyop = get_pygdb_selected_frame().get_pyop()
    filename = pyop.filename()
    lineno = pyop.current_line_num()
#    print(f'{filename}:{lineno}')
"""


def ceval_case_target_lines():
    contents = (Path(__file__).parent / 'ceval-py392.c').read_text().splitlines()
    lines = [l for i, l in enumerate(contents)]
    lineno_list = [i + 1 for i, l in enumerate(contents) if r'case TARGET(' in l]
    assert len(lineno_list) > 0
    return lineno_list

# these `case` statements are all in _PyEval_EvalFrameDefault:
CASE_TARGET_LIST = [f'../Python/ceval.c:{lineno}' for lineno in ceval_case_target_lines()]


STEP_MODE = None


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
    else:
        gdb.write('py-break only accepts function names (and no line numbers) right now.\n')
        return

    brk = UserInitStackFrameBreakpoint(where)

'''
@gdb_command("py-step-old", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'step'

    try:
        frame = PyStackFrame()
    except PyStackFrame.NoActiveFrame:
        gdb.write('No active python frame!\n')  # TODO set breakpoint and wait until we have one
        return

    STACK.append(frame)

    brk_args = OrderedDict(type=gdb.BP_BREAKPOINT,
                           wp_class=gdb.WP_WRITE,
                           internal=True,
                           temporary=True)

    if len(STACK) == 1:
        cleanup_list = []
        init_frame_brk = InitStackFrameBreakpoint(cleanup_list, *brk_args.values())
        next_instr_brk_list = [NextInstrBreakpoint(position, *brk_args.values()) for position in CASE_TARGET_LIST]
        end_frame_brk = EndStackFrameBreakpoint(cleanup_list, *brk_args.values())

        cleanup_list += [init_frame_brk, end_frame_brk] + next_instr_brk_list

    gdb.execute('continue')


@gdb_command("py-reverse-step-old", gdb.COMMAND_RUNNING, gdb.COMPLETE_NONE)
def invoke(cmd, args, from_tty):
    global STEP_MODE
    STEP_MODE = 'step'
    gdb.execute('reverse-continue')
'''
