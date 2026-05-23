# AgentLab Live Presentation & Demo Script

This document details the exact 3-minute script, sequencing, and visual beats for the live panel presentation. 

- **Target Duration**: 3:00 (Ceiling: 3:15)
- **Roles**: Presenter (speaks), Operator (clicks)

---

## Beat-by-Beat Presentation Sequence

### Beat 1: The Healthy Regime (0:00 - 0:45)
* **Goal**: Walk through the routing topology and prove baseline optimization.
* **Visuals**:
  1. Open the browser to the console dashboard (Pipeline tab).
  2. Show the three step nodes: `DATA PREP` (GCP), `CAUSAL ESTIMATION` (AWS), and `READOUT` (Azure).
  3. All nodes show green status dots (`● PIPELINE HEALTHY`) and low query costs/latencies.
  4. Point to the **ATE Monitor** at the bottom showing causal lift in-bounds (+2.4%).
* **Script**:
  > "Welcome. Today, we are demonstrating AgentLab, a decentralized, cross-cloud router and fault localization engine.
  > Here in our console, we see our workflow topology: Step 1 runs on GCP, Step 2 on AWS, and Step 3 on Azure OpenAI.
  > Under normal operation, the pipeline is healthy. Our router optimizes for the Pareto frontier, matching tasks to the cheapest agent that meets quality requirements. In this state, the estimated causal effect is at +2.4%, well within our statistical bounds of 0% to 10%."

### Beat 2: Silent Failure & Degradation (0:45 - 1:15)
* **Goal**: Inject a failure and demonstrate cause-vs-symptom propagation.
* **Visuals**:
  1. Operator clicks **"Inject Pipeline Fault"** in the sidebar.
  2. The status bar immediately transitions to `▲ DEGRADATION DETECTED`.
  3. The `CAUSAL EST.` node border turns red and pulses (`animate-fault-glow`). Its pass rate drops to `0.18`.
  4. The causal ATE estimate slides far to the right, showing `+48.5%` (out of bounds).
  5. The connecting path to `READOUT` turns amber and animates (`animate-flow-edge`).
  6. The `READOUT` node border turns amber (`animate-warn-glow`), displaying the `"input from CAUSAL ↑"` warning.
* **Script**:
  > "Now, we trigger a regression on AWS by swapping the causal estimation model. 
  > Instantly, the system registers a degradation. Notice the visual separation of cause and symptom: AWS turns red—the root cause—because its estimate of +48.5% is far out of bounds. 
  > The readout agent downstream, though operating correctly, receives this bad input. The flow edge carries an amber pulse, and the readout card turns amber—flagging it as a symptom. We see cause and symptom in a single frame."

### Beat 3: Autonomous Triage & Verdict (1:15 - 2:00)
* **Goal**: Show the agent's real-time reasoning and task generation.
* **Visuals**:
  1. Operator switches to the **Triage** tab.
  2. Show the reasoning log streaming line-by-line into the terminal console.
  3. The **Fault Localization Verdict** card snaps in:
     - `CAUSAL ESTIMATION` labeled as `CAUSE` (red chip).
     - `READOUT` labeled as `SYMPTOM` (amber chip).
  4. Point to the 3 newly-drafted evaluation tasks at the bottom.
* **Script**:
  > "We switch to Triage. Rather than querying a lookup table, our autonomous agent is reading trace signals, running clustering, and localizing the fault. 
  > The verdict is clear: it isolates the fault to Causal Estimation and correctly identifies Readout as a symptom. 
  > Furthermore, the agent generates 3 new evaluation scenarios to expand the harness and test this regression pattern, requiring human verification before rollout."

### Beat 4: Approval & Self-Healing (2:00 - 2:30)
* **Goal**: Click approve, show the re-scoring loop, and watch the pipeline recover.
* **Visuals**:
  1. Operator clicks the green **"Approve & Rollout Tasks"** button.
  2. The screen switches back to the Pipeline tab. Loop state transitions to `re-scoring`.
  3. After a brief delay, the `CAUSAL EST.` agent swaps to `causal-estimation-spare`.
  4. The ATE numeral slides back to the healthy range (`+2.4%`).
  5. The Causal and Readout nodes both turn green, and the flow edge returns to solid gray.
* **Script**:
  > "I click Approve. The system runs the new tasks, updates the agent's evaluation scores, and the router automatically reroutes requests to a healthy AWS Spare.
  > Observe the recovery sequence: Causal Estimation heals first, and the downstream Readout follows a beat later as clean data flows through. The system has self-healed."

### Beat 5: Optimization & Conclusion (2:30 - 3:00)
* **Goal**: Close on the optimization results and the Pareto curve.
* **Visuals**:
  1. Operator switches to the **Pareto** tab.
  2. Show the learned router's curve drawing itself over the baseline.
  3. Point to the callout: `learned router — same quality, ~40% less cost`.
* **Script**:
  > "To close, we view the Pareto tab. Our learned router operates on a superior efficiency frontier. At the same quality target, it achieves a ~40% reduction in query cost compared to a baseline matcher. 
  > AgentLab doesn't just route—it detects, isolates, generates tests, recovers, and optimizes. Thank you."
