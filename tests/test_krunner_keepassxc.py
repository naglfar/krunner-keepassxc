import unittest

from krunner_keepassxc import __version__
from krunner_keepassxc.dhcrypto import dhcrypto

class Tests(unittest.TestCase):

    def test_version(self):
        self.assertEqual(__version__, '1.0.0')

    def test_crypto(self):
        crypto1 = dhcrypto()
        crypto2 = dhcrypto()
        crypto1.set_server_public_key(crypto2.pubkey_as_list())
        crypto2.set_server_public_key(crypto1.pubkey_as_list())

        self.assertEqual(crypto1.aes_key, crypto2.aes_key)

        secret = "a secret message"
        result1 = crypto1.encryptMessage(secret)
        result2 = crypto2.decryptMessage(result1)
        self.assertEqual(result2, secret)

    def test_crypto_server(self):
        """
        keys
        147566589851476177870810964496093990934306790047078165572566230176527840758765675034603131144606182367924651223102171984891386850386435996534792108338145371539000265217100821932875981501307453173931859149567579535962260168103300170942754359672285525300978843650330965329270964780811226675432026346246133222303
        164230467356653606922423559802908377728996834007263510352224394641063801575952010268826445746182985516837916562687718863677429945387908863624420464850481869713818376415548626751974410461326141004646198388634983917959881458176760161383493455754970214337579235821486867280451394242765668071523386904795147174731
        public_key
        b'\xa1c\xa0\xa1nR\xce\xc7}\xc4;i\x05\x88J%\xf2.\xe4#\x80@N\x048\xfa \xb0\xb8l\xe3\x0e\xb5P\xee\xca`\x9f\xf0\x1f9\xd9f\xa3\xfc\xd5]\xc4\xe7\xbbX\xea!R\xd6\r\xb7]\xe7M=\xad\xb7\xa3\x95\x0b]\xf0\xbf\t\x86\xeaZ\xecZu\xb5\xbds\xc4\x95\x1fF"\x9d\xf79\x1d2\xb5\xcd\x89:\x91\xf4\xf3\xf7|W\x80\xfe#f\xb3P\x89\xebX\xce\x84\xb5\x8b\x83\xfd\x01\x06rl\x0fU\x92{\x86\x02\xecI\xc8#'
        decrypt
        b'\xc00\x9a\x8d\x98\xfeze\xd1\xf0E\xc0\xeczE\x88'
        b"\x9c'\xe3\xab\xef\x08\xd6r\xe2\x8e%\xda\xa3\xf5\xff\xbaU\x0b\x9eB\x8fS{?\rQq~\x862\\5"
        b'\x84m\\\xbd\xef1\xa7\x88\xd9\xfaV+\xc3%\xc3\x12\xfa\x04G\x1b!\xd5\xd2\x85*]\xb9[\xe84\xd6%'
        """

        crypto = dhcrypto()
        crypto.pkey = 147566589851476177870810964496093990934306790047078165572566230176527840758765675034603131144606182367924651223102171984891386850386435996534792108338145371539000265217100821932875981501307453173931859149567579535962260168103300170942754359672285525300978843650330965329270964780811226675432026346246133222303
        crypto.pubkey = 164230467356653606922423559802908377728996834007263510352224394641063801575952010268826445746182985516837916562687718863677429945387908863624420464850481869713818376415548626751974410461326141004646198388634983917959881458176760161383493455754970214337579235821486867280451394242765668071523386904795147174731

        crypto.set_server_public_key(b'\xa1c\xa0\xa1nR\xce\xc7}\xc4;i\x05\x88J%\xf2.\xe4#\x80@N\x048\xfa \xb0\xb8l\xe3\x0e\xb5P\xee\xca`\x9f\xf0\x1f9\xd9f\xa3\xfc\xd5]\xc4\xe7\xbbX\xea!R\xd6\r\xb7]\xe7M=\xad\xb7\xa3\x95\x0b]\xf0\xbf\t\x86\xeaZ\xecZu\xb5\xbds\xc4\x95\x1fF"\x9d\xf79\x1d2\xb5\xcd\x89:\x91\xf4\xf3\xf7|W\x80\xfe#f\xb3P\x89\xebX\xce\x84\xb5\x8b\x83\xfd\x01\x06rl\x0fU\x92{\x86\x02\xecI\xc8#')
        result = crypto.decryptMessage(('', b'\xc00\x9a\x8d\x98\xfeze\xd1\xf0E\xc0\xeczE\x88', b"\x9c'\xe3\xab\xef\x08\xd6r\xe2\x8e%\xda\xa3\xf5\xff\xbaU\x0b\x9eB\x8fS{?\rQq~\x862\\5"))

        self.assertEqual(result, 'kanji漢字かんじ')


if __name__ == '__main__':
    unittest.main()