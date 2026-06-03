"""Push notification service.

This is a placeholder. Integrate with Firebase Cloud Messaging (FCM) or
Apple Push Notification Service (APNs) when push notifications are needed.
"""


async def send_notification(token: str, title: str, body: str) -> bool:
    """Send a push notification to a device.

    Args:
        token: FCM/APNs device token.
        title: Notification title.
        body: Notification body text.

    Returns:
        True if sent successfully.
    """
    # TODO: integrate with FCM
    # Example with firebase-admin:
    #   from firebase_admin import messaging
    #   message = messaging.Message(
    #       notification=messaging.Notification(title=title, body=body),
    #       token=token,
    #   )
    #   messaging.send(message)
    print(f"[NOTIFICATION] {title}: {body} -> {token}")
    return True
