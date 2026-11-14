from enum import Enum

from pydantic import BaseModel, Field, model_validator
from pushikoo_interface import PusherConfig, PusherInstanceConfig


class SecurityMode(str, Enum):
    SSL = "ssl"
    STARTTLS = "starttls"
    NONE = "none"


class SMTPAccount(BaseModel):
    host: str = Field(default="smtp.example.com", description="SMTP server hostname")
    port: int = Field(default=465, ge=1, le=65535, description="SMTP server port")
    username: str = Field(default="", description="SMTP login username")
    password: str = Field(
        default="",
        description="SMTP login password or application password",
        json_schema_extra={"format": "password"},
    )
    from_address: str = Field(
        default="pushikoo@example.com", description="Envelope and From email address"
    )
    from_name: str = Field(
        default="Pushikoo", description="Display name in From header"
    )
    security: SecurityMode = Field(
        default=SecurityMode.SSL, description="SMTP transport security"
    )
    timeout_seconds: float = Field(
        default=30, ge=1, description="SMTP and remote image timeout in seconds"
    )


class AdapterConfig(PusherConfig):
    accounts: dict[str, SMTPAccount] = Field(
        default_factory=lambda: {"default": SMTPAccount()},
        description="SMTP accounts",
    )


class InstanceConfig(PusherInstanceConfig):
    account: str = Field(default="default", description="SMTP account to use")
    to: list[str] = Field(
        default_factory=lambda: ["recipient@example.com"],
        description="Primary recipients",
    )
    cc: list[str] = Field(default_factory=list, description="Carbon-copy recipients")
    bcc: list[str] = Field(default_factory=list, description="Blind-copy recipients")
    subject: str | None = Field(
        default=None,
        description="Fixed subject; the first content title is used when empty",
    )
    embed_images: bool = Field(
        default=True,
        description="Download local or remote images and embed them in the HTML email",
    )

    @model_validator(mode="after")
    def validate_recipients(self):
        if not self.to and not self.cc and not self.bcc:
            raise ValueError("At least one recipient is required")
        return self
