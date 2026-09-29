Does anyone run Postgres logical replication across regions with more than 2 TB of changes a day?

We're on 16.2 and see replication lag climb past 40 minutes during nightly batch loads. We've raised max_wal_senders and moved the slots to faster disks, and neither changed the lag much. I'd like to compare slot settings with someone before we try a different design.
