import collections
import sys
from pathlib import Path

sys.path.append(Path(__file__).absolute().parent.parent.__fspath__())

if __name__ == '__main__':
    import yp
    yp.gdb = gdb

    yp.gdbenv = collections.UserDict()
    vars = dict(locals())
    for k, v in vars.items():
        if not k.startswith('__'):
            setattr(yp.gdbenv, k, v)
    from yp.yp_gdb import *
    import yp.commands.step
    import yp.commands.stepi
