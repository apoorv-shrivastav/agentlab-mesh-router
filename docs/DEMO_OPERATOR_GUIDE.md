# AgentLab Console Operator Guide — Live 3-Minute Demo

This document provides a click-by-click operational sequence for driving the console UI during the live panel presentation. Use this to sync the speaker's narrative with the screen transitions.

- **Total Duration**: 3:00
- **Primary Roles**:
  - **Speaker/Narrator**: Speaks to the judges, directing their attention.
  - **Operator/Driver**: Clicks buttons, switches tabs, and points cursor at key UI elements.

---

## Pre-Demo Checklist (The Reset)
Before the pitch begins (or when resetting between judges/runs):
1. Locate the **Simulation Deck** at the bottom of the left sidebar.
2. Click the **`Force Reset System`** button.
3. This resets the console state to **Healthy**:
   - Tab resets to **Pipeline** (default).
   - Global status bar reads `● PIPELINE HEALTHY` (green).
   - `loopState` reads `idle` (blue/gray).
   - Causal lift ATE estimate monitor resets to `+2.4%` (green region).
   - All components display normal metrics (Data Prep = 0.98, Causal = 0.91, Readout = 0.94).

---

## Beat-by-Beat Operator Sequence

### Beat 1: The Pipeline — Healthy Regime
* **Time Window**: `0:00 – 0:35` (35 seconds)
* **Active Tab**: `Pipeline` (Default)
* **Speaker Script**:
  > *"This is a real workflow — analyzing a finished A/B test. Three agents in a pipeline. Each step's output feeds the next."*
* **Operator Actions**:
  1. Ensure the browser is on the **Pipeline** view.
  2. Hover the cursor over the three cards to highlight the cross-cloud layout:
     - **DATA PREP** (`● GCP`) — passRate `0.98`
     - **CAUSAL EST.** (`● AWS`) — passRate `0.91`
     - **READOUT** (`● Azure`) — passRate `0.94`
  3. Circle the cursor around the **ATE EFFECT ESTIMATE MONITOR** at the bottom of the screen.
  4. Point to the green lift dot showing **`+2.4%`**, highlighting that it sits comfortably within the statistical bounds of `[0.0%, 10.0%]`.

---

### Beat 2: Silent Failure & Propagation
* **Time Window**: `0:35 – 1:20` (45 seconds)
* **Active Tab**: `Pipeline` ➔ `Signals`
* **Speaker Script**:
  > *"The causal-estimation step's model just got upgraded — the kind of thing a vendor does without telling you. Nothing crashed. The causal agent is now producing an effect estimate outside the plausible statistical bounds — a confident, wrong number. And watch the readout: it's healthy, it did nothing wrong, but it just turned that wrong number into a confident wrong recommendation. The visible mistake is in the last step. The fault is two steps up. That's the trap."*
* **Operator Actions**:
  1. At **0:35**, click the red **`Trigger Pipeline Fault`** button in the sidebar (Simulation Deck).
  2. **Watch the Pipeline View update immediately**:
     - Global status turns red: `▲ DEGRADATION DETECTED` (pulsing).
     - `loopState` in the header switches to `detecting`.
     - **Causal Est.** node glows red (`animate-fault-glow`), and its passRate drops to `0.18`.
     - Causal ATE estimate dot leaps to the far right, displaying **`+48.5%`** (red, out of bounds).
     - The connecting arrow between Causal Est. and Readout flashes amber (`animate-flow-edge`).
     - **Readout** node glows amber (`animate-warn-glow`), and a bounce label appears: `"input from CAUSAL ↑"`.
  3. At **0:50**, click the **`Signals`** tab in the sidebar.
  4. Highlight the three triggered alarms:
     - **Out of Bounds Lift Ratio**: Sparkline spikes up, status displays `ALARM` (value `1.0`).
     - **System Latency Spike**: Latency shows `ALARM` (`450ms` vs `280ms`).
     - **Low Confidence Output**: Readout classifier shows `ALARM` (value `1.0`).
  5. Hover over the **Low Confidence Output** alarm to show that the downstream Readout agent caught the logical error.

---

### Beat 3: Localization & Triage (The Headline Beat)
* **Time Window**: `1:20 – 2:15` (55 seconds)
* **Active Tab**: `Triage`
* **Speaker Script**:
  > *"This is the part nobody else automates. The triage agent — Gemini 3.5 Flash — clustered the failures and localized the fault: not to the step that looks wrong, but to the causal step that actually broke. It separated the cause from the symptom. And it didn't just point — it reasoned through the pattern and drafted new evaluation cases targeting that exact failure. I review the drafted tests and approve them. That approval is deliberate... New tests, targeting exactly what broke, now in the golden set."*
* **Operator Actions**:
  1. Click the **`Triage`** tab in the sidebar (note: a red ping indicator will be pulsing next to it).
     - *Note: Under the hood, 2.5 seconds after clicking the trigger, the triage agent starts streaming logs. If you switch to Triage, you'll see the terminal logs scrolling live in `triage_reasoner_shell.log`.*
  2. Let the logs stream visibly on screen. Once they finish (takes ~5 seconds), the **Fault Localized Verdict** card snaps into view.
  3. Point to the **Verdict Card**:
     - **CAUSE**: `CAUSAL ESTIMATION` (Red chip)
     - **SYMPTOM**: `READOUT` (Amber chip)
     - Under "root cause", point to the description stating that the +48.5% estimate violated the statistical thresholds.
  4. Scroll down to show the **Proposed Evaluation Scenarios** containing the 3 drafted tests:
     - `ATE Bounds Check`
     - `Covariate Covariance Variance`
     - `Readout Contamination Filter`
  5. At **2:10**, hover over the green **`Approve & Rollout Tasks`** button, wait for the narrator's cue (*"...now in the golden set"*), and **Click it**.

---

### Beat 4: Pipeline Recovery (Self-Healing)
* **Time Window**: `2:15 – 2:40` (25 seconds)
* **Active Tab**: `Pipeline` (Auto-Switched) ➔ `Router`
* **Speaker Script**:
  > *"The new tests re-scored the causal agent. The router saw the drop and rerouted that step to a healthy agent. The estimate is back inside bounds — and so is the readout, because the input it was given is now correct."*
* **Operator Actions**:
  1. The UI will **automatically switch** back to the **Pipeline** view after clicking Approve.
  2. Notice the `loopState` displays `re-scoring` (yellow, pulsing).
  3. **Watch the live transition**:
     - The ATE numeral slides rapidly downwards from **`+48.5%`** back to **`+2.4%`** (taking ~1 second).
     - The Causal Est. agent flips to **`causal-estimation-spare`** (`● AWS Spare`), and its passRate goes green at `0.93`.
     - The Readout node passRate goes back to green at `0.94`.
     - The global status returns to `● PIPELINE HEALTHY`, and loopState becomes `recovered`.
  4. At **2:30**, click the **`Router`** tab in the sidebar.
  5. Highlight the top entry of the decision table:
     - Request `req-7f89ac` mapped `causal_estimation` to `causal-estimation-spare` with a `0.94` success probability.
     - Rationale reads: *"Rerouted to spare after active fault isolation verified ATE constraints on model."*

---

### Beat 5: The Chart & Close
* **Time Window**: `2:40 – 3:00` (20 seconds)
* **Active Tab**: `Pareto`
* **Speaker Script**:
  > *"When an agent pipeline gives you a confident wrong answer, the question that matters isn't 'is something wrong' — it's which step, and how do you know. AgentLab answers both, with the statistics to back it. That's what agent infrastructure has to become."*
* **Operator Actions**:
  1. Click the **`Pareto`** tab in the sidebar.
  2. **Watch the animation**: The green glowing curve for the **Learned Router** will draw itself over the dashed gray baseline curve.
  3. Once the animation completes, the callout box will fade in: **`LEARNED ROUTER: same quality, ~40% less cost`**.
  4. Hover the cursor over the callout box and hold it there until the end of the presentation.

---

## Fallback Plan (If Live Services Hang)
If any step hangs for more than **15 seconds** during the live presentation:
1. Open the fallback dashboard URL (which uses the single-container SQLite snapshot: `agentlab-console-fallback`).
2. Continue narrating the script without calling attention to the transition.
3. The fallback console uses a read-only mock configuration that advances views automatically when clicked, bypassing any live GCP/AWS/Azure external API calls.
4. **Be honest if asked by judges**: *"We pivoted to a recorded snapshot from an hour ago due to local network latency, but the live code runs exactly the same pipeline."*
