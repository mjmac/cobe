from halng.brain import Brain
from halng.tokenizer import MegaHALTokenizer
import os
import unittest

TEST_BRAIN_FILE = "hal.test_halng.brain"

class testInit(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_BRAIN_FILE):
            os.remove(TEST_BRAIN_FILE)

    def testInit(self):
        Brain.init(TEST_BRAIN_FILE)
        self.failUnless(os.path.exists(TEST_BRAIN_FILE),
                        "missing brain file after init")

        brain = Brain(TEST_BRAIN_FILE)
        self.failUnless(brain.order, "missing brain order after init")
        self.failUnless(brain._end_token_id,
                        "missing brain _end_token_id after init")

    def testInitWithOrder(self):
        order = 2
        Brain.init(TEST_BRAIN_FILE, order=order)

        brain = Brain(TEST_BRAIN_FILE)
        self.assertEqual(order, brain.order)

class testLearn(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_BRAIN_FILE):
            os.remove(TEST_BRAIN_FILE)

    def testLearn(self):
        Brain.init(TEST_BRAIN_FILE, order=2)
        brain = Brain(TEST_BRAIN_FILE)

        brain.learn("this is a test")
        brain.learn("this is also a test")

class testReply(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_BRAIN_FILE):
            os.remove(TEST_BRAIN_FILE)

        Brain.init(TEST_BRAIN_FILE, order=2)
        self._brain = brain = Brain(TEST_BRAIN_FILE)

        brain.learn("this is a test")
        brain.learn("this is also a test")
        brain.learn("this is a pretty great test thing")

    def testReply(self):
        self._brain.reply("this is a test")

if __name__ == '__main__':
    unittest.main()
