# Runbooks

One file per alert. Every rule in
[`infra/observability/prometheus/rules/`](../../infra/observability/prometheus/rules/)
carries a `runbook_url` pointing here.

The rule is simple: **an alert without a runbook does not ship.** A page with no
documented response gets silenced the first time it fires at 3am, and after that
the alert is worse than useless — it has trained the team to ignore alerts.

Each runbook answers four questions in the same order, because that is the order
you need them at 3am:

1. What does this actually mean?
2. Is it urgent, and what is the learner-visible impact?
3. How do I confirm the cause? (specific queries, specific commands)
4. What do I do about it?

These files are also the worked examples the SRE track uses. They are written to
be read by someone who did not build the system.
