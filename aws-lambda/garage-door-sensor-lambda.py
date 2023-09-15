import json
import os

import boto3


def handler(event, context):
    print(event)  # for diagnostics
    print(context)  # keeps lint happy

    client = boto3.client('sns')

    response = client.publish(
        TopicArn=os.environ['SNS_TOPIC_ARN'],
        Message='Garage door open',
    )

    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        raise RuntimeError

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps('Set garage door status to open')
    }
