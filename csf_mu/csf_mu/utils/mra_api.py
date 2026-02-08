import base64
import json
import os
from datetime import timedelta

import frappe
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from frappe.utils import get_datetime, get_site_path, now_datetime


MRA_DATETIME_FORMAT = "%Y%m%d %H:%M:%S"
TOKEN_REFRESH_BUFFER = timedelta(minutes=10)
DEFAULT_TIMEOUT = 60


def _resolve_file_path(file_url):
	if not file_url:
		return None
	if file_url.startswith("/private/files/"):
		filename = file_url.replace("/private/files/", "", 1)
		return get_site_path("private", "files", filename)
	if file_url.startswith("/files/"):
		filename = file_url.replace("/files/", "", 1)
		return get_site_path("public", "files", filename)
	if file_url.startswith("/"):
		return get_site_path(file_url.lstrip("/"))
	return file_url


def _load_public_key(cert_path):
	with open(cert_path, "rb") as f:
		data = f.read()
	try:
		cert = x509.load_pem_x509_certificate(data)
	except ValueError:
		cert = x509.load_der_x509_certificate(data)
	return cert.public_key()


def _load_private_key(key_path):
	with open(key_path, "rb") as f:
		data = f.read()
	return serialization.load_pem_private_key(data, password=None)


def _aes_ecb_encrypt(key, data):
	padder = PKCS7(128).padder()
	padded = padder.update(data) + padder.finalize()
	cipher = Cipher(algorithms.AES(key), modes.ECB())
	encryptor = cipher.encryptor()
	return encryptor.update(padded) + encryptor.finalize()


def _aes_ecb_decrypt(key, data):
	cipher = Cipher(algorithms.AES(key), modes.ECB())
	decryptor = cipher.decryptor()
	decrypted = decryptor.update(data) + decryptor.finalize()
	unpadder = PKCS7(128).unpadder()
	return unpadder.update(decrypted) + unpadder.finalize()


def _settings():
	return frappe.get_single("CSF MU Settings")


def _auth_headers(settings):
	return {
		"username": settings.username,
		"ebsMraId": settings.ebs_mra_id,
		"areaCode": settings.area_code,
		"Content-Type": "application/json",
	}


def _transmit_headers(settings, token):
	headers = _auth_headers(settings)
	headers["token"] = token
	return headers


def _format_mra_datetime(dt):
	return get_datetime(dt).strftime(MRA_DATETIME_FORMAT)


def get_token_and_mra_key():
	settings = _settings()
	if not settings.public_key_certificate:
		frappe.throw("Public Key Certificate is required in CSF MU Settings.")

	now = now_datetime()

	cert_path = _resolve_file_path(settings.public_key_certificate)
	if not cert_path or not os.path.exists(cert_path):
		frappe.throw("Public Key Certificate file not found.")

	public_key = _load_public_key(cert_path)
	aes_key = os.urandom(32)
	encrypt_key_b64 = base64.b64encode(aes_key).decode()

	password = settings.get_password("password") or ""
	payload = {
		"username": settings.username,
		"password": password,
		"encryptKey": encrypt_key_b64,
		"refreshToken": "true",
	}

	encrypted_payload = public_key.encrypt(
		json.dumps(payload).encode(),
		padding.PKCS1v15(),
	)
	auth_request = {
		"requestId": now.strftime("%Y%m%d%H%M%S"),
		"payload": base64.b64encode(encrypted_payload).decode(),
	}

	resp = requests.post(
		settings.auth_url,
		headers=_auth_headers(settings),
		json=auth_request,
		timeout=DEFAULT_TIMEOUT,
	)
	if resp.status_code >= 400:
		raise frappe.ValidationError(
			f"Auth failed ({resp.status_code}): {resp.text}"
		)
	data = resp.json()

	if data.get("status") != "SUCCESS":
		frappe.throw(str(data))

	settings.db_set("token", data.get("token"), update_modified=False)
	settings.db_set("token_expiry", data.get("expiryDate"), update_modified=False)

	encrypted_key_b64 = data.get("key") or ""
	if not encrypted_key_b64:
		raise frappe.ValidationError(f"Auth response missing key: {data}")

	decrypted = _aes_ecb_decrypt(aes_key, base64.b64decode(encrypted_key_b64))
	try:
		mra_key = base64.b64decode(decrypted)
	except Exception:
		mra_key = decrypted

	return data.get("token"), mra_key


def sign_payload(payload_json, settings):
	if not settings.enable_invoice_signature:
		return ""
	if not settings.private_key_file:
		frappe.throw("Private Key File is required when invoice signature is enabled.")

	key_path = _resolve_file_path(settings.private_key_file)
	if not key_path or not os.path.exists(key_path):
		frappe.throw("Private Key File not found.")

	private_key = _load_private_key(key_path)
	signature = private_key.sign(
		payload_json.encode(),
		padding.PKCS1v15(),
		hashes.SHA256(),
	)
	return base64.b64encode(signature).decode()


def encrypt_invoice(payload_json, mra_key):
	if not mra_key:
		frappe.throw("MRA encryption key is missing.")
	encrypted = _aes_ecb_encrypt(mra_key, payload_json.encode())
	return base64.b64encode(encrypted).decode()


def transmit_invoice(payload_json, signed_hash):
	settings = _settings()
	token, mra_key = get_token_and_mra_key()

	request_id = now_datetime().strftime("%Y%m%d%H%M%S")
	request_datetime = _format_mra_datetime(now_datetime())
	
	encrypted_invoice = encrypt_invoice(payload_json, mra_key)
	
	request_payload = {
		"requestId": request_id,
		"requestDateTime": request_datetime,
		"signedHash": signed_hash or "",
		"encryptedInvoice": encrypted_invoice,
	}

	resp = requests.post(
		settings.transmit_url,
		headers=_transmit_headers(settings, token),
		json=request_payload,
		timeout=DEFAULT_TIMEOUT,
	)
	if resp.status_code >= 400:
		raise frappe.ValidationError(
			f"Transmit failed ({resp.status_code}): {resp.text}"
		)
	return request_payload, resp.json()
