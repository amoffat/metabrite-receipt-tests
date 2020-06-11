#!/bin/bash
THIS_DIR="`dirname \"$0\"`"
THIS_DIR="`( cd \"$THIS_DIR\" && pwd )`"

TARGET=/home/ocr
docker run -it --rm\
    -v $THIS_DIR/renders:$TARGET/renders\
    -v $THIS_DIR/tables:$TARGET/tables:ro\
    -v $THIS_DIR/receipts:$TARGET/receipts:ro\
    -v $THIS_DIR/hdris:$TARGET/hdris:ro\
    -v $THIS_DIR/fonts:$TARGET/fonts:ro\
    amoffat/receipts\
    /bin/bash launch_blender.sh\
    --output $TARGET/renders\
    $@
