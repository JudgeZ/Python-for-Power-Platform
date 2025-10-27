# Analytics Advisor Recommendations

The analytics client and CLI expose the Power Platform Advisor Recommendations
surface area, allowing you to review environment health signals and act on
remediation guidance.

## Required Azure AD scopes

Advisor Recommendations are published under the main Power Platform resource.
Grant your service principal or user the ``https://api.powerplatform.com/.default``
scope, or the equivalent delegated consent in Azure Active Directory. Without
this scope the analytics endpoints return ``403 Forbidden`` responses.

## Browsing scenarios

List available scenarios to understand which areas expose recommendations:

```bash
ppx analytics scenarios
```

You can then inspect the actions, impacted resources, and active
recommendations for a scenario:

```bash
ppx analytics actions maker
ppx analytics resources maker --top 5 --pages 0
ppx analytics recommendations maker
ppx analytics show maker 00000000-0000-0000-0000-000000000000
```

Each command returns JSON or rich console output that mirrors the REST payloads
documented in ``openapi/analytics-recommendations.yaml``.

## Acting on recommendations

Use the ``acknowledge`` and ``dismiss`` commands to signal that you have taken
action on a recommendation. Both commands submit requests that return an
``Operation-Location`` header. PACX polls that operation until a terminal state
unless you pass ``--no-wait``:

```bash
# Acknowledge and wait for completion
ppx analytics acknowledge --scenario maker --recommendation-id rec-1 \
  --notes "Investigating with the maker team"

# Dismiss without waiting (poll the operation manually later)
ppx analytics dismiss --scenario maker --recommendation-id rec-2 --no-wait
```

When additional automation is required you can execute remediation actions
directly:

```bash
ppx analytics execute run --scenario maker --parameters '{"force": true}'
```

Action payloads are validated against the schema documented in the OpenAPI
definition. The command returns the per-resource status from the Advisor API.
