import sys, os, re, logging
import pandas as pd

root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

from src.utils.CallApi import call_qwen_api
from modules.Prompt import Pattern_Prompt

def extract_from_llm(rules, field_name):
    """Extract field value from LLM output"""
    pattern = rf"\*\*\s*{re.escape(field_name)}\s*\*\*\s*:\s*(.*?)(?=\n|$)"
    match = re.search(pattern, rules, flags=re.IGNORECASE)
    return match.group(1).strip() if match else "unknown"

def generate_vb(args, minimal_seg, SDKG):
    """Generate patterns from trajectory data with identifiers"""
    logging.info("Generating patterns from trajectory data...")

    # Calculate duration directly
    duration_seconds = 0
    if 'timestamp' in minimal_seg.columns:
        timestamps = pd.to_datetime(minimal_seg['timestamp'], errors='coerce').dropna()
        if len(timestamps) >= 2:
            start_time = timestamps.iloc[0]
            end_time = timestamps.iloc[-1]
            duration_seconds = (end_time - start_time).total_seconds()
            logging.info(f"Calculated duration: {duration_seconds} seconds")
        else:
            # Insufficient data points, estimate based on point count
            num_points = len(minimal_seg)
            duration_seconds = num_points * 60  # Assume 60 seconds per point
            logging.info(f"Using estimated duration: {duration_seconds} seconds")
    else:
        # No timestamp column, estimate based on point count
        num_points = len(minimal_seg)
        duration_seconds = num_points * 60
        logging.info(f"Using estimated duration: {duration_seconds} seconds")
    
    # Direct discretization
    d = max(0, float(duration_seconds))
    step = 50
    lower = int(d // step) * step
    upper = lower + step
    duration = f"{lower}~{upper}"
    logging.info(f"Duration interval: {duration}")
    
    # Generate prompt with available options
    field_dicts = SDKG.get_vb_attributes_dicts()
    input_text = Pattern_Prompt.format(
        trajectory_data='\n'.join(minimal_seg['dynamic_info']).strip(),
        **field_dicts
    )
    # Call LLM API to generate patterns
    raw_output = call_qwen_api(args, input_text,args.mining_llm,'pattern')
    rule_blocks = re.findall(r"('''[\s\S]*?''')", raw_output, flags=re.DOTALL)
    
    if not rule_blocks:
        logging.warning("No valid pattern blocks found in LLM output")
        return []
    
    vb = []
    for block in rule_blocks:
        # Extract pattern components from LLM output
        speed_profile = extract_from_llm(block, "speed_pattern")
        course_change = extract_from_llm(block, "course_pattern")
        heading_fluctuation = extract_from_llm(block, "heading_pattern")
        intent = extract_from_llm(block, "intent")       
        
        # Construct pattern data
        pattern_data = {
            "speed_profile": speed_profile,
            "course_change": course_change,
            "heading_fluctuation": heading_fluctuation,
            "intent": intent,
            "duration": duration,
            "llm_output": block
        }
        
        # Add identification information
        vb.append(pattern_data)
        
        # Update pattern dictionary with new pattern
        new_flags=SDKG.update_dicts(pattern_data)

    return vb[0] if vb else None, new_flags

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
    v_b = generate_vb(args, minimal_seg, SDKG)
    print(v_b)

