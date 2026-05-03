import os
import subprocess
import time
import traceback

import numpy as np
from pycoral.utils.edgetpu import list_edge_tpus, make_interpreter


MODEL = "/app/mobilenet_v2_1.0_224_inat_bird_quant_edgetpu.tflite"
INTERVAL = int(os.environ.get("PROBE_INTERVAL", "60"))


def run(command):
    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.strip(), flush=True)
    if proc.stderr:
        print(proc.stderr.strip(), flush=True)


def probe_once():
    print("coral-probe lsusb:", flush=True)
    run(["lsusb"])

    tpus = list_edge_tpus()
    print(f"coral-probe listed_tpus={tpus}", flush=True)

    interpreter = make_interpreter(MODEL)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    input_data = np.zeros(input_details["shape"], dtype=input_details["dtype"])
    interpreter.set_tensor(input_details["index"], input_data)

    start = time.monotonic()
    interpreter.invoke()
    elapsed_ms = (time.monotonic() - start) * 1000

    output_details = interpreter.get_output_details()[0]
    output = interpreter.get_tensor(output_details["index"])
    print(
        "coral-probe ok "
        f"elapsed_ms={elapsed_ms:.2f} "
        f"output_shape={tuple(output.shape)} "
        f"output_dtype={output.dtype}",
        flush=True,
    )


print("coral-probe starting", flush=True)

while True:
    try:
        probe_once()
    except Exception:
        print("coral-probe failed", flush=True)
        print(traceback.format_exc(), flush=True)
    time.sleep(INTERVAL)
