#!/bin/bash
xfce4-screenshooter --region --save /tmp/ss.png
xclip -selection clipboard -t image/png -i /tmp/ss.png


