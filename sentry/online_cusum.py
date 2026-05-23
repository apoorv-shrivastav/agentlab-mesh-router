import numpy as np

class CUSUMDetector:
    def __init__(self, target_mean: float, target_std: float, k_factor: float = 0.5, h_factor: float = 4.0):
        """
        Cumulative Sum (CUSUM) Control Chart for detecting small, persistent shifts in signal rates.
        target_mean: Baseline expected value.
        target_std: Baseline standard deviation.
        k_factor: Slack parameter multiplier (usually 0.5, detecting a 1-sigma shift).
        h_factor: Threshold multiplier (usually 4 or 5, above which drift is flagged).
        """
        self.mean = target_mean
        self.std = max(target_std, 1e-5) # Avoid division by zero
        self.k = k_factor * self.std
        self.h = h_factor * self.std
        
        # Cumulative sums
        self.g_plus = 0.0
        self.g_minus = 0.0

    def update(self, x: float) -> tuple[bool, str]:
        """
        Updates the CUSUM chart with a new observation.
        Returns a tuple (drift_detected, direction) where direction is 'up', 'down', or 'none'.
        """
        # Upper CUSUM (detecting an increase in signal rate/failure rate)
        self.g_plus = max(0.0, self.g_plus + x - self.mean - self.k)
        # Lower CUSUM (detecting a decrease in signal rate)
        self.g_minus = max(0.0, self.g_minus + self.mean - self.k - x)
        
        if self.g_plus > self.h:
            return True, "up"
        if self.g_minus > self.h:
            return True, "down"
            
        return False, "none"

    def reset(self):
        self.g_plus = 0.0
        self.g_minus = 0.0


class EWMADetector:
    def __init__(self, target_mean: float, target_std: float, lambda_val: float = 0.2, L_factor: float = 3.0):
        """
        Exponentially Weighted Moving Average (EWMA) Control Chart.
        target_mean: Baseline expected value.
        target_std: Baseline standard deviation.
        lambda_val: Smoothing factor in [0, 1] (usually 0.1 to 0.3).
        L_factor: Control limit multiplier (usually 3.0).
        """
        self.mean = target_mean
        self.std = max(target_std, 1e-5)
        self.lam = lambda_val
        self.L = L_factor
        
        self.z = target_mean
        self.t = 0

    def update(self, x: float) -> bool:
        """
        Updates the EWMA chart with a new observation.
        Returns True if the value breaches the Control Limits (LCL/UCL).
        """
        self.t += 1
        self.z = self.lam * x + (1.0 - self.lam) * self.z
        
        # Compute exact time-varying variance
        var_z = (self.std ** 2) * (self.lam / (2.0 - self.lam)) * (1.0 - (1.0 - self.lam) ** (2 * self.t))
        std_z = np.sqrt(var_z)
        
        ucl = self.mean + self.L * std_z
        lcl = self.mean - self.L * std_z
        
        if self.z > ucl or self.z < lcl:
            return True
            
        return False

    def reset(self):
        self.z = self.mean
        self.t = 0


def detect_drift_in_series(
    series: list[float],
    baseline_mean: float,
    baseline_std: float,
    method: str = "cusum",
    **kwargs
) -> tuple[bool, int]:
    """
    Runs CUSUM or EWMA over a sequence of observations to identify drift.
    Returns (drift_detected, first_breach_index).
    """
    if method == "cusum":
        detector = CUSUMDetector(baseline_mean, baseline_std, **kwargs)
        for idx, val in enumerate(series):
            drifted, _ = detector.update(val)
            if drifted:
                return True, idx
    elif method == "ewma":
        detector = EWMADetector(baseline_mean, baseline_std, **kwargs)
        for idx, val in enumerate(series):
            if detector.update(val):
                return True, idx
                
    return False, -1
