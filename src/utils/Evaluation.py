import numpy as np
import pandas as pd
import logging
import json
import os
from src.utils.utils import get_root_path

def get_vf_function(sdkg, function_id):
    """Get and compile function from SDKG by function ID"""
    vf_node = sdkg.SDK_graph_vf_node.get(function_id)
    if not vf_node or not vf_node.get('code'):
        logging.warning(f"Function {function_id} not found or has no code")
        return None
    
    try:
        local_ns = {}
        exec(vf_node['code'], {'np': np}, local_ns)
        return local_ns.get("spatial_function")
    except Exception as e:
        logging.warning(f"Failed to compile function {function_id}: {e}")
        return None

def execute_imputation(function, segment_data, prev_segment_data=None, next_segment_data=None):
    """Execute imputation using the spatial function with context segments"""
    try:
        if prev_segment_data is not None and not prev_segment_data.empty:
            start = (float(prev_segment_data.iloc[-1]['latitude']), 
                    float(prev_segment_data.iloc[-1]['longitude']))
        else:
            start = (float(segment_data.iloc[0]['latitude']), 
                    float(segment_data.iloc[0]['longitude']))
            
        if next_segment_data is not None and not next_segment_data.empty:
            end = (float(next_segment_data.iloc[0]['latitude']), 
                  float(next_segment_data.iloc[0]['longitude']))
        else:
            end = (float(segment_data.iloc[-1]['latitude']), 
                  float(segment_data.iloc[-1]['longitude']))
        
        timestamps = segment_data['timestamp'].values
        start_time = pd.to_datetime(timestamps[0])
        T = np.array([(pd.to_datetime(ts) - start_time).total_seconds() for ts in timestamps])
        
        trajectory = function(start, end, T)
        return np.array(trajectory, dtype=float)
    except Exception as e:
        logging.warning(f"Imputation execution failed: {e}")
        return None

def save_evaluation_results(args, metrics):
    """Save evaluation results to file"""
    root_path = get_root_path()
    eval_dir = os.path.join(root_path, 'results', args.exp_name, 'EVA')
    os.makedirs(eval_dir, exist_ok=True)
    
    filename = f"evaluations{args.trajectory_num}_len{args.trajectory_len}_seed{args.seed}_{args.end_point_sdkg}_{args.end_point}.json"
    file_path = os.path.join(eval_dir, filename)
    
    # Add metadata to metrics
    metrics_with_meta = {
        'evaluation_metadata': {
            'exp_name': args.exp_name,
            'trajectory_num': args.trajectory_num,
            'trajectory_len': args.trajectory_len,
            'seed': args.seed,
            'end_point_sdkg': args.end_point_sdkg,
            'end_point': args.end_point,
            'timestamp': pd.Timestamp.now().isoformat()
        },
        'metrics': metrics
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(metrics_with_meta, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Evaluation results saved to: {file_path}")
    return file_path

def save_comparison_csv(args, comparison_data):
    """Save detailed comparison between original and imputed results to CSV"""
    root_path = get_root_path()
    comp_dir = os.path.join(root_path, 'results', args.exp_name, 'COMPARISON')
    os.makedirs(comp_dir, exist_ok=True)
    
    filename = f"comparison{args.trajectory_num}_len{args.trajectory_len}_seed{args.seed}_{args.end_point_sdkg}_{args.end_point}.csv"
    file_path = os.path.join(comp_dir, filename)
    
    # Create DataFrame from comparison data
    df = pd.DataFrame(comparison_data)
    
    # Save to CSV
    df.to_csv(file_path, index=False, encoding='utf-8')
    
    logging.info(f"Comparison results saved to: {file_path}")
    return file_path

def evaluate_imputed_result(args, result_manager, test_df, mark_missing_test, sdkg):
    """Evaluate imputation results by comparing with ground truth"""
    lat_errors, lon_errors, spherical_dists = [], [], []
    processed_segments = 0

    comparison_data = []
    
    for i, result in enumerate(result_manager.results_list):
        if not result or 'method_selector' not in result:
            continue
            
        try:
            # Get function from SDKG
            function_id = result['method_selector']['selected_function_id']
            function = get_vf_function(sdkg, function_id)
            if not function:
                continue
                
            # Get corresponding test data
            seq_data = test_df[
                (test_df['sequence_id'] == result['sequence_id']) & 
                (test_df['mmsi'] == result['mmsi'])
            ].sort_values('timestamp')
            
            seg_data = seq_data[seq_data['segment_id'] == result['segment_id']]
            
            if seg_data.empty:
                continue
            
            current_segment_id = result['segment_id']
            all_segments = seq_data['segment_id'].unique()
            current_idx = np.where(all_segments == current_segment_id)[0][0]
            
            prev_segment_data = None
            next_segment_data = None
            
            if current_idx > 0:
                prev_segment_id = all_segments[current_idx - 1]
                prev_segment_data = seq_data[seq_data['segment_id'] == prev_segment_id]
            
            if current_idx < len(all_segments) - 1:
                next_segment_id = all_segments[current_idx + 1]
                next_segment_data = seq_data[seq_data['segment_id'] == next_segment_id]
                
            # Execute imputation with context segments
            imputed_traj = execute_imputation(function, seg_data, prev_segment_data, next_segment_data)
            if imputed_traj is None:
                continue
                
            # Calculate errors (assuming entire segment is masked)
            true_points = seg_data[['latitude', 'longitude']].values.astype(float)

            for j, (true_point, imputed_point) in enumerate(zip(true_points, imputed_traj)):
                # Calculate spherical distance using Haversine formula
                R = 6371  
                lat1, lon1 = np.radians(true_point[0]), np.radians(true_point[1])
                lat2, lon2 = np.radians(imputed_point[0]), np.radians(imputed_point[1])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
                spherical_dist = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
                
                comparison_data.append({
                    'sequence_id': result['sequence_id'],
                    'mmsi': result['mmsi'],
                    'segment_id': result['segment_id'],
                    'point_index': j,
                    'timestamp': seg_data.iloc[j]['timestamp'],
                    'original_latitude': true_point[0],
                    'original_longitude': true_point[1],
                    'imputed_latitude': imputed_point[0],
                    'imputed_longitude': imputed_point[1],
                    'latitude_error': abs(true_point[0] - imputed_point[0]),
                    'longitude_error': abs(true_point[1] - imputed_point[1]),
                    'spherical_distance_km': spherical_dist,
                    'selected_function_id': function_id
                })

            lat_errors.extend(np.abs(true_points[:, 0] - imputed_traj[:, 0]))
            lon_errors.extend(np.abs(true_points[:, 1] - imputed_traj[:, 1]))
            
            # Calculate spherical distances using Haversine formula (in kilometers)
            R = 6371  # Earth radius in kilometers
            lat1, lon1 = np.radians(true_points[:, 0]), np.radians(true_points[:, 1])
            lat2, lon2 = np.radians(imputed_traj[:, 0]), np.radians(imputed_traj[:, 1])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            spherical_dists.extend(R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a)))
            
            processed_segments += 1
            
        except Exception as e:
            logging.warning(f"Failed to evaluate result {i}: {e}")
            continue
    
    # Calculate final metrics
    if not lat_errors:
        logging.error("No valid results to evaluate")
        metrics = {"error": "No valid results"}
        comparison_file = None
    else:
        lat_errors, lon_errors, spherical_dists = map(np.array, [lat_errors, lon_errors, spherical_dists])
        
        metrics = {
            'processed_segments': processed_segments,
            'processed_points': len(lat_errors),
            'latitude_mae': float(np.mean(lat_errors)),
            'longitude_mae': float(np.mean(lon_errors)),
            'latitude_rmse': float(np.sqrt(np.mean(lat_errors**2))),
            'longitude_rmse': float(np.sqrt(np.mean(lon_errors**2))),
            'mean_spherical_distance_km': float(np.mean(spherical_dists)),
            'max_spherical_distance_km': float(np.max(spherical_dists)),
            'min_spherical_distance_km': float(np.min(spherical_dists))
        }

        comparison_file = save_comparison_csv(args, comparison_data)
        metrics['comparison_file'] = comparison_file
    
    # Print evaluation results
    logging.info("\n" + "="*50)
    logging.info("IMPUTATION EVALUATION RESULTS")
    logging.info("="*50)
    logging.info(f"Processed segments: {metrics['processed_segments']}")
    logging.info(f"Total points evaluated: {metrics['processed_points']}")
    logging.info(f"Latitude MAE: {metrics['latitude_mae']:.6f}")
    logging.info(f"Longitude MAE: {metrics['longitude_mae']:.6f}")
    logging.info(f"Latitude RMSE: {metrics['latitude_rmse']:.6f}")
    logging.info(f"Longitude RMSE: {metrics['longitude_rmse']:.6f}")
    logging.info(f"Mean spherical distance: {metrics['mean_spherical_distance_km']:.4f} km")
    logging.info(f"Max spherical distance: {metrics['max_spherical_distance_km']:.4f} km")
    logging.info(f"Min spherical distance: {metrics['min_spherical_distance_km']:.4f} km")
    
    if comparison_file:
        logging.info(f"Detailed comparison saved to: {comparison_file}")
    
    logging.info("="*50)
    
    # Save results
    saved_file = save_evaluation_results(args, metrics)
    logging.info(f"Results saved to: {saved_file}")
    
    return metrics