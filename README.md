# yp
A reverse debugger for python based on rr

## How To Use

  git clone git@github.com:manuels/yp.git
  apt-get install rr
  echo 1 | sudo tee /proc/sys/kernel/perf_event_paranoid
  pip install -e ./yp
  yp record python3 my_python_script.py
  yp replay
  
