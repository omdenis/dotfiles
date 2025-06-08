#!/bin/bash

cd ~/apps/ffmpeg_build
mkdir -p bin
cd bin

curl -LO https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
cd ffmpeg-*-amd64-static

echo 'export PATH=$HOME/apps/ffmpeg-*-static:$PATH' >> ~/.bashrc
source ~/.bashrc
