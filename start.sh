#!/bin/sh
sed -i "s/PORT_PLACEHOLDER/$PORT/g" /etc/nginx/conf.d/default.conf
nginx -g 'daemon off;'
