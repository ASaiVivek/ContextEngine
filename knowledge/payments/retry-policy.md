# Payment API retry policy

## Overview

Clients must use exponential backoff when retrying failed payment API requests.

## Rules

1. Retry only on **5xx** responses and **429** (rate limit).
2. Do **not** retry on **4xx** except **429**.
3. Maximum **5** attempts including the initial request.
4. Base delay **200ms**, multiplier **2**, cap **30s**.
5. Add jitter: uniform random in `[0, base_delay]`.

## Idempotency

For mutating requests, always send an idempotency key (see `payments/idempotency`).
