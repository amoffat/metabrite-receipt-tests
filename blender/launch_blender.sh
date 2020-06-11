#!/bin/bash
blender/blender -b\
    -noaudio\
    receipt.blend\
    -P receipts.py\
    -- $@
