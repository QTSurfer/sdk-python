# Signal channels

Use the generated endpoints through the SDK session. The session refreshes the JWT on a
`401` for authenticated calls. Your application controls publishing, offers, single-use
codes, subscriptions, and delivery polling.

```python
from qtsurfer.api.client.api.signal_channels import list_signal_subscriptions
from qtsurfer.api.client.models import SignalSubscriptionList
from qtsurfer_sdk import auth

session = auth()
response = session.call(lambda client: list_signal_subscriptions.sync_detailed(client=client))
if not isinstance(response.parsed, SignalSubscriptionList):
    raise RuntimeError(f"Subscription list failed with HTTP {response.status_code}")
for subscription in response.parsed.subscriptions:
    print(subscription.subscription_id, subscription.state)
```

Public channel discovery and the secret-path webhook use the API client's unauthenticated
`Client`. Keep webhook paths and unredeemed codes private. Delivery records omit the source
and notice data until their scheduled time.

Read the [API guide](https://www.qtsurfer.com/docs/developers/api/signals) for the full
publisher and subscriber workflows, scopes and errors.
