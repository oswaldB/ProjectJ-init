
import boto3
import logging
import os

logger = logging.getLogger(__name__)

# AWS configuration
REGION = os.environ.get('AWS_REGION') or 'eu-west-2'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')


class Email:
    def __init__(self, to, subject, content, cc=None):
        self.to = to if isinstance(to, list) else [to]
        self.subject = subject
        self.content = content
        self.cc = cc or []

    def send(self):
        client = boto3.client(
            'ses',
            region_name=REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

        try:
            destination = {'ToAddresses': self.to}
            if self.cc:
                destination['CcAddresses'] = self.cc

            response = client.send_email(
                Destination=destination,
                Message={
                    'Body': {
                        'Html': {
                            'Charset': 'UTF-8',
                            'Data': self.content,
                        },
                    },
                    'Subject': {
                        'Charset': 'UTF-8',
                        'Data': self.subject,
                    },
                },
                Source="palms.reporting@noexternalmail.hsbc.com",
            )
            logger.info(f"Email sent! Message ID: {response['MessageId']}")
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise
