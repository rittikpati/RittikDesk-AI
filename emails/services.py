import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from django.utils import timezone
from django.core.files.storage import default_storage
from .models import EmailMessage

logger = logging.getLogger(__name__)


def test_smtp_connection(smtp_config):
    """Test SMTP connection with the given config. Returns (success, message).

    Follows the standard SMTP sequence with detailed logging at each step:
      connect → EHLO → STARTTLS → EHLO → login → quit
    """
    server = None
    try:
        host = smtp_config.host
        port = smtp_config.port
        logger.info('=== SMTP Test Start ===')
        logger.info('Connecting to %s:%s...', host, port)

        if smtp_config.use_ssl:
            logger.info('Using SSL mode (SMTP_SSL)')
            server = smtplib.SMTP_SSL(host, port, timeout=15)
            logger.info('Connected via SSL.')
        else:
            logger.info('Using plain TCP mode (SMTP)')
            server = smtplib.SMTP(host, port, timeout=15)
            logger.info('Connected. Sending EHLO...')
            server.ehlo()
            logger.info('EHLO ok.')
            if smtp_config.use_tls:
                logger.info('Starting TLS (STARTTLS)...')
                server.starttls()
                logger.info('TLS started. Re-sending EHLO...')
                server.ehlo()
                logger.info('EHLO ok (after TLS).')

        logger.info('Authenticating as %s...', smtp_config.username)
        server.login(smtp_config.username, smtp_config.password)
        logger.info('Authentication successful.')
        server.quit()
        server = None
        logger.info('Connection closed cleanly.')
        logger.info('=== SMTP Test End (SUCCESS) ===')
        return True, 'Connection successful!'

    except smtplib.SMTPAuthenticationError:
        msg = 'Authentication failed. Check your username/password.'
        logger.error('SMTP AuthenticationError: %s', msg)
        return False, msg
    except smtplib.SMTPHeloError as e:
        msg = f'EHLO rejected by server: {e}'
        logger.error('SMTPHeloError: %s', msg)
        return False, msg
    except smtplib.SMTPNotSupportedError as e:
        msg = f'STARTTLS not supported by server: {e}'
        logger.error('SMTPNotSupportedError: %s', msg)
        return False, msg
    except smtplib.SMTPServerDisconnected as e:
        msg = f'Server disconnected unexpectedly: {e}'
        logger.error('SMTPServerDisconnected: %s', msg)
        return False, msg
    except smtplib.SMTPException as e:
        msg = f'SMTP error: {e}'
        logger.error('SMTPException: %s', msg)
        return False, msg
    except TimeoutError as e:
        msg = f'Connection timed out after {15}s. Check host/port/firewall.'
        logger.error('TimeoutError: %s', msg)
        return False, msg
    except OSError as e:
        msg = f'Network error: {e}'
        logger.error('OSError: %s', msg)
        return False, msg
    except Exception as e:
        msg = f'Connection failed: {e}'
        logger.error('Unexpected error: %s', msg, exc_info=True)
        return False, msg
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def send_email_message(email_message):
    """Send an EmailMessage instance via its SMTP config.
    Returns (success, error_message).
    """
    smtp_config = email_message.smtp_config
    if not smtp_config:
        return False, 'No SMTP configuration found.'

    try:
        msg = MIMEMultipart('alternative')
        sender_email = smtp_config.effective_sender_email
        sender_name = smtp_config.sender_name or sender_email
        msg['From'] = f'{sender_name} <{sender_email}>'
        msg['To'] = email_message.to_emails
        if email_message.cc_emails:
            msg['Cc'] = email_message.cc_emails
        msg['Subject'] = email_message.subject
        msg['X-Priority'] = str({'low': '5', 'normal': '3', 'high': '1'}.get(
            email_message.priority, '3'))

        if email_message.body_html:
            msg.attach(MIMEText(email_message.body_html, 'html'))
        if email_message.body_plain:
            msg.attach(MIMEText(email_message.body_plain, 'plain'))

        all_recipients = email_message.recipient_list()
        all_recipients += email_message.cc_list()
        all_recipients += email_message.bcc_list()

        for attachment in email_message.attachments.all():
            try:
                with default_storage.open(attachment.file.name, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{attachment.original_filename}"',
                    )
                    msg.attach(part)
            except Exception as e:
                logger.warning('Failed to attach %s: %s', attachment.original_filename, e)

        server = None
        try:
            if smtp_config.use_ssl:
                server = smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30)
                server.ehlo()
                if smtp_config.use_tls:
                    server.starttls()
                    server.ehlo()
            server.login(smtp_config.username, smtp_config.password)
            server.sendmail(sender_email, all_recipients, msg.as_string())
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

        email_message.status = 'sent'
        email_message.sent_at = timezone.now()
        email_message.save(update_fields=['status', 'sent_at'])
        return True, ''

    except Exception as e:
        error_msg = str(e)
        email_message.status = 'failed'
        email_message.error_message = error_msg
        email_message.save(update_fields=['status', 'error_message'])
        logger.error('Failed to send email %s: %s', email_message.pk, error_msg)
        return False, error_msg


def diagnostic_smtp_connection(smtp_config):
    """Internal diagnostic tool — available only when DEBUG=True.

    Attempts a real SMTP connection and returns a detailed dict
    describing every step taken and any error encountered.
    Never returns the password in the result.
    """
    import socket
    import smtplib as smtp_mod

    steps = []
    server = None

    def _step(name, status, detail=''):
        steps.append({'step': name, 'status': status, 'detail': detail})

    try:
        host = smtp_config.host
        port = smtp_config.port

        _step('DNS Lookup', 'pending')
        try:
            addr = socket.getaddrinfo(host, port)
            _step('DNS Lookup', 'ok', f'Resolved {host} to {addr[0][4][0]}')
        except socket.gaierror as e:
            _step('DNS Lookup', 'fail', f'Could not resolve {host}: {e}')
            return steps

        _step(f'Connect to {host}:{port}', 'pending')
        if smtp_config.use_ssl:
            server = smtp_mod.SMTP_SSL(host, port, timeout=15)
            _step(f'Connect to {host}:{port} (SSL)', 'ok',
                  f'Connected via SSL on port {port}')
        else:
            server = smtp_mod.SMTP(host, port, timeout=15)
            _step(f'Connect to {host}:{port}', 'ok',
                  f'TCP connection established on port {port}')

            _step('EHLO', 'pending')
            try:
                code, msg = server.ehlo()
                _step('EHLO', 'ok', f'Server responded: {msg.decode(errors="replace")[:200]}')
            except smtp_mod.SMTPHeloError as e:
                _step('EHLO', 'fail', f'EHLO rejected: {e}')
                return steps

            if smtp_config.use_tls:
                _step('STARTTLS', 'pending')
                try:
                    server.starttls()
                    _step('STARTTLS', 'ok', 'TLS handshake completed')
                except smtp_mod.SMTPNotSupportedError as e:
                    _step('STARTTLS', 'fail', f'STARTTLS not supported: {e}')
                    return steps
                except Exception as e:
                    _step('STARTTLS', 'fail', f'TLS handshake failed: {e}')
                    return steps

                _step('EHLO (post-TLS)', 'pending')
                try:
                    code, msg = server.ehlo()
                    _step('EHLO (post-TLS)', 'ok',
                          f'Server responded: {msg.decode(errors="replace")[:200]}')
                except smtp_mod.SMTPHeloError as e:
                    _step('EHLO (post-TLS)', 'fail', f'EHLO rejected after TLS: {e}')
                    return steps

        _step('Login', 'pending')
        try:
            server.login(smtp_config.username, smtp_config.password)
            _step('Login', 'ok', f'Authenticated as {smtp_config.username}')
        except smtp_mod.SMTPAuthenticationError:
            _step('Login', 'fail',
                  'SMTPAuthenticationError: Username and Password not accepted. '
                  'For Gmail, use an App Password (16 characters, no spaces).')
            return steps
        except smtp_mod.SMTPException as e:
            _step('Login', 'fail', f'Login failed: {e}')
            return steps

        _step('Quit', 'pending')
        server.quit()
        server = None
        _step('Quit', 'ok', 'Connection closed cleanly')

    except smtp_mod.SMTPServerDisconnected as e:
        _step('Connection', 'fail', f'Server disconnected unexpectedly: {e}')
    except TimeoutError as e:
        _step('Connection', 'fail', f'Timeout after 15s: {e}')
    except OSError as e:
        _step('Connection', 'fail', f'Network error: {e}')
    except Exception as e:
        _step('Connection', 'fail', f'Unexpected error: {e}')
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    return steps


def send_queued_emails():
    """Send all queued emails that are due. Called by management command or scheduler."""
    now = timezone.now()
    queued = EmailMessage.objects.filter(
        status='queued',
        scheduled_time__lte=now,
    ).select_related('smtp_config')
    sent = 0
    failed = 0
    for email in queued:
        success, _ = send_email_message(email)
        if success:
            sent += 1
        else:
            failed += 1
    return sent, failed
