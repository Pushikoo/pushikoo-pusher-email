# pushikoo-pusher-email

SMTP email pusher adapter for Pushikoo.

## Features

- Multiple SMTP accounts
- SSL, STARTTLS, or plain SMTP connections
- To, Cc, and Bcc recipients
- Plain-text and HTML multipart messages
- Subject derived from the first `StructTitle`, with an optional fixed override
- Optional CID embedding for remote and local images
- Configurable SMTP and image download timeout

## Configuration

Adapter-level configuration stores reusable SMTP accounts. Instance-level configuration selects an account and defines recipients and subject behavior.

```json
{
  "accounts": {
    "default": {
      "host": "smtp.example.com",
      "port": 465,
      "username": "sender@example.com",
      "password": "application-password",
      "from_address": "sender@example.com",
      "from_name": "Pushikoo",
      "security": "ssl",
      "timeout_seconds": 30
    }
  }
}
```

```json
{
  "account": "default",
  "to": ["recipient@example.com"],
  "cc": [],
  "bcc": [],
  "subject": null,
  "embed_images": true
}
```

Do not commit real SMTP credentials. Configure them through Pushikoo's adapter configuration UI or API.
