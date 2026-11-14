import html
import mimetypes
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from pushikoo_interface import Struct, StructImage, StructText, StructTitle, StructURL

from pushikoo_pusher_email.config import InstanceConfig, SMTPAccount, SecurityMode


@dataclass
class InlineImage:
    cid: str
    data: bytes
    content_type: str
    filename: str


@dataclass
class RenderedEmail:
    subject: str
    plain: str
    html: str
    images: list[InlineImage] = field(default_factory=list)


def _text_html(element: StructText) -> str:
    text = html.escape(element.text).replace("\n", "<br>\n")
    if element.bold:
        text = f"<strong>{text}</strong>"
    if element.italic:
        text = f"<em>{text}</em>"
    return text


def _read_image(
    source: str,
    *,
    timeout_seconds: float,
    proxies: dict[str, str] | None,
) -> tuple[bytes, str, str]:
    if source.startswith(("http://", "https://")):
        response = requests.get(
            source,
            timeout=(timeout_seconds, timeout_seconds),
            proxies=proxies,
        )
        response.raise_for_status()
        filename = Path(unquote(urlparse(source).path)).name or "image"
        content_type = (
            response.headers.get("Content-Type", "").split(";", 1)[0]
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )
        return response.content, content_type, filename

    if source.startswith("file://"):
        parsed = urlparse(source)
        path_text = unquote(parsed.path)
        if parsed.netloc:
            path_text = f"//{parsed.netloc}{path_text}"
        elif os.name == "nt" and len(path_text) >= 3 and path_text[2] == ":":
            path_text = path_text.lstrip("/")
        path = Path(path_text)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path.read_bytes(), content_type, path.name

    raise ValueError(f"Unsupported image source: {source}")


def render_email(
    content: Struct,
    instance_config: InstanceConfig,
    *,
    timeout_seconds: float,
    proxies: dict[str, str] | None = None,
) -> RenderedEmail:
    subject = instance_config.subject
    if not subject:
        subject = next(
            (
                element.text.strip()
                for element in content.content
                if isinstance(element, StructTitle) and element.text.strip()
            ),
            "Pushikoo notification",
        )

    plain_parts: list[str] = []
    html_parts: list[str] = []
    images: list[InlineImage] = []

    for element in content.content:
        if isinstance(element, StructTitle):
            heading = min(max(element.heading, 1), 6)
            plain_parts.append(element.text + "\n")
            html_parts.append(f"<h{heading}>{_text_html(element)}</h{heading}>")
        elif isinstance(element, StructText):
            plain_parts.append(element.text)
            html_parts.append(f"<p>{_text_html(element)}</p>")
        elif isinstance(element, StructURL):
            title = str(element.title) or element.source
            plain_parts.append(f"{title}: {element.source}")
            html_parts.append(
                f'<p><a href="{html.escape(element.source, quote=True)}">'
                f"{_text_html(element.title)}</a></p>"
            )
        elif isinstance(element, StructImage):
            plain_parts.append(element.alt or element.source)
            if instance_config.embed_images:
                data, content_type, filename = _read_image(
                    element.source,
                    timeout_seconds=timeout_seconds,
                    proxies=proxies,
                )
                cid = f"pushikoo-image-{len(images)}"
                images.append(
                    InlineImage(
                        cid=cid,
                        data=data,
                        content_type=content_type,
                        filename=filename,
                    )
                )
                image_source = f"cid:{cid}"
            else:
                image_source = element.source
            html_parts.append(
                f'<p><img src="{html.escape(image_source, quote=True)}" '
                f'alt="{html.escape(element.alt, quote=True)}"></p>'
            )

    return RenderedEmail(
        subject=subject,
        plain="\n\n".join(part for part in plain_parts if part),
        html="<!doctype html><html><body>" + "\n".join(html_parts) + "</body></html>",
        images=images,
    )


class EmailClient:
    def __init__(self, account: SMTPAccount, proxies: dict[str, str] | None = None):
        self.account = account
        self.proxies = proxies

    def _create_message(
        self, rendered: RenderedEmail, instance_config: InstanceConfig
    ) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = rendered.subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(
            domain=self.account.from_address.rpartition("@")[2] or None
        )
        message["From"] = formataddr(
            (self.account.from_name, self.account.from_address)
        )
        if instance_config.to:
            message["To"] = ", ".join(instance_config.to)
        if instance_config.cc:
            message["Cc"] = ", ".join(instance_config.cc)

        message.set_content(rendered.plain)
        message.add_alternative(rendered.html, subtype="html")
        html_part = message.get_payload()[-1]
        for image in rendered.images:
            maintype, _, subtype = image.content_type.partition("/")
            if not subtype:
                maintype, subtype = "application", "octet-stream"
            html_part.add_related(
                image.data,
                maintype=maintype,
                subtype=subtype,
                cid=f"<{image.cid}>",
                filename=image.filename,
            )
        return message

    def send(self, content: Struct, instance_config: InstanceConfig) -> None:
        rendered = render_email(
            content,
            instance_config,
            timeout_seconds=self.account.timeout_seconds,
            proxies=self.proxies,
        )
        message = self._create_message(rendered, instance_config)
        recipients = instance_config.to + instance_config.cc + instance_config.bcc
        context = ssl.create_default_context()

        if self.account.security == SecurityMode.SSL:
            client = smtplib.SMTP_SSL(
                self.account.host,
                self.account.port,
                timeout=self.account.timeout_seconds,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                self.account.host,
                self.account.port,
                timeout=self.account.timeout_seconds,
            )

        try:
            client.ehlo()
            if self.account.security == SecurityMode.STARTTLS:
                client.starttls(context=context)
                client.ehlo()
            if self.account.username:
                client.login(self.account.username, self.account.password)
            client.send_message(
                message,
                from_addr=self.account.from_address,
                to_addrs=recipients,
            )
        finally:
            try:
                client.quit()
            except (OSError, smtplib.SMTPException):
                try:
                    client.close()
                except OSError:
                    pass
