from unittest.mock import Mock, patch

from pushikoo_interface import Struct, StructImage, StructText, StructTitle, StructURL

from pushikoo_pusher_email.api import EmailClient, render_email
from pushikoo_pusher_email.config import InstanceConfig, SMTPAccount, SecurityMode


def test_render_email_uses_title_and_embeds_remote_image():
    content = Struct(
        content=[
            StructTitle(text="Alert", heading=2),
            StructText(text="A < B", bold=True),
            StructURL(source="https://example.com", title=StructText(text="Details")),
            StructImage(source="https://example.com/image.png", alt="Chart"),
        ]
    )
    response = Mock(
        content=b"image-data",
        headers={"Content-Type": "image/png; charset=binary"},
    )

    with patch("pushikoo_pusher_email.api.requests.get", return_value=response) as get:
        rendered = render_email(
            content,
            InstanceConfig(to=["to@example.com"]),
            timeout_seconds=20,
            proxies={"https": "http://proxy.local"},
        )

    assert rendered.subject == "Alert"
    assert "A < B" in rendered.plain
    assert "A &lt; B" in rendered.html
    assert "cid:pushikoo-image-0" in rendered.html
    assert rendered.images[0].content_type == "image/png"
    get.assert_called_once_with(
        "https://example.com/image.png",
        timeout=(20, 20),
        proxies={"https": "http://proxy.local"},
    )
    response.raise_for_status.assert_called_once_with()


def test_render_email_embeds_local_file(tmp_path):
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"image-data")

    rendered = render_email(
        Struct(content=[StructImage(source=image_path.as_uri(), alt="Chart")]),
        InstanceConfig(to=["to@example.com"]),
        timeout_seconds=20,
    )

    assert rendered.images[0].data == b"image-data"
    assert rendered.images[0].content_type == "image/png"
    assert rendered.images[0].filename == "chart.png"


def test_create_message_keeps_bcc_out_of_headers():
    account = SMTPAccount(
        from_address="sender@example.com",
        from_name="Pushikoo",
    )
    instance = InstanceConfig(
        to=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        subject="Fixed subject",
        embed_images=False,
    )
    rendered = render_email(
        Struct(content=[StructText(text="Body")]),
        instance,
        timeout_seconds=30,
    )

    message = EmailClient(account)._create_message(rendered, instance)

    assert message["Subject"] == "Fixed subject"
    assert message["Date"] is not None
    assert message["Message-ID"].endswith("@example.com>")
    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Bcc"] is None
    assert message.is_multipart()


def test_send_with_ssl_logs_in_and_uses_all_recipients():
    account = SMTPAccount(
        host="smtp.example.com",
        port=465,
        username="sender@example.com",
        password="secret",
        from_address="sender@example.com",
        security=SecurityMode.SSL,
    )
    instance = InstanceConfig(
        to=["to@example.com"],
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
        embed_images=False,
    )
    smtp = Mock()

    with patch("pushikoo_pusher_email.api.smtplib.SMTP_SSL", return_value=smtp):
        EmailClient(account).send(Struct(content=[StructText(text="Body")]), instance)

    smtp.login.assert_called_once_with("sender@example.com", "secret")
    smtp.send_message.assert_called_once()
    assert smtp.send_message.call_args.kwargs["to_addrs"] == [
        "to@example.com",
        "cc@example.com",
        "bcc@example.com",
    ]
    smtp.quit.assert_called_once_with()


def test_quit_failure_does_not_retry_a_delivered_message():
    account = SMTPAccount(
        host="smtp.example.com",
        username="sender@example.com",
        password="secret",
        from_address="sender@example.com",
    )
    smtp = Mock()
    smtp.quit.side_effect = OSError("connection closed")

    with patch("pushikoo_pusher_email.api.smtplib.SMTP_SSL", return_value=smtp):
        EmailClient(account).send(
            Struct(content=[StructText(text="Body")]),
            InstanceConfig(to=["to@example.com"], embed_images=False),
        )

    smtp.send_message.assert_called_once()
    smtp.close.assert_called_once_with()


def test_send_with_starttls_upgrades_connection():
    account = SMTPAccount(
        host="smtp.example.com",
        port=587,
        username="",
        password="",
        from_address="sender@example.com",
        security=SecurityMode.STARTTLS,
    )
    smtp = Mock()

    with patch("pushikoo_pusher_email.api.smtplib.SMTP", return_value=smtp):
        EmailClient(account).send(
            Struct(content=[StructText(text="Body")]),
            InstanceConfig(to=["to@example.com"], embed_images=False),
        )

    smtp.starttls.assert_called_once()
    smtp.login.assert_not_called()
    smtp.quit.assert_called_once_with()
