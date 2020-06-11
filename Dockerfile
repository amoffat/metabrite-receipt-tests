FROM ubuntu:xenial

RUN apt-get update
RUN apt-get -y install locales

RUN locale-gen en_US.UTF-8  
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8 

RUN apt-get -y install\
    software-properties-common\
    curl\
    bzip2\
    blender\
    libspatialindex-dev\
    git


ARG uid=1000
ARG gid=1000
ENV user=ocr
ENV home=/home/$user

RUN groupadd -g $gid ocr\
    && useradd -m -u $uid -g $gid $user\
    && gpasswd -a $user sudo\
    && echo "$user:$user" | chpasswd

WORKDIR $home
USER $user

# install blender
RUN\
    curl -L https://download.blender.org/release/Blender2.78/blender-2.78c-linux-glibc219-x86_64.tar.bz2 | tar -xvj
RUN mv blender-2.78c-linux-glibc219-x86_64 blender

# set up our color profiles
ENV colormg $home/blender/2.78/datafiles/colormanagement
RUN\
    rm $colormg -rf\
    && git clone https://github.com/sobotka/filmic-blender.git $colormg

ENV pbin $home/blender/2.78/python/bin
RUN\
    curl https://bootstrap.pypa.io/get-pip.py > /tmp/get-pip.py\
    && $pbin/python3.5m /tmp/get-pip.py\
    && rm /tmp/get-pip.py

COPY blender/* ./
RUN $pbin/pip install -r requirements.txt

COPY --chown=$user:$user blender/launch_blender.sh .
RUN chmod +x launch_blender.sh

CMD ['/bin/bash', 'launch_blender.sh']
