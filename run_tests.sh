#!/bin/bash

#set -e

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run Nova's test suite(s)"
  echo ""
  echo "  -N, --no-virtual-env     Don't use virtualenv.  Run tests in local environment"
  echo "  -s, --no-site-packages   Isolate the virtualenv from the global Python environment"
  echo "  -x, --stop               Stop running tests after the first error or failure."
  echo "  -f, --force              Force a clean re-build of the virtual environment. Useful when dependencies have been added."
  echo "  -p, --pep8               Just run pep8"
  echo "  -P, --no-pep8            Don't run pep8"
  echo "  -h, --help               Print this usage message"
  echo ""
  echo "Note: with no options specified, the script will try to run the tests in a virtual environment,"
  echo "      If no virtualenv is found, the script will ask if you would like to create one.  If you "
  echo "      prefer to run tests NOT in a virtual environment, simply pass the -N option."
  exit
}

function process_option {
  case "$1" in
    -h|--help) usage;;
    -N|--no-virtual-env) always_venv=0; never_venv=1;;
    -s|--no-site-packages) no_site_packages=1;;
    -f|--force) force=1;;
    -p|--pep8) just_pep8=1;;
    -P|--no-pep8) no_pep8=1;;
    -*) noseopts="$noseopts $1";;
    *) noseargs="$noseargs $1"
  esac
}

venv=.venv
installvenvopts=
always_venv=0
never_venv=0
force=0
no_site_packages=0
just_pep8=0
no_pep8=0
wrapper=""

for arg in "$@"; do
  process_option $arg
done

if [ $no_site_packages -eq 1 ]; then
  installvenvopts="--no-site-packages"
fi

function with_venv {
   ( source $venv/bin/activate && $@ )
}

function install_venv {
    virtualenv $venv $@ || exit 1
    with_venv pip install -r requirements.txt
    with_venv pip install -r test-requirements.txt
    # TODO(aloga): move this to test requirements
    with_venv pip install http://sourceforge.net/projects/pychecker/files/pychecker/0.8.19/pychecker-0.8.19.tar.gz/download
}

function run_pep8 {
  echo "Running pep8 ..."
  # Just run PEP8 in current environment
  #
  # NOTE(sirp): W602 (deprecated 3-arg raise) is being ignored for the
  # following reasons:
  #
  #  1. It's needed to preserve traceback information when re-raising
  #     exceptions; this is needed b/c Eventlet will clear exceptions when
  #     switching contexts.
  #
  #  2. There doesn't appear to be an alternative, "pep8-tool" compatible way of doing this
  #     in Python 2 (in Python 3 `with_traceback` could be used).
  #
  #  3. Can find no corroborating evidence that this is deprecated in Python 2
  #     other than what the PEP8 tool claims. It is deprecated in Python 3, so,
  #     perhaps the mistake was thinking that the deprecation applied to Python 2
  #     as well.
  pep8_opts="--ignore=W602 --repeat"
  ${wrapper} pep8 ${pep8_opts} ${srcfiles}
}

function run_tests {

    rm -rf build/html
    mkdir -p build/html

#    echo '\n PyLint report     \n****************************************\n'
#
#    $wrapper pylint -d W0511,I0011,E1101,E0611,F0401 -i y --report no **/*.py

    echo -e '\n Unittest coverage \n****************************************\n'

    nc -z localhost 8787
    if [ "$?" -ne 0 ]; then
      echo "Unable to connect to OCCI endpoint localhost 8787 - will not run
      system test."
      $wrapper nosetests --with-coverage --cover-erase --cover-package=occi_os_api --exclude=system
    else
      echo "Please make sure that the following line is available in nova.conf:"
      echo "allow_resize_to_same_host=True libvirt_inject_password=True enabled_apis=ec2,occiapi,osapi_compute,osapi_volume,metadata )"
    
      source ../devstack/openrc
      $wrapepr nova-manage flavor create --name=itsy --cpu=1 --memory=32 --flavor=98 --root_gb=1 --ephemeral_gb=1
      $wrapper nova-manage flavor create --name=bitsy --cpu=1 --memory=64 --flavor=99 --root_gb=1 --ephemeral_gb=1
      $wrapper nosetests --with-coverage --cover-erase --cover-package=occi_os_api
    fi
    
    echo -e '\n Issues report     \n****************************************\n'
    
    $wrapper pyflakes occi_os_api
    $wrapper vulture occi_os_api

    echo -e '\n Pychecker report  \n****************************************\n'
    
    $wrapper pychecker -# 99 occi_os_api/*.py occi_os_api/backends/*.py occi_os_api/nova_glue/*.py occi_os_api/extensions/*.py
    
    exit 0
}

if [ $never_venv -eq 0 ]
then
  # Remove the virtual environment if --force used
  if [ $force -eq 1 ]; then
    echo "Cleaning virtualenv..."
    rm -rf ${venv}
  fi
  if [ -e ${venv} ]; then
    wrapper=with_venv
  else
    if [ $always_venv -eq 1 ]; then
      # Automatically install the virtualenv
      install_venv $installvenvopts
      wrapper=with_venv
    else
      echo -e "No virtual environment found...create one? (Y/n) \c"
      read use_ve
      if [ "x$use_ve" = "xY" -o "x$use_ve" = "x" -o "x$use_ve" = "xy" ]; then
        # Install the virtualenv and run the test suite in it
        install_venv $installvenvopts
        wrapper=with_venv
      fi
    fi
  fi
fi

if [ $just_pep8 -eq 1 ]; then
    run_pep8
    exit
fi

run_tests

# TODO: create project!
#epydoc epydoc.prj

# Fix:
#tmetsch@ubuntu:~/devstack$ cat /etc/tgt/targets.conf
#include /etc/tgt/conf.d/cinder.conf
#
# in devstack/files/horizon_settings:
#HORIZON_CONFIG = {
# #'dashboards': ('nova', 'syspanel', 'settings',),
# 'dashboards': ('project', 'admin', 'settings',),
# 'default_dashboard': 'project',
#}
