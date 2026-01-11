import argparse, sys, os
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_path)
from src.utils.utils import get_root_path
root_path = get_root_path()
sys.path.append(root_path)

def configure_parser():
    """Configure command line arguments for the experiment"""
    parser = argparse.ArgumentParser(description="VISTA")

    # Base configuration
    base_group = parser.add_argument_group('Base Configuration')
    base_group.add_argument('--seed', type=int, default=40,
                          help='Random seed for reproducibility') 
    base_group.add_argument("--config", type=str,
                        default=f'config.yaml',
                        help='Path to configuration file')
    base_group.add_argument("--exp_name", type=str,
                        default=f'Default',
                        help='Experiment name')
    base_group.add_argument('--end_point_sdkg', type=int, default=2,
                          help='End point for SDKG load')
    base_group.add_argument('--check_point', type=int, default=0,
                          help='Starting point for processing')
    base_group.add_argument('--process_length', type=int, default=2,
                          help='How many pieces of data are saved once')
    base_group.add_argument('--end_point', type=int, default=1,
                          help='End point for processing')
    base_group.add_argument('--pre_load', type=bool, default=False,
                          help='IF you want preload the imputation results')
    # Dataset configuration
    dataset_group = parser.add_argument_group('Dataset Configuration')
    dataset_group.add_argument('--raw_data_file', type=str, default=f'{root_path}/data/RawData/aisdk-2024-03-01@31_1.csv',
                             help='Path to raw data file')
    dataset_group.add_argument('--trajectory_num', type=int, default=1000,
                             help='Number of trajectories to process')
    dataset_group.add_argument('--trajectory_len', type=int, default=200,
                             help='Length of each trajectory')
    dataset_group.add_argument('--mini_segment_len', type=int, default=20,
                             help='Minimum segment length')
    dataset_group.add_argument('--missing_ratio', type=float, default=0.2,
                             help='Ratio of missing data to simulate')
    dataset_group.add_argument('--training_test', type=float, default=0.8,
                             help='Training/test split ratio')
    # VISTA Configuration
    vista_group = parser.add_argument_group('VISTA Configuration')
    vista_group.add_argument('--retry_times', type=int, default=3,
                             help='Max retry attempts per function')
    vista_group.add_argument('--e_f', type=float, default=3e-3,
                             help='Error threshold: e(f)=0.5*(MAE_lat + MAE_lon)')
    vista_group.add_argument('--top_k', type=int, default=5,    
                            help='Top K candidate functions to consider')
    vista_group.add_argument('--max_concurrent', type=int, default=9,    
                            help='max concurrent nums')
    vista_group.add_argument('--max_retries', type=int, default=3,    
                            help='max retry times')
    # LLM Configuration
    llm_group = parser.add_argument_group('LLM Configuration')
    llm_group.add_argument('--llm_api_key', type=str, default='',
                             help='LLM API Key')
    llm_group.add_argument('--mining_llm', type=str, default='qwen-plus',
                             help='LLM model for pattern mining')
    llm_group.add_argument('--coding_llm', type=str, default='qwen-plus',
                             help='LLM model for code generation')
    llm_group.add_argument('--analysis_llm', type=str, default='qwen-plus',
                             help='LLM model for result analysis')
    
    # Parse initial arguments to get config file path
    args, unknown = parser.parse_known_args()
    
    # Load configuration from YAML file if it exists
    if args.config and os.path.exists(root_path + '/config/' + args.config):
        import yaml
        with open(root_path + '/config/' + args.config, 'r') as f:
            config = yaml.safe_load(f) 

        # Update parser defaults with config values
        if config:
            # Set defaults directly from config
            parser.set_defaults(**config)

    return parser