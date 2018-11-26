#!/bin/sh -e
#
# This simple script to buildout slapos from source using 1.0 branch on 
# /opt/slapos folder, adapt this script as you please.  
#
# Be carefull to not run this script were the script is already installed.
# 
# Before run this script, ensure dependencies are installed, on debian, you can 
# use the command bellow:
#
# apt-get install python gcc g++ make uml-utilities bridge-utils patch wget
#

# Use sudo or superuser and create slapos directory (you can pick a different directory)
mkdir -p /opt/slapos/log/
cd /opt/slapos/

# Create buildout.cfg SlapOS bootstrap file
echo "[buildout]
extends = https://lab.nexedi.com/nexedi/slapos/raw/1.0/component/slapos/buildout.cfg
" > buildout.cfg

# Required in some distros such as Mandriva
unset PYTHONPATH
unset PYTHONDONTWRITEBYTECODE
unset CONFIG_SITE

#
# Bootstrap SlapOS, using forked version of buildout.
#
wget https://bootstrap.pypa.io/bootstrap-buildout.py
python -S bootstrap-buildout.py --buildout-version 2.5.2+slapos013 \
  -f http://www.nexedi.org/static/packages/source/slapos.buildout/

#
# Warning:Depending on your distribution you might need to
# replace python by python2 in the last command. This happens when your
# distribution considers that the standard python is the 3.x branch.
#
# Finally start to build

bin/buildout -v
