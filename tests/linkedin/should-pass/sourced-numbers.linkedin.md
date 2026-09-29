Our p95 latency dropped from 800 ms to 120 ms after we moved session lookups from Postgres into Redis.

The change shipped on 12 September, and the migration went live in all three regions in 3 days. Error rates stayed flat, and the Redis cluster runs at about 30% memory. The graphs and the rollback plan are in the design doc linked from our team wiki.
