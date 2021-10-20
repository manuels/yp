import collections
import sys
from pathlib import Path

sys.path.append(Path(__file__).absolute().parent.parent.__fspath__())

if __name__ == '__main__':
    import yp

    yp.gdbenv = collections.UserDict()
    vars = dict(locals())
    for k, v in vars.items():
        if not k.startswith('__'):
            setattr(yp.gdbenv, k, v)

    import yp.yp_gdb
    import yp.commands.step
    import yp.commands.stepi
    import yp.commands.break_
    import yp.commands.next_
    import yp.commands.finish

    # TODO: run 'set prompt (yp) '