import os, sys
import datetime
import logging
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)

def get_root_path():
    current_path = os.path.dirname(os.path.abspath(__file__))
    parent_current_path = os.path.dirname(current_path)
    root_path = os.path.dirname(parent_current_path)
    return root_path
    
def setup_logging(args):
    """
    Set up logging to file and console with timestamps.
    """
    # Create results directory if it doesn't exist
    results_dir = os.path.join(root_path, 'results', args.exp_name, 'logs')
    os.makedirs(results_dir, exist_ok=True)
    
    # Log file with timestamp
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"run_{current_time}.log"
    log_filepath = os.path.join(results_dir, log_filename)
    
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Log initial information
    logging.info(f" Starting experiment: {args.exp_name}")
    logging.info(f" Log file: {log_filepath}")
    logging.info(f" Start time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")