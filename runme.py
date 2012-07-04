#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Starter script for Nova OCCI API."""

import eventlet
eventlet.monkey_patch(os=False)

import os
import sys


possible_topdir = os.path.normpath(os.path.join(os.path.abspath(
    sys.argv[0]), os.pardir, os.pardir))
if os.path.exists(os.path.join(possible_topdir, "nova", "__init__.py")):
    sys.path.insert(0, possible_topdir)


from nova import flags
from nova import log as logging
from nova import service
from nova import utils

if __name__ == '__main__':
    utils.default_flagfile()
    flags.FLAGS(sys.argv)
    logging.setup()
    utils.monkey_patch()
    server = service.WSGIService('occiapi')
    service.serve(server)
    service.wait()
