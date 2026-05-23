import json
import random
import uuid
from datetime import datetime, timedelta

from common.bq import DB_FILE, get_sqlite_conn


def seed_database():
    print(f"Seeding historical trace and signal corpus into local database ({DB_FILE})...")
    conn = get_sqlite_conn()
    cursor = conn.cursor()

    # Clear previous seed data
    cursor.execute("DELETE FROM agent_responses")
    cursor.execute("DELETE FROM signals")
    cursor.execute("DELETE FROM eval_scores")
    cursor.execute("DELETE FROM route_decisions")
    cursor.execute("DELETE FROM triage_clusters")
    conn.commit()

    base_time = datetime.utcnow() - timedelta(days=14)
    request_counter = 0

    # We will seed 14 days of data.
    # Days 1 to 10: Healthy regime
    # Days 11 to 14: Degraded regime
    for day in range(14):
        day_date = base_time + timedelta(days=day)
        num_runs = 30
        is_degraded_period = day >= 10

        for run in range(num_runs):
            request_counter += 1
            request_id = str(uuid.uuid4())
            run_time = day_date + timedelta(minutes=30 * run)
            run_time_str = run_time.isoformat()

            # --- STEP 1: Data Prep ---
            s1_output = (
                "SRM validation PASSED.\n"
                "Total users: 10,000 (Treatment: 5,020, Control: 4,980)\n"
                "SRM p-value: 0.69 (randomization intact)"
            )
            cursor.execute(
                """
                INSERT INTO agent_responses
                (request_id, agent_id, output, success, tokens_in, tokens_out,
                 latency_ms, tool_calls, self_reports, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    "data-prep",
                    s1_output,
                    1,
                    150,
                    250,
                    120.0 + random.uniform(-10, 10),
                    "[]",
                    json.dumps(["Checked randomization. SRM check passed."]),
                    run_time_str,
                ),
            )
            # Add explicit step 1 signals
            cursor.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, "data-prep", run_time_str, "latency", 120.0, "explicit"),
            )

            # --- STEP 2: Causal Estimation ---
            # If degraded period, 90% of requests in Step 2 are degraded/unstable
            is_run_degraded = is_degraded_period and (random.random() < 0.90)

            if is_run_degraded:
                s2_success = False
                s2_output = (
                    "Causal Estimation Complete.\n"
                    "Method: CUPED-adjusted OLS\n"
                    "Estimated Lift: +48.5%\n"
                    "95% Confidence Interval: [42.1%, 54.9%]\n"
                    "p-value: < 0.0001 (Highly Significant)"
                )
                s2_reports = [
                    "CUPED covariate adjustment yielded unusually high variance. "
                    "Point estimate is extreme."
                ]

                # Signal indicators for failure
                # 1. Out of Bounds signal
                cursor.execute(
                    "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        "causal-estimation",
                        run_time_str,
                        "out_of_bounds",
                        1.0,
                        "explicit",
                    ),
                )
                # 2. Self report warning
                cursor.execute(
                    "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        "causal-estimation",
                        run_time_str,
                        "self_report",
                        1.0,
                        "self_report",
                    ),
                )
                # 3. High latency signal
                cursor.execute(
                    "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        "causal-estimation",
                        run_time_str,
                        "latency",
                        450.0,
                        "explicit",
                    ),
                )
            else:
                s2_success = True
                s2_output = (
                    "Causal Estimation Complete.\n"
                    "Method: CUPED-adjusted OLS\n"
                    "Estimated Lift: +2.4%\n"
                    "95% Confidence Interval: [0.8%, 4.0%]\n"
                    "p-value: 0.0031 (Statistically Significant)"
                )
                s2_reports = ["ATE calculation completed with CUPED variance reduction."]

            cursor.execute(
                """
                INSERT INTO agent_responses
                (request_id, agent_id, output, success, tokens_in, tokens_out,
                 latency_ms, tool_calls, self_reports, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    "causal-estimation",
                    s2_output,
                    1 if s2_success else 0,
                    300,
                    400,
                    280.0 + random.uniform(-20, 20) if not is_run_degraded else 450.0,
                    "[]",
                    json.dumps(s2_reports),
                    run_time_str,
                ),
            )

            # --- STEP 3: Readout ---
            # Propagated wrong value
            if is_run_degraded:
                s3_output = (
                    "MEMO: A/B Experiment Recommendation\n"
                    "Recommendation: SHIP IMMEDIATELY\n"
                    "Rationale: Causal estimation shows an unprecedented +48.5% lift. "
                    "This result is statistically solid and we recommend 100% rollout."
                )
                s3_reports = [
                    "Drafting memo. Treatment lift is extremely large (+48.5%). "
                    "Proceeding with ship recommendation."
                ]
                # Low confidence signal triggers from readout (downstream symptom)
                cursor.execute(
                    "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        request_id,
                        "readout",
                        run_time_str,
                        "low_confidence_output",
                        1.0,
                        "classifier",
                    ),
                )
            else:
                s3_output = (
                    "MEMO: A/B Experiment Recommendation\n"
                    "Recommendation: SHIP\n"
                    "Rationale: The treatment group demonstrated a +2.4% lift (p = 0.003). "
                    "Sample ratio checks indicate randomization was successful. Rolling out."
                )
                s3_reports = ["Drafting memo. Treatment lift (+2.4%) is significant."]

            cursor.execute(
                """
                INSERT INTO agent_responses
                (request_id, agent_id, output, success, tokens_in, tokens_out,
                 latency_ms, tool_calls, self_reports, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    "readout",
                    s3_output,
                    1 if s2_success else 0,
                    400,
                    300,
                    150.0 + random.uniform(-10, 10),
                    "[]",
                    json.dumps(s3_reports),
                    run_time_str,
                ),
            )

        # Seed evaluation scores for the days to show regression trends
        # Causal Estimation agent score goes from ~0.95 to ~0.20 on Day 11
        ce_score = 0.95 if not is_degraded_period else 0.22
        cursor.execute(
            """
            INSERT INTO eval_scores
            (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "causal-estimation",
                "causal_estimation",
                ce_score,
                100,
                ce_score - 0.05,
                ce_score + 0.05,
                day_date.isoformat(),
            ),
        )

        # Data Prep agent stays highly accurate (constant ~0.98)
        cursor.execute(
            """
            INSERT INTO eval_scores
            (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "data-prep",
                "data_prep",
                0.98,
                100,
                0.95,
                1.0,
                day_date.isoformat(),
            ),
        )

        # Readout agent success rate drops from 0.94 to 0.40 since it propagates the bad lift
        ro_score = 0.94 if not is_degraded_period else 0.42
        cursor.execute(
            """
            INSERT INTO eval_scores
            (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "readout",
                "readout",
                ro_score,
                100,
                ro_score - 0.06,
                ro_score + 0.06,
                day_date.isoformat(),
            ),
        )

        # Populate spares with steady healthy profiles
        cursor.execute(
            """
            INSERT INTO eval_scores
            (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "causal-estimation-spare",
                "causal_estimation",
                0.93,
                100,
                0.89,
                0.97,
                day_date.isoformat(),
            ),
        )

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    seed_database()
