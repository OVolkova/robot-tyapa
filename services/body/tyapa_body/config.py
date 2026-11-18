import os

DRY_RUN = os.getenv("BODY_DRY_RUN", "0") == "1"  # laptop: log commands instead of sending
ROBOT_BAUD = 115200
ROBOT_WAKE_DELAY_S = 0.5
GAIT_MAX_S = float(
    os.getenv("GAIT_MAX_S", "10")
)  # any gait stops after this; 0 = never (V1 behaviour)
STOP_ACTION = "balance"  # stand still, servos on
TICK_MS = 100  # watchdog resolution
