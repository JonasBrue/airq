import os
import base64
import json
import http.client
from typing import List

from dotenv import load_dotenv
from Crypto.Cipher import AES

###############################################################################
# Configuration
###############################################################################
load_dotenv()

AIRQ_HOST: str = os.getenv("AIRQ_HOST", "").strip()
AIRQ_SENSORS: List[str] = [
    p.strip() for p in os.getenv("AIRQ_SENSORS", "").split(",") if p.strip()
]
AIRQ_PASSWORD: str = os.getenv("AIRQ_PASSWORD", "").strip()

if not (AIRQ_HOST and AIRQ_PASSWORD and AIRQ_SENSORS):
    raise RuntimeError("Missing or incomplete .env configuration")

###############################################################################
# Helpers
###############################################################################
# Functions required for decryption
def unpad(data):
  return data[:-ord(data[-1])]

def decodeMessage(msgb64):
    # First step: decode base64
    msg = base64.b64decode(msgb64)

    # Create AES key of length 32 from the air-Q password
    key = AIRQ_PASSWORD.encode('utf-8')
    if len(key) < 32:
        for i in range(32 - len(key)):
            key += b'0'
    elif len(key) > 32:
        key = key[:32]

    # Second step: Decode AES256
    cipher = AES.new(key=key, mode=AES.MODE_CBC, IV=msg[:16])
    return unpad(cipher.decrypt(msg[16:]).decode('utf-8'))

###############################################################################
# Main logic
###############################################################################
def fetch_sensor(path: str) -> dict:
    # Establishing a connection to the air-Q sensor
    conn = http.client.HTTPSConnection(AIRQ_HOST, timeout=5)
    try:
        # Request data
        conn.request("GET", path + "/ping/")
        resp = conn.getresponse()
        # Decrypt data
        encoded_json = json.loads(resp.read())
        decoded_payload = json.loads(decodeMessage(encoded_json["content"]))
        encoded_json["content_decoded"] = decoded_payload
        return encoded_json
    finally:
        conn.close()


def main() -> None:
    for path in AIRQ_SENSORS:
        result = fetch_sensor(path)
        print(f"--- {path} ---")
        print("Encoded and Decoded:", json.dumps(result, indent=2), "\n")


if __name__ == "__main__":
    main()
