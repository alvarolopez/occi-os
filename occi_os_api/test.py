
import mox
from oslo.config import cfg
import testtools

from nova import rpc

CONF = cfg.CONF


class TestCase(testtools.TestCase):
    def setUp(self):
        super(TestCase, self).setUp()
        rpc.init(CONF)
        self.mox = mox.Mox()

    def tearDown(self):
        """
        Cleanup mocks.
        """
        super(TestCase, self).tearDown()
        self.mox.UnsetStubs()
