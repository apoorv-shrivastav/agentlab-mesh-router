# NOTIFICATIONS.md — Optional Fault-Notification Email

A small, optional add-on: when the loop detects and localizes a fault, send **one email** summarizing it, with a link back to the console to approve. ~1–2 hours, low risk.

Read alongside `SCAFFOLD.md` (the `triage/runner.py` this hooks into), `PITCH.md` (the Q&A framing), and `DESIGN_UPDATE.md` (which holds the work that actually moves the 45% score).

---

## 0. Read This First — Build It Or Not?

This feature is **not on the demo's critical path.** The 3-minute script approves in the console (Beat 3). A judge will never see this email during the demo. So before building, be honest about time:

- **If time is tight at all → do not build it. Make it a Q&A answer.** See §5. A roadmap answer costs zero build time and a senior interviewer respects it.
- **If you have a genuinely spare, low-stakes 1–2 hours → build the version in this file, and only this version.**

Two hard limits if you do build it:

1. **Email only. No SMS.** SMS means Twilio — account, number provisioning (which can stall on ID verification), an inbound webhook, reply parsing. That is half a day of work and a real landmine this close to judging. Email is one API call. Do not cross this line.
2. **Notify-only. No approve-by-email.** The email *links to the console* to approve. It does not carry an approve action itself. Approval stays in the console — one surface, auditable, and the place the demo shows it. Building approve-over-email means a second approval path to secure and test. Don't.

> **Why these limits.** You already deleted the Slack approval surface deliberately — an external approval channel was build cost for something not in the demo. Approve-by-email is the same thing wearing a different hat. Notify-only email keeps the supervised-approval design intact: the triage agent proposes, a human approves *in the console*. The email is just a faster page to the human.

---

## 1. What It Is

When `triage/runner.py` localizes a fault, it sends one email:

- **Subject:** the headline — which step broke. e.g. `AgentLab: fault localized — causal-estimation step`
- **Body:** a short summary — the localized step (cause), the downstream symptom step, the one-line root cause, the count of drafted eval tasks awaiting review.
- **One link:** to the console's Triage view, where the human reviews and approves.

That's it. One email, one link, no reply handling.

---

## 2. Building It

Use a transactional email API — **Resend** or **SendGrid** are simplest; both are a single authenticated POST. (Plain SMTP works too but is fiddlier from a container.)

**Setup (~20 min):**
- Create an account, get an API key.
- Store the key in Secret Manager (per `SETUP.md`'s secrets pattern) — `notify-email-api-key`. Do not put it in an env var in plaintext.
- Pick a recipient address for the demo — your own.

**Code (~45–60 min):** a small module, `triage/notify.py`:

```python
# triage/notify.py — fault-notification email. Optional; notify-only.
import os
import httpx

def send_fault_email(cluster, console_url: str) -> None:
    """Send one summary email when a fault is localized.
    Fails soft — a notification failure must never break the loop."""
    api_key = os.environ.get("NOTIFY_EMAIL_API_KEY")
    recipient = os.environ.get("NOTIFY_EMAIL_TO")
    if not api_key or not recipient:
        return  # notifications not configured — skip silently

    subject = f"AgentLab: fault localized — {cluster.cause_step} step"
    body = (
        f"A fault was localized in the pipeline.\n\n"
        f"  Cause step:    {cluster.cause_step}\n"
        f"  Symptom steps: {', '.join(cluster.symptom_steps) or 'none'}\n"
        f"  Root cause:    {cluster.root_cause}\n"
        f"  Drafted eval tasks awaiting review: {len(cluster.proposed_tasks)}\n\n"
        f"Review and approve in the console:\n"
        f"  {console_url}/triage\n"
    )
    try:
        httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": "AgentLab <onboarding@resend.dev>",
                "to": [recipient],
                "subject": subject,
                "text": body,
            },
            timeout=10,
        )
    except Exception:
        pass  # fail soft — never let a notification failure break the loop
```

**Wiring (~15 min):** in `triage/runner.py`, after the fault is localized and tasks are drafted — the same point that surfaces the cluster to the console — call `send_fault_email(cluster, console_url)`. One line. It runs alongside the console surfacing, not instead of it.

**The non-negotiable property: fail soft.** A notification is a convenience. If the email API is down, rate-limited, or misconfigured, `send_fault_email` must swallow the error and return — never raise, never block, never break the loop. The loop's job is localization and repair; the email is a courtesy on top. The `try/except` and the early-return-if-unconfigured above are both load-bearing.

---

## 3. Demo-Day Posture

If you build it, decide *before* judging how it appears:

- **Default: it runs silently in the background.** It is not in the 3-minute script. Don't tab to an inbox mid-demo — that breaks the console flow, exactly what the Slack surface was cut for.
- **Optional, only if it's solid:** mention in Beat 3 or 4, in one clause, without leaving the console — *"...and the same trigger pages whoever owns the pipeline by email."* No screen time, just a sentence.
- **If it's flaky in rehearsal:** disable it (unset `NOTIFY_EMAIL_API_KEY`) and make it a pure Q&A point. A half-working feature on stage is worse than a described one.

---

## 4. Checklist (only if building)

- [ ] Email API key in Secret Manager, not an env var in plaintext.
- [ ] `triage/notify.py` fails soft — verified by running the loop with a bad API key and confirming the loop still completes.
- [ ] The email link points at the deployed console's `/triage` view and actually loads.
- [ ] The summary names the **cause** step and the **symptom** step distinctly — consistent with the localization thesis.
- [ ] Tested once end to end: trigger a fault, confirm the email arrives within a few seconds.
- [ ] Decided demo posture (silent / one-clause mention / disabled) before judging.

---

## 5. If You Don't Build It — The Q&A Answer

This is a perfectly good outcome, and the recommended one if time is tight. When a judge asks "how does a human find out a fault happened?":

> *"The loop surfaces the localized fault for human approval. In the demo that's the console's Triage view — which is also where you saw me approve. In production it's a notification to whoever owns the pipeline — email, or SMS — with a one-click link back to approve. Same trigger, same supervised-approval design; I kept the demo on the console surface so the approval step is visible to you rather than buried in an inbox."*

That is an honest roadmap answer. It shows you have thought past the hackathon, it reinforces the supervised-by-design point, and it costs zero build time — time better spent on the `DESIGN_UPDATE.md` P0/P1 items, which are the ones that move the 45% live-demo score.

---

## The One Judgment Call

A feature judges will not see in the 3 minutes should never outrank a bug they will. If building this email trades against fixing the ATE-monitor overlap or the broken-state polish in `DESIGN_UPDATE.md` — fix those first, every time, and make this a Q&A sentence.
