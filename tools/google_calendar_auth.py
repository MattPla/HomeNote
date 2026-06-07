from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a HomeNote Google Calendar OAuth token.")
    parser.add_argument(
        "--credentials",
        default="google-credentials.json",
        help="Path to OAuth client credentials JSON downloaded from Google Cloud.",
    )
    parser.add_argument(
        "--token",
        default="google-token.json",
        help="Where to save the authorized token JSON.",
    )
    args = parser.parse_args()

    credentials_path = Path(args.credentials)
    token_path = Path(args.token)
    if not credentials_path.exists():
        print(f"Credentials file not found: {credentials_path}")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved Google Calendar token to {token_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

