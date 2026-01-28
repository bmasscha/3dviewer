import colorcet as cc
import numpy as np

def check(name):
    if hasattr(cc, name):
        p = getattr(cc, name)
        print(f"{name}: type={type(p)}, length={len(p)}", flush=True)
        if len(p) > 0:
            print(f"  element[0]: type={type(p[0])}, value={p[0]}", flush=True)
    else:
        print(f"{name}: NOT FOUND", flush=True)

check('glasbey')
check('glasbey_dark')
check('linear_kry_5_95_c72')
check('fire')
