import time
from common.schema import TaskFamily
from orchestrator.hub import OrchestratorHub

def run_smoke_test():
    print("=== AgentLab E2E Pipeline Smoke Test ===")
    print("Initializing Orchestrator Hub...")
    hub = OrchestratorHub()
    
    print("\n--- Running Healthy Experiment Readout Workflow ---")
    start_time = time.time()
    res = hub.run_workflow(
        initial_prompt="Analyze randomization and lift estimates for Experiment #1093."
    )
    duration = time.time() - start_time
    
    print(f"Status: SUCCESS")
    print(f"Workflow ID: {res['request_id']}")
    print(f"Total pipeline execution latency: {res['metrics']['total_latency_ms']:.2f} ms (actual duration: {duration*1000:.2f} ms)")
    print(f"Total tokens in: {res['metrics']['total_tokens_in']}")
    print(f"Total tokens out: {res['metrics']['total_tokens_out']}")
    
    print("\nStep 1 (GCP - Data Prep) Output:")
    print(res["steps"]["data_prep"].output.strip())
    print(f"Self-reports: {res['steps']['data_prep'].self_reports}")
    
    print("\nStep 2 (AWS - Causal Estimation) Output:")
    print(res["steps"]["causal_estimation"].output.strip())
    print(f"Self-reports: {res['steps']['causal_estimation'].self_reports}")
    
    print("\nStep 3 (Azure - Readout) Output:")
    print(res["steps"]["readout"].output.strip())
    print(f"Self-reports: {res['steps']['readout'].self_reports}")
    
    print("\n--- Running Degraded Causal Estimation Workflow ---")
    res_deg = hub.run_workflow(
        initial_prompt="Analyze randomization and lift estimates for Experiment #1093.",
        degrade_step=TaskFamily.CAUSAL_ESTIMATION
    )
    print("Degraded Causal Step Output:")
    print(res_deg["steps"]["causal_estimation"].output.strip())
    print(f"Degraded Causal Step Self-reports: {res_deg['steps']['causal_estimation'].self_reports}")
    
    print("\n=========================================")
    print("Smoke Test completed successfully!")
    print("=========================================")

if __name__ == "__main__":
    run_smoke_test()
