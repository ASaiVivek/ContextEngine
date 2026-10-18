# Idempotency for payment operations

## Idempotency keys

- Generate a UUID v4 per logical operation attempt chain.
- Send header: `Idempotency-Key: <uuid>`.
- Reuse the **same** key when retrying the **same** logical operation.

## Server behavior

- First request with a key is processed normally.
- Duplicate requests with the same key return the **original** result without side effects.
- Keys expire after **24 hours**.

## Client guidance

Never rotate keys between retries of the same user-facing action.
