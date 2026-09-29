# Backup job runbook

This runbook covers the nightly backup job for the file server. Follow it when the job fails or when you restore a folder.

## What the job does

The job runs at 02:00 UTC. It copies changed files from `\\fs01\shares` to the backup bucket, then deletes snapshots older than 30 days. A full run takes about 40 minutes. If it runs past 04:00, the monitoring check pages the on-call engineer.

The job writes a log to `C:\logs\backup\YYYY-MM-DD.log`. Each line starts with a timestamp and a level: `INFO`, `WARN`, or `ERROR`.

## Check a failed run

1. Open the latest log file.
2. Search for `ERROR`. The first error is usually the cause, and later errors follow from it.
3. If the error mentions `AccessDenied`, the service account's password expired. Reset it in Active Directory and rerun the job.
4. If the error mentions `Timeout`, check the VPN tunnel to the backup site. The job can't reach the bucket without it.

Don't rerun the job more than twice in a row. A third failure means something else is wrong, and repeated runs fill the bucket with partial copies.

## Restore a folder

To restore a folder, you need its path and the date you want. Run the restore script from the admin workstation:

```powershell
.\Restore-Folder.ps1 -Path "\\fs01\shares\finance\2026" -Date 2026-09-01
```

The script restores to a new folder next to the original, named with the date. It never overwrites current files. Compare the two folders, then move what you need.

## Known issues

- The job skips files locked by another process. Excel keeps a lock while a workbook is open, so an open budget file won't back up until someone closes it.
- Filenames longer than 260 characters fail on the old server. The new server doesn't have this limit.
- The test harness in `tests/` mocks the bucket, so a passing test run doesn't prove the job can reach the real one.

## Why the retention is 30 days

We picked 30 days because the finance team closes its books monthly. A mistake found at month end is almost always less than 30 days old. Longer retention costs more and hasn't been needed in two years of restores.

The vendor's guide says "retention should delve into business needs." We read that as "ask finance," which we did.

> The restore worked on the first try. Took ten minutes.

That quote is from the last real restore, in August 2026.

## MFA (Multi-Factor Authentication)

Every admin sign-in needs a second factor. The policy maps to the access control practice.

## Application control (3.4.9)

Only approved programs run on the file server.

## Access control (AC.L2-3.1.5)

Admins use a separate account for admin work.

## Run it

Start the job from the scheduler, not a shell, so it runs as the service account.

## Tell us if a restore fails

Post the job ID in the channel. You may need the log too.

## Costs

In real terms, the storage bill fell by a third after the retention change. Nobody talks to the vendor about renewals, so the date is on the team calendar. The part nobody wants to do is the yearly restore test, which is why it has an owner.

Go look at the log before you open a ticket. As I said in the handoff, the job skips locked files. [TODO: circle back and add the lock list here, this essay is about delving.]

To change the schedule, open Settings, then Jobs, then Backup. The migration script prints old -> new for each renamed share, including the Catalan team's col·lecció folder.

## Restore history

Restores by year: 2024 14; 2025 22; 2026 9; total 45.

| Folder | Owners | Notes |
|---|---|---|
| finance | Ana; Raj; Lee | Month-end close; audit copies; tax files |
| legal | Mo; Priya | Contracts; holds; exports |
