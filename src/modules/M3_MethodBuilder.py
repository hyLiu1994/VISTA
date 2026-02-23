import sys
import os

root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

import re,pandas
import logging
import threading
import numpy as np
from src.utils.CallApi import call_qwen_api
from src.modules.Prompt import Function_Prompt

# Method Builder statistics (thread-safe)
_mb_lock = threading.Lock()
_mb_stats = {
    'total_calls': 0,          # total generate_vf calls
    'reuse_sdkg': 0,           # reused existing VF from SDKG directly
    'first_attempt_success': 0, # LLM first attempt passed validation
    'retry_success': 0,        # succeeded after retry
    'final_failure': 0,        # failed after all retries
    'total_llm_attempts': 0,   # total LLM calls made
}

def get_mb_stats():
    with _mb_lock:
        return _mb_stats.copy()

def log_mb_stats():
    s = get_mb_stats()
    total = s['total_calls']
    if total == 0:
        logging.info("[MethodBuilder Stats] No calls recorded")
        return s
    llm_needed = total - s['reuse_sdkg']
    first_success_rate_excl = s['first_attempt_success'] / llm_needed if llm_needed > 0 else 0
    first_success_rate_incl = (s['reuse_sdkg'] + s['first_attempt_success']) / total
    final_success = s['reuse_sdkg'] + s['first_attempt_success'] + s['retry_success']
    final_success_rate = final_success / total if total > 0 else 0
    avg_retries_excl = s['total_llm_attempts'] / llm_needed if llm_needed > 0 else 0
    avg_retries_incl = s['total_llm_attempts'] / total
    logging.info("=" * 50)
    logging.info("METHOD BUILDER STATISTICS")
    logging.info("=" * 50)
    logging.info(f"Total calls: {total}")
    logging.info(f"Reused from SDKG: {s['reuse_sdkg']} ({s['reuse_sdkg']/total:.1%})")
    logging.info(f"LLM generation needed: {llm_needed}")
    logging.info(f"  First-attempt success: {s['first_attempt_success']} ({first_success_rate_excl:.1%})")
    logging.info(f"  Retry success: {s['retry_success']}")
    logging.info(f"  Final failure: {s['final_failure']}")
    logging.info(f"Total LLM attempts: {s['total_llm_attempts']}")
    logging.info(f"Avg retries per generation (excl reuse): {avg_retries_excl:.2f}")
    logging.info(f"First success rate (incl reuse): {first_success_rate_incl:.1%}")
    logging.info(f"Avg retries (incl reuse): {avg_retries_incl:.2f}")
    logging.info(f"Final success rate: {final_success}/{total} ({final_success_rate:.1%})")
    logging.info("=" * 50)
    return s

def extract_function_and_description(text):
    """Extract function code and description from LLM output"""
    func_match = re.search(r"(?:```python|''')[\s\r\n]*(.*?)[\s\r\n]*(?:```|''')", text, re.DOTALL)
    desc_match = re.search(r"Description:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    spatial_function = func_match.group(1).strip() if func_match else None
    function_description = desc_match.group(1).strip() if desc_match else ""
    return spatial_function, function_description

def compile_function_from_code(spatial_function_code):
    """Compile spatial function from code string"""
    local_ns = {}
    try:
        exec(spatial_function_code, {}, local_ns)
        function = local_ns.get("spatial_function", None)
        return function
    except Exception as e:
        raise RuntimeError(f"Function compilation failed: {e}")

def evaluate_function_on_batch(fn, minimal_seg_np):
    """
    Evaluate spatial function on batch data Returns: e_f, debug_string, mae_lat, mae_lon
    """
    N = minimal_seg_np.shape[0]
    lat_idx, lon_idx, ts_idx = 0, 1, 2   
    start = (float(minimal_seg_np[0, lat_idx]), float(minimal_seg_np[0, lon_idx]))
    end   = (float(minimal_seg_np[-1, lat_idx]), float(minimal_seg_np[-1, lon_idx]))
    
    try:
        timestamps = minimal_seg_np[:, ts_idx]
        start_time = pandas.to_datetime(timestamps[0])
        T = np.array([(pandas.to_datetime(ts) - start_time).total_seconds() for ts in timestamps])
        if np.any(np.isnan(T)) or len(T) == 0:
            raise ValueError("Invalid timestamps detected")           
        logging.info(f"Using real timestamps: {T}")
    except Exception as e:
        logging.warning(f"Failed to parse timestamps: {e}, using default time range")
        T = list(range(N)) 
    
    pred = fn(start, end, T)
    pred = np.array(pred, dtype=float)

    truth_mid = minimal_seg_np[1:-1, [lat_idx, lon_idx]].astype(float)
    pred_mid = pred[1:-1, :]

    diff = np.abs(pred_mid - truth_mid)
    mae_lat = float(np.mean(diff[:, 0])) if diff.size else float("inf")
    mae_lon = float(np.mean(diff[:, 1])) if diff.size else float("inf")
    e_f = 0.5 * (mae_lat + mae_lon)
    
    return e_f, mae_lat, mae_lon

def generate_vf(args, vb, SDKG, minimal_seg):
    """Generate and validate spatial function for a vb """
    is_new_vf = True

    def build_prompt(feedback_txt=""):
        return Function_Prompt.format(
            combined_data='\n'.join(minimal_seg['dynamic_info']).strip(),
            pattern=vb["llm_output"],
            feedback_txt=feedback_txt
        )

    args.llm_purpose = "function"

    attempt_ok = False
    last_err_msg = spatial_function_code = function_description = ""
    llm_attempts = 0

    selected_vf = SDKG.select_Cf_vb(vb)

    if selected_vf:
        spatial_function_code = selected_vf.get("code", "")
        function_description = selected_vf.get("description", "")
        logging.info("Selected existing VF from SDKG")

        function = compile_function_from_code(spatial_function_code)
        e_f,mae_lat, mae_lon = evaluate_function_on_batch(function, minimal_seg[['latitude', 'longitude', 'timestamp']].to_numpy())
        logging.info(f" Selected VF validation → {e_f}")
        if e_f <= args.e_f:
            attempt_ok = True
            is_new_vf = False
            logging.info("Selected VF passed validation")
            with _mb_lock:
                _mb_stats['total_calls'] += 1
                _mb_stats['reuse_sdkg'] += 1
        else:
            logging.warning(f"Selected VF failed validation: e(f)={e_f:.6f}")


    if not attempt_ok:
        logging.info("No suitable VF found in SDKG, generating new function...")
        for attempt in range(1, args.retry_times + 1):
            feedback = ""
            if attempt > 1 and last_err_msg:
                feedback = (
                    "\n\nFeedback: The previous function failed validation.\n"
                    f"{last_err_msg}\n"
                    "Please regenerate a numerically stable function that returns an array of points with shape (N or N+2, 2) "
                    "and reduces e(f)=0.5*(MAE_lat+MAE_lon) below 3e-3 degrees.\n"
                )

            llm_attempts += 1
            try:
                response_text = call_qwen_api(args, build_prompt(feedback_txt=feedback),args.coding_llm,'function')
                spatial_function_code, function_description = extract_function_and_description(response_text)

                if not spatial_function_code:
                    last_err_msg = "No valid function definition found."
                    logging.warning(f"Attempt {attempt}: {last_err_msg}")
                    continue

                # Validate function on trajectory data
                function = compile_function_from_code(spatial_function_code)
                e_f, mae_lat, mae_lon = evaluate_function_on_batch(function, minimal_seg[['latitude', 'longitude', 'timestamp']].to_numpy())
                logging.info(f"Attempt {attempt} validation → {e_f}")

                if e_f <= args.e_f:
                    attempt_ok = True
                    break
                else:
                    last_err_msg = (
                        f"Error summary: MAE_lat={mae_lat:.6f} deg, MAE_lon={mae_lon:.6f} deg, "
                        f"e(f)={e_f:.6f} deg exceeds threshold {args.e_f:.6f} deg."
                    )
            except Exception as e:
                last_err_msg = f"Runtime/validation error: {e}"
                logging.warning(f"Attempt {attempt} error: {last_err_msg}")

        # Record stats for LLM generation path
        with _mb_lock:
            _mb_stats['total_calls'] += 1
            _mb_stats['total_llm_attempts'] += llm_attempts
            if attempt_ok and llm_attempts == 1:
                _mb_stats['first_attempt_success'] += 1
            elif attempt_ok:
                _mb_stats['retry_success'] += 1
            else:
                _mb_stats['final_failure'] += 1

    vf = {
        "spatial_function": spatial_function_code,
        "describe_of_function": function_description.strip(),
    }
    logging.info("Function selected/generated successfully")
    return vf,is_new_vf



if __name__ == "__main__":
    print(sys.path)
    from src.modules.M0_SDKG import SDKG
    from src.utils.HyperParameters import configure_parser
    parser = configure_parser()
    args = parser.parse_args()
    SDKG = SDKG(args)
    args.raw_data_file = "/mnt/vdb1/2_workspace/interpretable_imputation/data/RawData/aisdk-2024-03-01@31_1.csv"
    from src.data.AISDataProcess import get_training_test_data
    _ , (test_df, mark_missing_test) = get_training_test_data(args)
    segment_idx = 0
    minimal_seg = test_df.iloc[segment_idx * args.mini_segment_len:(segment_idx + 1) * args.mini_segment_len]
    v_s = generate_vf(args, minimal_seg, SDKG)
    print(v_s)