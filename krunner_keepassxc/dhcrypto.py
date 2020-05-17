import hmac
import math
import os

CRYPTOGRAPHY_MISSING = False
try:
	from cryptography.hazmat.backends import default_backend
	from cryptography.hazmat.primitives import hashes, padding
	from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
	from cryptography.hazmat.primitives.kdf.hkdf import HKDF
	from cryptography.utils import int_from_bytes
except:
	CRYPTOGRAPHY_MISSING = True


class dhcrypto:
	
	# A standard 1024 bits (128 bytes) prime number for use in Diffie-Hellman exchange
	DH_PRIME_1024_BYTES = (
		0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xC9, 0x0F, 0xDA, 0xA2, 0x21, 0x68, 0xC2, 0x34,
		0xC4, 0xC6, 0x62, 0x8B, 0x80, 0xDC, 0x1C, 0xD1, 0x29, 0x02, 0x4E, 0x08, 0x8A, 0x67, 0xCC, 0x74,
		0x02, 0x0B, 0xBE, 0xA6, 0x3B, 0x13, 0x9B, 0x22, 0x51, 0x4A, 0x08, 0x79, 0x8E, 0x34, 0x04, 0xDD,
		0xEF, 0x95, 0x19, 0xB3, 0xCD, 0x3A, 0x43, 0x1B, 0x30, 0x2B, 0x0A, 0x6D, 0xF2, 0x5F, 0x14, 0x37,
		0x4F, 0xE1, 0x35, 0x6D, 0x6D, 0x51, 0xC2, 0x45, 0xE4, 0x85, 0xB5, 0x76, 0x62, 0x5E, 0x7E, 0xC6,
		0xF4, 0x4C, 0x42, 0xE9, 0xA6, 0x37, 0xED, 0x6B, 0x0B, 0xFF, 0x5C, 0xB6, 0xF4, 0x06, 0xB7, 0xED,
		0xEE, 0x38, 0x6B, 0xFB, 0x5A, 0x89, 0x9F, 0xA5, 0xAE, 0x9F, 0x24, 0x11, 0x7C, 0x4B, 0x1F, 0xE6,
		0x49, 0x28, 0x66, 0x51, 0xEC, 0xE6, 0x53, 0x81, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
	)
	
	active = True

	aes_key = None
	pkey = None
	pubkey = None
	
	def __init__(self):
		if CRYPTOGRAPHY_MISSING:
			self.active = False
		else:

			self.DH_PRIME_1024 = int_from_bytes(self.DH_PRIME_1024_BYTES, 'big')

			self.pkey = int_from_bytes(os.urandom(0x80), 'big')
			self.pubkey = pow(2, self.pkey, self.DH_PRIME_1024)
	
	def int_to_bytes(self, number):
		return number.to_bytes(math.ceil(number.bit_length() / 8), 'big')
		
	def pubkey_as_list(self):
		return list(self.int_to_bytes(self.pubkey))

	def set_server_public_key(self, server_public_key):
		common_secret = pow(int_from_bytes(server_public_key, 'big'), self.pkey, self.DH_PRIME_1024)
		common_secret = self.int_to_bytes(common_secret)

		hkdf = HKDF(
			algorithm=hashes.SHA256(),
			length=16,
			salt=None,
			info=None,
			backend=default_backend()
		)
		self.aes_key = hkdf.derive(common_secret)

		
	def decryptMessage(self, result):
		aes_iv = bytes(result[1])

		encrypted_secret = bytes(result[2])

		cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(aes_iv), backend=default_backend())
		decryptor = cipher.decryptor()
		ct = decryptor.update(encrypted_secret) + decryptor.finalize()

		unpadder = padding.PKCS7(128).unpadder()
		unpadded_data = unpadder.update(ct)
		return unpadded_data.decode('utf-8')

	def encryptMessage(self, message):
		aes_iv = bytes(os.urandom(16))
		
		padder = padding.PKCS7(128).padder()
		message = message.encode('utf-8')
		padded_data = padder.update(message) + padder.finalize()

		cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(aes_iv), backend=default_backend())
		encryptor = cipher.encryptor()
		
		ct = encryptor.update(padded_data) + encryptor.finalize()
		return "", aes_iv, ct