# ECS deployment

## Pre-deploy

- Confirm task definition revision is registered.
- Run integration tests on the candidate image tag.

## Rollout

- Use rolling update with `minimumHealthyPercent: 100` for stateless APIs.
- Set `maximumPercent: 200` to allow faster replacement.
- Wait for service steady state before closing the change ticket.

## Rollback

- Revert to previous task definition revision.
- If health checks fail for **> 5 minutes**, roll back automatically.
