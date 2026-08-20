"""
Exchange a Kite request_token for an access_token and update KITE_ACCESS_TOKEN
in GitHub Actions secrets so the alert bot always has a fresh token.

Required env vars:
  KITE_API_KEY        — Zerodha app API key
  KITE_API_SECRET     — Zerodha app API secret
  KITE_REQUEST_TOKEN  — one-time token from today's login redirect URL
  GH_PAT              — GitHub PAT with secrets:write scope on this repo
  GH_REPO             — owner/repo e.g. "alekhya14/gold-alert-bot"
"""

import base64
import os
import sys

import requests
from kiteconnect import KiteConnect
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox


def exchange_token() -> str:
    kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
    session = kite.generate_session(
        os.environ["KITE_REQUEST_TOKEN"],
        api_secret=os.environ["KITE_API_SECRET"],
    )
    access_token = session["access_token"]
    print(f"  Kite session generated — access_token starts with {access_token[:6]}...")
    return access_token


def get_repo_public_key(repo: str, pat: str) -> tuple[str, str]:
    """Returns (key_id, base64_public_key) for encrypting a secret."""
    url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    r = requests.get(url, headers={"Authorization": f"token {pat}"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt secret_value with the repo's libsodium public key."""
    pub_key = PublicKey(base64.b64decode(public_key_b64))
    sealed  = SealedBox(pub_key).encrypt(secret_value.encode(), encoder=Base64Encoder)
    return sealed.decode()


def update_github_secret(repo: str, pat: str, secret_name: str, secret_value: str):
    key_id, pub_key_b64 = get_repo_public_key(repo, pat)
    encrypted = encrypt_secret(pub_key_b64, secret_value)

    url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    r = requests.put(
        url,
        headers={"Authorization": f"token {pat}"},
        json={"encrypted_value": encrypted, "key_id": key_id},
        timeout=10,
    )
    r.raise_for_status()
    print(f"  GitHub secret {secret_name} updated (HTTP {r.status_code})")


def main():
    for var in ("KITE_API_KEY", "KITE_API_SECRET", "KITE_REQUEST_TOKEN", "GH_PAT", "GH_REPO"):
        if not os.environ.get(var):
            print(f"ERROR: missing env var {var}")
            sys.exit(1)

    print("[ Step 1 ] Exchanging request_token for access_token...")
    access_token = exchange_token()

    print("[ Step 2 ] Updating KITE_ACCESS_TOKEN in GitHub secrets...")
    update_github_secret(
        repo=os.environ["GH_REPO"],
        pat=os.environ["GH_PAT"],
        secret_name="KITE_ACCESS_TOKEN",
        secret_value=access_token,
    )

    print("\nDone. KITE_ACCESS_TOKEN is fresh — alert bot will use it on next run.")


if __name__ == "__main__":
    main()
