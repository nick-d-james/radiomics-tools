#!/usr/bin/env python3
"""
---===[ nifti_to_pyrad: radiomics-tools ]===---
 Created on July 03, 2021
 Copyright 2021 - Nick D. James and Rebecca E. Thornhill
"""
import sys
import os
import numpy as np
from inspect import signature


def main(xxxx):
    pass


def usage():
    print("Usage: nifti_to_pyrad " + " ".join(signature(main).parameters))


if __name__ == "__main__":
    if len(sys.argv) - 1 != len(signature(main).parameters):
        usage()
    else:
        main(*sys.argv[1:])
