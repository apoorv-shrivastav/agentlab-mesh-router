import json
from common.schema import TriageCluster

def format_slack_a2ui_card(cluster: TriageCluster) -> dict:
    """
    Constructs a Slack Block Kit interactive message payload representing the triage card.
    This enables humans in the loop to review localization results and approve new evaluation tasks.
    """
    symptom_text = ", ".join([f"`{s}`" for s in cluster.symptom_steps]) if cluster.symptom_steps else "None"
    
    # Render interactive card using standard Slack Block Kit
    card = {
        "text": f"AgentLab Triage Alert: Failure cluster {cluster.cluster_id} localized.",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 AgentLab Triage Alert: Regression Localized",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Failure Cluster ID:* `{cluster.cluster_id}` (Size: {cluster.size} failed traces)"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Cause Step:*\n`{cluster.cause_step.value}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Cause Agent:*\n`{cluster.cause_agent_id}`"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Symptom Step(s):*\n{symptom_text}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Localization Basis:*\n`{cluster.localization_basis}`"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n_{cluster.root_cause}_"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Proposed Evaluation Tasks:* \n" + "\n".join([
                        f"• *Prompt:* `{t['prompt']}`\n  *Expected:* `{t['expected']}`"
                        for t in cluster.proposed_tasks
                    ])
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve & Rollout Tasks",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": cluster.cluster_id,
                        "action_id": "approve_triage_cluster"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Reject",
                            "emoji": True
                        },
                        "style": "danger",
                        "value": cluster.cluster_id,
                        "action_id": "reject_triage_cluster"
                    }
                ]
            }
        ]
    }
    return card

def post_triage_alert(cluster: TriageCluster) -> None:
    """
    Simulates sending the interactive Slack block card to a designated Slack channel.
    Prints output log representing the network webhook execution.
    """
    card = format_slack_a2ui_card(cluster)
    print("\n--- [Slack Webhook (A2UI Card)] Posted Card Payload ---")
    print(json.dumps(card, indent=2))
    print("-------------------------------------------------------\n")

def handle_slack_interaction(payload: dict) -> dict:
    """
    Processes interactive webhook actions received from Slack button clicks.
    Returns status outcome dict.
    """
    actions = payload.get("actions", [])
    if not actions:
        return {"status": "error", "message": "No actions in payload"}
        
    action = actions[0]
    action_id = action.get("action_id")
    cluster_id = action.get("value")
    
    if action_id == "approve_triage_cluster":
        # Under real/mock execution, runner.py will carry out approval logic
        print(f"[Slack Interactivity] Triage cluster {cluster_id} APPROVED.")
        from triage.runner import approve_triage_tasks
        success = approve_triage_tasks(cluster_id)
        return {
            "status": "success",
            "message": f"Cluster {cluster_id} approved. Tasks rolled out successfully." if success else "Cluster approval failed."
        }
        
    elif action_id == "reject_triage_cluster":
        print(f"[Slack Interactivity] Triage cluster {cluster_id} REJECTED.")
        from triage.runner import reject_triage_tasks
        success = reject_triage_tasks(cluster_id)
        return {"status": "success", "message": f"Cluster {cluster_id} rejected."}
        
    return {"status": "error", "message": f"Unknown action: {action_id}"}
