import ctypes

def f():
  print('f1') # 6, 1
#  ctypes.string_at(0)
  print('f2') # 7, 2
  x = 1       # 8, 3
  return 1    # 9, 4

def g():
    print('g') #

def main():
  y = 2      # 1
  y = y + 1  # 2
  print(0)   # 3
  y = y + 2  # 4
  f()        # 5
  y = y + 3  # 6, 10
  print(1)   # 7, 11
  y = y + 4  # 8, 12
  g()        # 9, 13
  y = y + 5  # 10, 14
  print(y)   # 11, 15


if __name__ == '__main__':
  main()
  
print('EOF 00')

import dis
print(dis.dis(f))
print(dis.dis(g))
print(dis.dis(main))

