import hmac
import math
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.utils import int_from_bytes, int_to_bytes

#crypto from SecretStorage for testing
class dhcryptoss:
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
	
	DH_PRIME_1024 = int_from_bytes(DH_PRIME_1024_BYTES, 'big')

	active = True

	aes_key = None
	pkey = None
	pubkey = None

	def __init__(self):
		self.pkey = int_from_bytes(os.urandom(0x80), 'big')
		self.pubkey = pow(2, self.pkey, self.DH_PRIME_1024)

	def int_to_bytes(self, number):
		return number.to_bytes(math.ceil(number.bit_length() / 8), 'big')
		
	def pubkey_as_list(self):
		return list(int_to_bytes(self.pubkey))

	def set_server_public_key(self, server_public_key):
		from hashlib import sha256
		common_secret = pow(int_from_bytes(server_public_key, 'big'), self.pkey, self.DH_PRIME_1024)
		common_secret = self.int_to_bytes(common_secret)
		# Prepend NULL bytes if needed
		common_secret = b'\x00' * (0x80 - len(common_secret)) + common_secret
		# HKDF with null salt, empty info and SHA-256 hash
		salt = b'\x00' * 0x20
		pseudo_random_key = hmac.new(salt, common_secret, sha256).digest()
		output_block = hmac.new(pseudo_random_key, b'\x01', sha256).digest()
		# Resulting AES key should be 128-bit
		self.aes_key = output_block[:0x10]
		
	def decryptMessage(self, secret):
		aes = algorithms.AES(self.aes_key)
		aes_iv = bytes(secret[1])
		decryptor = Cipher(aes, modes.CBC(aes_iv), default_backend()).decryptor()
		encrypted_secret = secret[2]
		padded_secret = decryptor.update(bytes(encrypted_secret)) + decryptor.finalize()
		assert isinstance(padded_secret, bytes)
		return padded_secret[:-padded_secret[-1]].decode('utf-8')

	def encryptMessage(self, secret):
		if isinstance(secret, str):
			secret = secret.encode('utf-8')
		elif not isinstance(secret, bytes):
			raise TypeError('secret must be bytes')

		# PKCS-7 style padding
		padding = 0x10 - (len(secret) & 0xf)
		secret += bytes((padding,) * padding)
		aes_iv = os.urandom(0x10)
		aes = algorithms.AES(self.aes_key)
		encryptor = Cipher(aes, modes.CBC(aes_iv), default_backend()).encryptor()
		encrypted_secret = encryptor.update(secret) + encryptor.finalize()
		return "", aes_iv, encrypted_secret
	