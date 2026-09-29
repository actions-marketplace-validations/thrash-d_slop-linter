Last month our payments service went down for 41 minutes on a Friday afternoon.

A certificate on the internal load balancer expired. The renewal job had been failing silently since June because a service account password rotated and nobody updated the job.

We now alert on certificates 30 days before expiry, and the renewal job pages on-call when it fails. The postmortem is on our engineering blog.
