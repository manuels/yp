import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
#log.setLevel(logging.DEBUG)
#log.debug = print

STACK = []

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


STEP_MODE = None

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
