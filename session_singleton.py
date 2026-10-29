"""Authentication/session management for the Investopedia Simulator API.

Credentials are passed to the Node helper through environment variables rather
than command-line arguments. Never commit credentials.json or auth.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import warnings
from pathlib import Path
from typing import Any

import requests

from constants import API_URL, REFRESH_AUTH_TOKEN_URL
from queries import Queries

CWD = Path(__file__).resolve().parent
AUTH_FILE = CWD / "auth.json"
AUTH_SCRIPT = CWD / "auth.js"
PACKAGE_FILE = CWD / "package.json"


class NotLoggedInException(Exception):
    """Raised when no valid authenticated session is available."""


class InvestopediaAuthException(Exception):
    """Raised when Investopedia authentication fails."""


class Session:
    class __Session(requests.Session):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)

    __session: requests.Session | None = None
    __auth_data: dict[str, Any] | None = None
    __credentials: dict[str, str] | None = None

    def __new__(cls):
        if cls.__session is None:
            cls._load_tokens()
        if not cls.is_logged_in():
            raise NotLoggedInException("Not logged in. Call Session.login(credentials).")
        return cls.__session

    def __getattr__(self, name):
        session = type(self).__session
        if session is None:
            raise NotLoggedInException("No active HTTP session.")
        return getattr(session, name)

    def __setattr__(self, name, value):
        session = type(self).__session
        if session is None:
            raise NotLoggedInException("No active HTTP session.")
        return setattr(session, name, value)

    @classmethod
    def refresh_token(cls):
        if not cls.is_logged_in() or not cls.__auth_data:
            return None

        refresh_token = cls.__auth_data.get("refresh_token")
        if not refresh_token:
            raise InvestopediaAuthException(
                "The saved authentication data has no refresh token. Please log in again."
            )

        response = cls.__session.post(
            REFRESH_AUTH_TOKEN_URL,
            data=Queries.refresh_token(refresh_token),
            timeout=20,
        )
        if not response.ok:
            warnings.warn(
                "Saved Investopedia tokens could not be refreshed; please log in again.",
                RuntimeWarning,
            )
            cls.logout()
            if cls.__credentials:
                return cls.login(cls.__credentials)
            raise InvestopediaAuthException(
                "Token refresh failed. Run the login flow again."
            )

        try:
            auth_data = response.json()
        except ValueError as exc:
            raise InvestopediaAuthException(
                "Investopedia returned an invalid token response."
            ) from exc

        if not auth_data.get("access_token"):
            raise InvestopediaAuthException(
                "Investopedia token response did not contain an access token."
            )

        cls.__auth_data = auth_data
        cls.__session.headers.update(
            {
                "Authorization": f"Bearer {auth_data['access_token']}",
                "Content-Type": "application/json",
            }
        )
        cls._save_tokens()
        return cls.__session

    @classmethod
    def _load_tokens(cls):
        if cls.__auth_data is None and AUTH_FILE.is_file():
            try:
                with AUTH_FILE.open("r", encoding="utf-8") as auth_file:
                    auth_data = json.load(auth_file)
            except (OSError, json.JSONDecodeError) as exc:
                raise InvestopediaAuthException(
                    "auth.json is unreadable. Remove the local token file and log in again."
                ) from exc

            if not isinstance(auth_data, dict) or not auth_data.get("access_token"):
                raise InvestopediaAuthException(
                    "auth.json does not contain a valid access token. Log in again."
                )
            cls.__auth_data = auth_data

        if cls.__auth_data is None:
            if cls.__credentials is None:
                raise InvestopediaAuthException(
                    "No saved auth.json token exists. Call Session.login(credentials) first."
                )
            cls.login(cls.__credentials)

        if cls.__session is None and cls.__auth_data:
            cls.__session = requests.Session()
            cls.__session.headers.update(
                {
                    "Authorization": f"Bearer {cls.__auth_data['access_token']}",
                    "Content-Type": "application/json",
                }
            )

    @classmethod
    def _save_tokens(cls):
        if cls.__auth_data is None:
            return
        AUTH_FILE.write_text(
            json.dumps(cls.__auth_data),
            encoding="utf-8",
        )
        try:
            AUTH_FILE.chmod(0o600)
        except OSError:
            # Some mounted filesystems do not support POSIX permission changes.
            pass

    @classmethod
    def is_logged_in(cls):
        return bool(
            cls.__session is not None
            and cls.__session.headers.get("Authorization")
        )

    @classmethod
    def logout(cls):
        cls.__session = None
        cls.__auth_data = None
        if AUTH_FILE.exists():
            AUTH_FILE.unlink()

    @classmethod
    def login(cls, credentials):
        if not isinstance(credentials, dict):
            raise InvestopediaAuthException(
                "Login requires a dictionary with username and password fields."
            )
        username = credentials.get("username")
        password = credentials.get("password")
        if not isinstance(username, str) or not username:
            raise InvestopediaAuthException("A non-empty username is required.")
        if not isinstance(password, str) or not password:
            raise InvestopediaAuthException("A non-empty password is required.")

        cls.__credentials = {"username": username, "password": password}

        if not AUTH_FILE.is_file():
            if not AUTH_SCRIPT.is_file() or not PACKAGE_FILE.is_file():
                raise InvestopediaAuthException(
                    "auth.js or package.json is missing from the repository."
                )
            if not (CWD / "node_modules" / "puppeteer").exists():
                raise InvestopediaAuthException(
                    "Puppeteer is not installed in this Codespace. Run "
                    "'npm install' from the repository directory, then retry."
                )

            environment = os.environ.copy()
            environment["INVESTOPEDIA_USERNAME"] = username
            environment["INVESTOPEDIA_PASSWORD"] = password
            try:
                completed = subprocess.run(
                    ["node", str(AUTH_SCRIPT)],
                    cwd=str(CWD),
                    env=environment,
                    check=False,
                    timeout=180,
                    capture_output=True,
                    text=True,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise InvestopediaAuthException(
                    "Could not start the Investopedia login helper. Check that Node.js "
                    "and the installed Puppeteer browser are available."
                ) from exc
            finally:
                environment.pop("INVESTOPEDIA_PASSWORD", None)
                environment.pop("INVESTOPEDIA_USERNAME", None)

            if completed.returncode != 0 or not AUTH_FILE.is_file():
                # Do not include helper stdout/stderr: browser output can contain
                # private account data or authentication details.
                raise InvestopediaAuthException(
                    "Investopedia login did not complete. Check the login page and "
                    "the local Node/Puppeteer installation, then retry."
                )

        cls.__auth_data = None
        cls.__session = None
        cls._load_tokens()
        if not cls.is_logged_in():
            raise InvestopediaAuthException("Could not initialize an authenticated session.")

        cls.refresh_token()
        response = cls.__session.post(
            API_URL,
            data=Queries.read_user_id(),
            timeout=20,
        )
        if not response.ok:
            cls.__session = None
            raise InvestopediaAuthException(
                f"Investopedia returned HTTP {response.status_code} while verifying login."
            )
        return cls.__session
