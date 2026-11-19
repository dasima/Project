"""Create a private local environment file without printing credentials."""

import os
import secrets
from pathlib import Path

project = Path(__file__).resolve().parent.parent
destination = project / ".env"
if destination.exists():
    raise SystemExit(".env already exists; kept the existing configuration.")
template = (project / ".env.example").read_text()
for key in ("DJANGO_SECRET_KEY", "API_TOKEN", "DEMO_PROVIDER_TOKEN", "DB_PASSWORD"):
    template = template.replace(f"{key}=\n", f"{key}={secrets.token_urlsafe(48)}\n")
descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(descriptor, "w") as output:
    output.write(template)
print("Created private .env with random secrets; credentials were not printed.")
