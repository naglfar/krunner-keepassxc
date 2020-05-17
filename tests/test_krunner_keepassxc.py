import unittest

from krunner_keepassxc import __version__
from krunner_keepassxc.dhcrypto import dhcrypto

class Tests(unittest.TestCase):

    def test_version(self):
        self.assertEqual(__version__, '1.0.0')

    def test_crypt(self):
        crypto1 = dhcrypto()
        crypto2 = dhcrypto()
        crypto1.set_server_public_key(crypto2.pubkey_as_list())
        crypto2.set_server_public_key(crypto1.pubkey_as_list())

        self.assertEqual(crypto1.aes_key, crypto2.aes_key)

        secret = "a secret message"
        result1 = crypto1.encryptMessage(secret)
        result2 = crypto2.decryptMessage(result1)
        self.assertEqual(result2, secret)

if __name__ == '__main__':
    unittest.main()